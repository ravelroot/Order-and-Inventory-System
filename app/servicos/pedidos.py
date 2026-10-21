from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import agora_utc
from app.erros import NaoEncontrado, RegraViolada, SemPermissao, TransicaoInvalida
from app.esquemas.pedidos import ItemPedidoEntrada, PedidoAtualizar, PedidoCriar
from app.modelos import Cliente, HistoricoPedido, ItemPedidoVenda, PedidoVenda, Usuario
from app.modelos.enums import OrigemMovimentacao, Papel, StatusPedido
from app.servicos import estoque
from app.servicos.estoque import Contexto

CENTAVO = Decimal("0.01")
CEM = Decimal("100")

LIMITE_DESCONTO = {
    Papel.ADMIN: Decimal("100"),
    Papel.GERENTE: Decimal("30"),
    Papel.VENDEDOR: Decimal("10"),
    Papel.ESTOQUISTA: Decimal("0"),
}

COMERCIAL = {Papel.ADMIN, Papel.GERENTE, Papel.VENDEDOR}
LOGISTICA = {Papel.ADMIN, Papel.GERENTE, Papel.ESTOQUISTA}
GESTAO = {Papel.ADMIN, Papel.GERENTE}

STATUS_EM_ABERTO_CREDITO = (
    StatusPedido.CONFIRMADO,
    StatusPedido.SEPARADO,
    StatusPedido.FATURADO,
    StatusPedido.ENVIADO,
)


@dataclass(frozen=True)
class Transicao:
    de: frozenset[StatusPedido]
    para: StatusPedido
    papeis: frozenset[Papel]
    somente_dono: bool = False


TRANSICOES: dict[str, Transicao] = {
    "confirmar": Transicao(frozenset({StatusPedido.RASCUNHO}), StatusPedido.CONFIRMADO, frozenset(COMERCIAL), True),
    "separar": Transicao(frozenset({StatusPedido.CONFIRMADO}), StatusPedido.SEPARADO, frozenset(LOGISTICA)),
    "faturar": Transicao(frozenset({StatusPedido.SEPARADO}), StatusPedido.FATURADO, frozenset(LOGISTICA)),
    "enviar": Transicao(frozenset({StatusPedido.FATURADO}), StatusPedido.ENVIADO, frozenset(LOGISTICA)),
    "entregar": Transicao(frozenset({StatusPedido.ENVIADO}), StatusPedido.ENTREGUE, frozenset(LOGISTICA)),
    "cancelar": Transicao(
        frozenset({StatusPedido.RASCUNHO, StatusPedido.CONFIRMADO, StatusPedido.SEPARADO, StatusPedido.FATURADO}),
        StatusPedido.CANCELADO,
        frozenset(COMERCIAL),
        True,
    ),
}


def _eh_dono_ou_gestor(pedido: PedidoVenda, usuario: Usuario) -> bool:
    return usuario.papel in GESTAO or pedido.vendedor_id == usuario.id


def pode(acao: str, pedido: PedidoVenda, usuario: Usuario) -> bool:
    if acao == "editar":
        return pedido.status == StatusPedido.RASCUNHO and usuario.papel in COMERCIAL and _eh_dono_ou_gestor(pedido, usuario)
    regra = TRANSICOES.get(acao)
    if regra is None or pedido.status not in regra.de or usuario.papel not in regra.papeis:
        return False
    if regra.somente_dono and not _eh_dono_ou_gestor(pedido, usuario):
        return False
    if acao == "cancelar" and pedido.status == StatusPedido.FATURADO and usuario.papel not in GESTAO:
        return False
    return True


def acoes_disponiveis(pedido: PedidoVenda, usuario: Usuario) -> list[str]:
    return [acao for acao in ("editar", *TRANSICOES) if pode(acao, pedido, usuario)]


def obter_pedido(sessao: Session, pedido_id: int, travar: bool = False) -> PedidoVenda:
    pedido = sessao.get(PedidoVenda, pedido_id, with_for_update={"of": PedidoVenda} if travar else None)
    if pedido is None:
        raise NaoEncontrado(f"Pedido {pedido_id} não encontrado.")
    return pedido


def _obter_cliente_ativo(sessao: Session, cliente_id: int) -> Cliente:
    cliente = sessao.get(Cliente, cliente_id)
    if cliente is None:
        raise NaoEncontrado(f"Cliente {cliente_id} não encontrado.")
    if not cliente.ativo:
        raise RegraViolada(f"O cliente {cliente.nome} está inativo.")
    return cliente


