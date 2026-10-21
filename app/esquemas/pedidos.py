from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator

from app.esquemas.comum import Esquema, Valor, ValorEntrada
from app.modelos import ItemPedidoCompra, ItemPedidoVenda, PedidoCompra, PedidoVenda
from app.modelos.enums import StatusCompra, StatusPedido

Observacao = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=2000)]
Quantidade = Annotated[int, Field(gt=0, le=100_000)]


class ItemPedidoEntrada(Esquema):
    produto_id: int
    quantidade: Quantidade
    desconto_percentual: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Decimal("0")


def _sem_produto_repetido(itens: list) -> list:
    ids = [i.produto_id for i in itens]
    if len(ids) != len(set(ids)):
        raise ValueError("O mesmo produto aparece mais de uma vez; junte as quantidades em um item")
    return itens


class PedidoCriar(Esquema):
    cliente_id: int
    deposito_id: int
    itens: Annotated[list[ItemPedidoEntrada], Field(min_length=1, max_length=200)]
    frete: ValorEntrada = Decimal("0")
    observacoes: Observacao = None

    _itens = field_validator("itens")(_sem_produto_repetido)


class PedidoAtualizar(Esquema):
    cliente_id: int | None = None
    deposito_id: int | None = None
    frete: ValorEntrada | None = None
    observacoes: Observacao = None


class ItensSubstituir(Esquema):
    itens: Annotated[list[ItemPedidoEntrada], Field(min_length=1, max_length=200)]

    _itens = field_validator("itens")(_sem_produto_repetido)


class AcaoPedido(Esquema):
    observacao: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=255)] = None


class EnvioPedido(AcaoPedido):
    codigo_rastreio: Annotated[str, StringConstraints(strip_whitespace=True, min_length=4, max_length=40)]


class CancelamentoPedido(Esquema):
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=255)]


class ItemPedidoSaida(Esquema):
    id: int
    produto_id: int
    sku: str
    produto: str
    quantidade: int
    preco_unitario: Valor
    desconto_percentual: Valor
    total: Valor

    @classmethod
    def de(cls, i: ItemPedidoVenda) -> "ItemPedidoSaida":
        return cls(
            id=i.id,
            produto_id=i.produto_id,
            sku=i.produto.sku,
            produto=i.produto.nome,
            quantidade=i.quantidade,
            preco_unitario=i.preco_unitario,
            desconto_percentual=i.desconto_percentual,
            total=i.total,
        )


class HistoricoSaida(Esquema):
    de_status: StatusPedido | None
    para_status: StatusPedido
    observacao: str | None
    usuario: str | None
    criado_em: datetime


class PedidoResumo(Esquema):
    id: int
    numero: str | None
    status: StatusPedido
    cliente_id: int
    cliente: str
    deposito: str
    vendedor: str | None
    quantidade_itens: int
    total: Valor
    criado_em: datetime
    faturado_em: datetime | None

    @classmethod
    def de(cls, p: PedidoVenda) -> "PedidoResumo":
        return cls(
            id=p.id,
            numero=p.numero,
            status=p.status,
            cliente_id=p.cliente_id,
            cliente=p.cliente.nome,
            deposito=p.deposito.codigo,
            vendedor=p.vendedor.nome if p.vendedor else None,
            quantidade_itens=sum(i.quantidade for i in p.itens),
            total=p.total,
            criado_em=p.criado_em,
            faturado_em=p.faturado_em,
        )


