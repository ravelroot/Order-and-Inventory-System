from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database import agora_utc
from app.erros import NaoEncontrado, RegraViolada, TransicaoInvalida
from app.esquemas.pedidos import CompraCriar, ItemRecebimento
from app.modelos import Fornecedor, ItemPedidoCompra, PedidoCompra, Usuario
from app.modelos.enums import OrigemMovimentacao, StatusCompra
from app.servicos import estoque
from app.servicos.estoque import Contexto


def obter_compra(sessao: Session, compra_id: int, travar: bool = False) -> PedidoCompra:
    compra = sessao.get(PedidoCompra, compra_id, with_for_update={"of": PedidoCompra} if travar else None)
    if compra is None:
        raise NaoEncontrado(f"Pedido de compra {compra_id} não encontrado.")
    return compra


def criar(sessao: Session, dados: CompraCriar, usuario: Usuario, agora: datetime | None = None) -> PedidoCompra:
    momento = agora or agora_utc()
    fornecedor = sessao.get(Fornecedor, dados.fornecedor_id)
    if fornecedor is None:
        raise NaoEncontrado(f"Fornecedor {dados.fornecedor_id} não encontrado.")
    if not fornecedor.ativo:
        raise RegraViolada(f"O fornecedor {fornecedor.razao_social} está inativo.")
    estoque.obter_deposito(sessao, dados.deposito_id)
    itens = []
    for entrada in dados.itens:
        produto = estoque.obter_produto(sessao, entrada.produto_id)
        itens.append(
            ItemPedidoCompra(
                produto_id=produto.id,
                produto=produto,
                quantidade=entrada.quantidade,
                custo_unitario=entrada.custo_unitario,
            )
        )
    compra = PedidoCompra(
        fornecedor_id=fornecedor.id,
        deposito_id=dados.deposito_id,
        previsao_entrega=dados.previsao_entrega,
        observacoes=dados.observacoes,
        criado_por_id=usuario.id,
        itens=itens,
        total=sum((i.custo_unitario * i.quantidade for i in itens), Decimal("0")),
        criado_em=momento,
        atualizado_em=momento,
    )
    sessao.add(compra)
    sessao.flush()
    compra.numero = f"PC-{momento.year}-{compra.id:06d}"
    return compra


def enviar(compra: PedidoCompra, agora: datetime | None = None) -> PedidoCompra:
    if compra.status != StatusCompra.RASCUNHO:
        raise TransicaoInvalida(f"Só pedidos em rascunho podem ser enviados (atual: {compra.status.value}).")
    compra.status = StatusCompra.ENVIADO
    compra.enviado_em = agora or agora_utc()
    return compra


def cancelar(compra: PedidoCompra) -> PedidoCompra:
    if compra.status not in (StatusCompra.RASCUNHO, StatusCompra.ENVIADO):
        raise TransicaoInvalida("Pedidos com recebimento não podem ser cancelados.")
    compra.status = StatusCompra.CANCELADO
    return compra


def receber(
    sessao: Session,
    compra: PedidoCompra,
    usuario: Usuario,
    itens: list[ItemRecebimento] | None = None,
    agora: datetime | None = None,
) -> PedidoCompra:
    if compra.status not in (StatusCompra.ENVIADO, StatusCompra.RECEBIDO_PARCIAL):
        raise TransicaoInvalida(f"Só pedidos enviados podem ser recebidos (atual: {compra.status.value}).")
    momento = agora or agora_utc()
    por_id = {i.id: i for i in compra.itens}
    if itens is None:
        recebimentos = [(item, item.pendente) for item in compra.itens if item.pendente > 0]
    else:
        recebimentos = []
        for entrada in itens:
            item = por_id.get(entrada.item_id)
            if item is None:
                raise NaoEncontrado(f"Item {entrada.item_id} não pertence a este pedido de compra.")
            if entrada.quantidade > item.pendente:
                raise RegraViolada(
                    f"Recebendo {entrada.quantidade} de {item.produto.sku}, mas só faltam {item.pendente}.",
                    {"item_id": item.id, "pendente": item.pendente},
                )
            if entrada.quantidade:
                recebimentos.append((item, entrada.quantidade))
    if not recebimentos:
        raise RegraViolada("Nada para receber.")

    ctx = Contexto(usuario, OrigemMovimentacao.PEDIDO_COMPRA, compra.id, f"Recebimento {compra.numero}", momento)
    for item, quantidade in sorted(recebimentos, key=lambda r: r[0].produto_id):
        estoque.entrada(sessao, item.produto_id, compra.deposito_id, quantidade, ctx, item.custo_unitario)
        item.quantidade_recebida += quantidade
        if item.produto.fornecedor_id is None:
            item.produto.fornecedor_id = compra.fornecedor_id

    completo = all(i.pendente == 0 for i in compra.itens)
    compra.status = StatusCompra.RECEBIDO if completo else StatusCompra.RECEBIDO_PARCIAL
    compra.atualizado_em = momento
    if completo:
        compra.recebido_em = momento
    return compra