def calcular_total_item(quantidade: int, preco: Decimal, desconto_percentual: Decimal) -> Decimal:
    bruto = preco * quantidade
    return (bruto * (CEM - desconto_percentual) / CEM).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _montar_itens(sessao: Session, entradas: list[ItemPedidoEntrada], usuario: Usuario) -> list[ItemPedidoVenda]:
    limite = LIMITE_DESCONTO[usuario.papel]
    itens = []
    for entrada in entradas:
        produto = estoque.obter_produto(sessao, entrada.produto_id)
        if not produto.ativo:
            raise RegraViolada(f"O produto {produto.sku} está inativo e não pode ser vendido.")
        if produto.preco_venda <= 0:
            raise RegraViolada(f"O produto {produto.sku} está sem preço de venda.")
        if entrada.desconto_percentual > limite:
            raise RegraViolada(
                f"Desconto de {entrada.desconto_percentual}% em {produto.sku} passa do limite do seu perfil ({limite}%).",
                {"produto_id": produto.id, "limite": float(limite)},
            )
        itens.append(
            ItemPedidoVenda(
                produto_id=produto.id,
                produto=produto,
                quantidade=entrada.quantidade,
                preco_unitario=produto.preco_venda,
                desconto_percentual=entrada.desconto_percentual,
                custo_unitario=produto.custo_medio,
                total=calcular_total_item(entrada.quantidade, produto.preco_venda, entrada.desconto_percentual),
            )
        )
    return itens


def recalcular_totais(pedido: PedidoVenda) -> None:
    bruto = sum((i.preco_unitario * i.quantidade for i in pedido.itens), Decimal("0"))
    liquido = sum((i.total for i in pedido.itens), Decimal("0"))
    pedido.subtotal = bruto.quantize(CENTAVO)
    pedido.desconto_total = (bruto - liquido).quantize(CENTAVO)
    pedido.total = (liquido + (pedido.frete or Decimal("0"))).quantize(CENTAVO)


def _historico(
    pedido: PedidoVenda, de: StatusPedido | None, para: StatusPedido, usuario: Usuario | None, obs: str | None, momento: datetime
) -> None:
    pedido.historico.append(
        HistoricoPedido(
            de_status=de, para_status=para, observacao=obs, usuario_id=usuario.id if usuario else None, criado_em=momento
        )
    )


def criar(
    sessao: Session,
    dados: PedidoCriar,
    usuario: Usuario,
    chave_idempotencia: str | None = None,
    agora: datetime | None = None,
) -> tuple[PedidoVenda, bool]:
    if chave_idempotencia:
        existente = sessao.scalars(
            select(PedidoVenda).where(PedidoVenda.vendedor_id == usuario.id, PedidoVenda.chave_idempotencia == chave_idempotencia)
        ).first()
        if existente is not None:
            return existente, False

    momento = agora or agora_utc()
    _obter_cliente_ativo(sessao, dados.cliente_id)
    estoque.obter_deposito(sessao, dados.deposito_id)
    pedido = PedidoVenda(
        cliente_id=dados.cliente_id,
        deposito_id=dados.deposito_id,
        vendedor_id=usuario.id,
        status=StatusPedido.RASCUNHO,
        frete=dados.frete,
        observacoes=dados.observacoes,
        chave_idempotencia=chave_idempotencia,
        criado_em=momento,
        atualizado_em=momento,
    )
    pedido.itens = _montar_itens(sessao, dados.itens, usuario)
    recalcular_totais(pedido)
    _historico(pedido, None, StatusPedido.RASCUNHO, usuario, "Pedido criado", momento)
    sessao.add(pedido)
    sessao.flush()
    pedido.numero = f"PV-{momento.year}-{pedido.id:06d}"
    return pedido, True


def atualizar(sessao: Session, pedido: PedidoVenda, dados: PedidoAtualizar, usuario: Usuario) -> PedidoVenda:
    if not pode("editar", pedido, usuario):
        raise TransicaoInvalida("Só é possível editar pedidos em rascunho que sejam seus.")
    campos = dados.model_dump(exclude_unset=True)
    if "cliente_id" in campos and campos["cliente_id"] is not None:
        _obter_cliente_ativo(sessao, campos["cliente_id"])
        pedido.cliente_id = campos["cliente_id"]
    if "deposito_id" in campos and campos["deposito_id"] is not None:
        estoque.obter_deposito(sessao, campos["deposito_id"])
        pedido.deposito_id = campos["deposito_id"]
    if "frete" in campos and campos["frete"] is not None:
        pedido.frete = campos["frete"]
    if "observacoes" in campos:
        pedido.observacoes = campos["observacoes"]
    recalcular_totais(pedido)
    return pedido