class PedidoSaida(PedidoResumo):
    deposito_id: int
    vendedor_id: int | None
    subtotal: Valor
    desconto_total: Valor
    frete: Valor
    observacoes: str | None
    codigo_rastreio: str | None
    motivo_cancelamento: str | None
    confirmado_em: datetime | None
    enviado_em: datetime | None
    entregue_em: datetime | None
    cancelado_em: datetime | None
    versao: int
    acoes_disponiveis: list[str] = []
    itens: list[ItemPedidoSaida]
    historico: list[HistoricoSaida]

    @classmethod
    def de(cls, p: PedidoVenda, acoes: list[str] | None = None) -> "PedidoSaida":
        base = PedidoResumo.de(p).model_dump()
        return cls(
            **base,
            deposito_id=p.deposito_id,
            vendedor_id=p.vendedor_id,
            subtotal=p.subtotal,
            desconto_total=p.desconto_total,
            frete=p.frete,
            observacoes=p.observacoes,
            codigo_rastreio=p.codigo_rastreio,
            motivo_cancelamento=p.motivo_cancelamento,
            confirmado_em=p.confirmado_em,
            enviado_em=p.enviado_em,
            entregue_em=p.entregue_em,
            cancelado_em=p.cancelado_em,
            versao=p.versao,
            acoes_disponiveis=acoes or [],
            itens=[ItemPedidoSaida.de(i) for i in p.itens],
            historico=[
                HistoricoSaida(
                    de_status=h.de_status,
                    para_status=h.para_status,
                    observacao=h.observacao,
                    usuario=h.usuario.nome if h.usuario else None,
                    criado_em=h.criado_em,
                )
                for h in p.historico
            ],
        )


class ItemCompraEntrada(Esquema):
    produto_id: int
    quantidade: Quantidade
    custo_unitario: ValorEntrada


class CompraCriar(Esquema):
    fornecedor_id: int
    deposito_id: int
    previsao_entrega: date | None = None
    itens: Annotated[list[ItemCompraEntrada], Field(min_length=1, max_length=200)]
    observacoes: Observacao = None

    _itens = field_validator("itens")(_sem_produto_repetido)


class ItemRecebimento(Esquema):
    item_id: int
    quantidade: Annotated[int, Field(ge=0, le=100_000)]


class RecebimentoEntrada(Esquema):
    itens: Annotated[list[ItemRecebimento], Field(min_length=1)] | None = Field(
        None, description="Vazio = receber tudo o que falta"
    )


class ItemCompraSaida(Esquema):
    id: int
    produto_id: int
    sku: str
    produto: str
    quantidade: int
    quantidade_recebida: int
    pendente: int
    custo_unitario: Valor
    total: Valor

    @classmethod
    def de(cls, i: ItemPedidoCompra) -> "ItemCompraSaida":
        return cls(
            id=i.id,
            produto_id=i.produto_id,
            sku=i.produto.sku,
            produto=i.produto.nome,
            quantidade=i.quantidade,
            quantidade_recebida=i.quantidade_recebida,
            pendente=i.pendente,
            custo_unitario=i.custo_unitario,
            total=i.custo_unitario * i.quantidade,
        )


class CompraSaida(Esquema):
    id: int
    numero: str | None
    status: StatusCompra
    fornecedor_id: int
    fornecedor: str
    deposito_id: int
    deposito: str
    previsao_entrega: date | None
    total: Valor
    observacoes: str | None
    criado_por: str | None
    criado_em: datetime
    enviado_em: datetime | None
    recebido_em: datetime | None
    percentual_recebido: float
    itens: list[ItemCompraSaida]

    @classmethod
    def de(cls, c: PedidoCompra) -> "CompraSaida":
        pedida = sum(i.quantidade for i in c.itens) or 1
        recebida = sum(i.quantidade_recebida for i in c.itens)
        return cls(
            id=c.id,
            numero=c.numero,
            status=c.status,
            fornecedor_id=c.fornecedor_id,
            fornecedor=c.fornecedor.nome_fantasia or c.fornecedor.razao_social,
            deposito_id=c.deposito_id,
            deposito=c.deposito.codigo,
            previsao_entrega=c.previsao_entrega,
            total=c.total,
            observacoes=c.observacoes,
            criado_por=c.criado_por.nome if c.criado_por else None,
            criado_em=c.criado_em,
            enviado_em=c.enviado_em,
            recebido_em=c.recebido_em,
            percentual_recebido=round(recebida / pedida * 100, 1),
            itens=[ItemCompraSaida.de(i) for i in c.itens],
        )
