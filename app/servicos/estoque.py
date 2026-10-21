from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import agora_utc
from app.erros import EstoqueInsuficiente, NaoEncontrado, RegraViolada
from app.modelos import Deposito, MovimentacaoEstoque, Produto, SaldoEstoque, Usuario
from app.modelos.enums import OrigemMovimentacao, TipoMovimentacao

CENTAVO = Decimal("0.01")


@dataclass
class Contexto:
    usuario: Usuario | None
    origem: OrigemMovimentacao = OrigemMovimentacao.MANUAL
    origem_id: int | None = None
    motivo: str | None = None
    agora: datetime | None = None

    @property
    def momento(self) -> datetime:
        return self.agora or agora_utc()


def obter_produto(sessao: Session, produto_id: int) -> Produto:
    produto = sessao.get(Produto, produto_id)
    if produto is None:
        raise NaoEncontrado(f"Produto {produto_id} não encontrado.")
    return produto


def obter_deposito(sessao: Session, deposito_id: int, exigir_ativo: bool = True) -> Deposito:
    deposito = sessao.get(Deposito, deposito_id)
    if deposito is None:
        raise NaoEncontrado(f"Depósito {deposito_id} não encontrado.")
    if exigir_ativo and not deposito.ativo:
        raise RegraViolada(f"O depósito {deposito.codigo} está inativo.")
    return deposito


def obter_saldo(sessao: Session, produto_id: int, deposito_id: int) -> SaldoEstoque:
    sessao.flush()
    consulta = (
        select(SaldoEstoque)
        .where(SaldoEstoque.produto_id == produto_id, SaldoEstoque.deposito_id == deposito_id)
        .with_for_update(of=SaldoEstoque)
        .execution_options(populate_existing=True)
    )
    saldo = sessao.scalars(consulta).first()
    if saldo is not None:
        return saldo
    try:
        with sessao.begin_nested():
            sessao.add(SaldoEstoque(produto_id=produto_id, deposito_id=deposito_id, quantidade=0, reservado=0))
    except IntegrityError:
        pass
    return sessao.scalars(consulta).one()


def _registrar(
    sessao: Session,
    saldo: SaldoEstoque,
    tipo: TipoMovimentacao,
    quantidade: int,
    ctx: Contexto,
    custo_unitario: Decimal | None = None,
    motivo: str | None = None,
) -> MovimentacaoEstoque:
    momento = ctx.momento
    saldo.atualizado_em = momento
    movimentacao = MovimentacaoEstoque(
        produto_id=saldo.produto_id,
        deposito_id=saldo.deposito_id,
        tipo=tipo,
        quantidade=quantidade,
        saldo_apos=saldo.quantidade,
        reservado_apos=saldo.reservado,
        custo_unitario=custo_unitario,
        origem=ctx.origem,
        origem_id=ctx.origem_id,
        motivo=motivo or ctx.motivo,
        usuario_id=ctx.usuario.id if ctx.usuario else None,
        criado_em=momento,
    )
    sessao.add(movimentacao)
    return movimentacao


def _insuficiente(saldo: SaldoEstoque, produto: Produto, solicitado: int, deposito: str) -> dict:
    return {
        "produto_id": produto.id,
        "sku": produto.sku,
        "produto": produto.nome,
        "deposito": deposito,
        "disponivel": saldo.disponivel,
        "solicitado": solicitado,
    }


def estoque_total(sessao: Session, produto_id: int) -> int:
    return sessao.scalar(select(func.coalesce(func.sum(SaldoEstoque.quantidade), 0)).where(SaldoEstoque.produto_id == produto_id))


def recalcular_custo_medio(produto: Produto, estoque_anterior: int, quantidade: int, custo: Decimal) -> None:
    base = max(estoque_anterior, 0)
    total = base + quantidade
    if total <= 0:
        return
    novo = (produto.custo_medio * base + custo * quantidade) / total
    produto.custo_medio = novo.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def entrada(
    sessao: Session,
    produto_id: int,
    deposito_id: int,
    quantidade: int,
    ctx: Contexto,
    custo_unitario: Decimal | None = None,
    tipo: TipoMovimentacao = TipoMovimentacao.ENTRADA,
) -> MovimentacaoEstoque:
    produto = obter_produto(sessao, produto_id)
    obter_deposito(sessao, deposito_id)
    if custo_unitario is not None and tipo == TipoMovimentacao.ENTRADA:
        recalcular_custo_medio(produto, estoque_total(sessao, produto_id), quantidade, Decimal(custo_unitario))
    saldo = obter_saldo(sessao, produto_id, deposito_id)
    saldo.quantidade += quantidade
    return _registrar(sessao, saldo, tipo, quantidade, ctx, custo_unitario or produto.custo_medio)