def substituir_itens(sessao: Session, pedido: PedidoVenda, entradas: list[ItemPedidoEntrada], usuario: Usuario) -> PedidoVenda:
    if not pode("editar", pedido, usuario):
        raise TransicaoInvalida("Só é possível alterar itens de pedidos em rascunho que sejam seus.")
    pedido.itens.clear()
    sessao.flush()
    pedido.itens.extend(_montar_itens(sessao, entradas, usuario))
    recalcular_totais(pedido)
    return pedido


def _verificar_credito(sessao: Session, pedido: PedidoVenda, usuario: Usuario) -> str | None:
    cliente = pedido.cliente
    if not cliente.limite_credito or cliente.limite_credito <= 0:
        return None
    em_aberto = sessao.scalar(
        select(func.coalesce(func.sum(PedidoVenda.total), 0)).where(
            PedidoVenda.cliente_id == cliente.id,
            PedidoVenda.status.in_(STATUS_EM_ABERTO_CREDITO),
            PedidoVenda.id != pedido.id,
        )
    ) or Decimal("0")
    comprometido = Decimal(em_aberto) + pedido.total
    if comprometido <= cliente.limite_credito:
        return None
    if usuario.papel in GESTAO:
        return f"Limite de crédito excedido (R$ {comprometido:.2f} de R$ {cliente.limite_credito:.2f}) — liberado pela gestão"
    raise RegraViolada(
        "O pedido ultrapassa o limite de crédito do cliente. Peça liberação a um gerente.",
        {"limite": float(cliente.limite_credito), "comprometido": float(comprometido)},
        codigo="limite_credito",
    )


def transicionar(
    sessao: Session,
    pedido: PedidoVenda,
    acao: str,
    usuario: Usuario,
    observacao: str | None = None,
    codigo_rastreio: str | None = None,
    motivo: str | None = None,
    agora: datetime | None = None,
) -> PedidoVenda:
    regra = TRANSICOES.get(acao)
    if regra is None:
        raise NaoEncontrado(f"Ação '{acao}' não existe.")
    if pedido.status not in regra.de:
        raise TransicaoInvalida(
            f"Não é possível {acao} um pedido com status {pedido.status.value}.",
            {"status_atual": pedido.status.value, "permitido_de": sorted(s.value for s in regra.de)},
        )
    if not pode(acao, pedido, usuario):
        raise SemPermissao(f"Seu perfil não pode {acao} este pedido.")

    momento = agora or agora_utc()
    de = pedido.status
    itens = [(i.produto_id, i.quantidade) for i in pedido.itens]
    ctx = Contexto(usuario, OrigemMovimentacao.PEDIDO_VENDA, pedido.id, f"Pedido {pedido.numero}", momento)

    if acao == "confirmar":
        aviso = _verificar_credito(sessao, pedido, usuario)
        observacao = "; ".join(x for x in (observacao, aviso) if x) or None
        estoque.reservar(sessao, pedido.deposito_id, itens, ctx)
        pedido.confirmado_em = momento
    elif acao == "faturar":
        estoque.baixar_reservado(sessao, pedido.deposito_id, itens, ctx)
        pedido.faturado_em = momento
    elif acao == "enviar":
        if not codigo_rastreio:
            raise RegraViolada("Informe o código de rastreio para enviar o pedido.")
        pedido.codigo_rastreio = codigo_rastreio
        pedido.enviado_em = momento
    elif acao == "entregar":
        pedido.entregue_em = momento
    elif acao == "cancelar":
        if not motivo:
            raise RegraViolada("Informe o motivo do cancelamento.")
        if de in (StatusPedido.CONFIRMADO, StatusPedido.SEPARADO):
            ctx.motivo = f"Cancelamento do pedido {pedido.numero}"
            estoque.liberar_reserva(sessao, pedido.deposito_id, itens, ctx)
        elif de == StatusPedido.FATURADO:
            ctx.motivo = f"Estorno do pedido {pedido.numero}"
            estoque.estornar(sessao, pedido.deposito_id, itens, ctx)
        pedido.motivo_cancelamento = motivo
        pedido.cancelado_em = momento
        observacao = observacao or motivo

    pedido.status = regra.para
    pedido.atualizado_em = momento
    _historico(pedido, de, regra.para, usuario, observacao, momento)
    return pedido