def ajustar(sessao: Session, produto_id: int, deposito_id: int, contada: int, ctx: Contexto) -> MovimentacaoEstoque | None:
    produto = obter_produto(sessao, produto_id)
    obter_deposito(sessao, deposito_id)
    saldo = obter_saldo(sessao, produto_id, deposito_id)
    diferenca = contada - saldo.quantidade
    if diferenca == 0:
        return None
    if contada < saldo.reservado:
        raise RegraViolada(
            f"Há {saldo.reservado} unidade(s) reservadas para pedidos; a contagem não pode ficar abaixo disso.",
            {"reservado": saldo.reservado, "contada": contada},
        )
    saldo.quantidade = contada
    tipo = TipoMovimentacao.AJUSTE_POSITIVO if diferenca > 0 else TipoMovimentacao.AJUSTE_NEGATIVO
    return _registrar(sessao, saldo, tipo, abs(diferenca), ctx, produto.custo_medio)


def transferir(
    sessao: Session, produto_id: int, origem_id: int, destino_id: int, quantidade: int, ctx: Contexto
) -> tuple[MovimentacaoEstoque, MovimentacaoEstoque]:
    produto = obter_produto(sessao, produto_id)
    origem = obter_deposito(sessao, origem_id)
    obter_deposito(sessao, destino_id)
    saldos = {d: obter_saldo(sessao, produto_id, d) for d in sorted((origem_id, destino_id))}
    saida_saldo, entrada_saldo = saldos[origem_id], saldos[destino_id]
    if saida_saldo.disponivel < quantidade:
        raise EstoqueInsuficiente(
            "Estoque disponível insuficiente no depósito de origem.",
            [_insuficiente(saida_saldo, produto, quantidade, origem.codigo)],
        )
    saida_saldo.quantidade -= quantidade
    mov_saida = _registrar(sessao, saida_saldo, TipoMovimentacao.TRANSFERENCIA_SAIDA, quantidade, ctx, produto.custo_medio)
    entrada_saldo.quantidade += quantidade
    mov_entrada = _registrar(sessao, entrada_saldo, TipoMovimentacao.TRANSFERENCIA_ENTRADA, quantidade, ctx, produto.custo_medio)
    return mov_saida, mov_entrada


def _travar_em_ordem(sessao: Session, deposito_id: int, itens: Iterable[tuple[int, int]]) -> list[tuple[SaldoEstoque, int]]:
    agrupado: dict[int, int] = {}
    for produto_id, quantidade in itens:
        agrupado[produto_id] = agrupado.get(produto_id, 0) + quantidade
    return [(obter_saldo(sessao, pid, deposito_id), agrupado[pid]) for pid in sorted(agrupado)]


def reservar(sessao: Session, deposito_id: int, itens: Iterable[tuple[int, int]], ctx: Contexto) -> None:
    deposito = obter_deposito(sessao, deposito_id)
    travados = _travar_em_ordem(sessao, deposito_id, itens)
    faltando = [
        _insuficiente(saldo, saldo.produto, quantidade, deposito.codigo)
        for saldo, quantidade in travados
        if saldo.disponivel < quantidade
    ]
    if faltando:
        raise EstoqueInsuficiente("Estoque disponível insuficiente para confirmar o pedido.", faltando)
    for saldo, quantidade in travados:
        saldo.reservado += quantidade
        _registrar(sessao, saldo, TipoMovimentacao.RESERVA, quantidade, ctx)


def liberar_reserva(sessao: Session, deposito_id: int, itens: Iterable[tuple[int, int]], ctx: Contexto) -> None:
    for saldo, quantidade in _travar_em_ordem(sessao, deposito_id, itens):
        liberar = min(quantidade, saldo.reservado)
        if liberar > 0:
            saldo.reservado -= liberar
            _registrar(sessao, saldo, TipoMovimentacao.LIBERACAO_RESERVA, liberar, ctx)


def baixar_reservado(sessao: Session, deposito_id: int, itens: Iterable[tuple[int, int]], ctx: Contexto) -> None:
    for saldo, quantidade in _travar_em_ordem(sessao, deposito_id, itens):
        if saldo.reservado < quantidade or saldo.quantidade < quantidade:
            raise RegraViolada(
                "A reserva do pedido não confere com o saldo; confira as movimentações do produto.",
                {"produto_id": saldo.produto_id, "reservado": saldo.reservado, "necessario": quantidade},
            )
        saldo.reservado -= quantidade
        saldo.quantidade -= quantidade
        _registrar(sessao, saldo, TipoMovimentacao.SAIDA, quantidade, ctx, saldo.produto.custo_medio)


def estornar(sessao: Session, deposito_id: int, itens: Iterable[tuple[int, int]], ctx: Contexto) -> None:
    for saldo, quantidade in _travar_em_ordem(sessao, deposito_id, itens):
        saldo.quantidade += quantidade
        _registrar(sessao, saldo, TipoMovimentacao.ESTORNO, quantidade, ctx, saldo.produto.custo_medio)
