from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, DataHoraUTC, DecimalFixo, Dinheiro, agora_utc
from app.modelos.enums import (
    OrigemMovimentacao,
    Papel,
    StatusCompra,
    StatusPedido,
    TipoMovimentacao,
    TipoPessoa,
    Unidade,
)


def _enum(tipo, nome: str):
    return SAEnum(
        tipo,
        name=nome,
        native_enum=False,
        length=24,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


class CriadoAtualizado:
    criado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc, onupdate=agora_utc, nullable=False)


class Usuario(CriadoAtualizado, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    usuario: Mapped[str] = mapped_column(String(40), unique=True)
    email: Mapped[str | None] = mapped_column(String(160), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[Papel] = mapped_column(_enum(Papel, "papel"), default=Papel.VENDEDOR)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    versao_token: Mapped[int] = mapped_column(Integer, default=1)
    trocar_senha: Mapped[bool] = mapped_column(Boolean, default=False)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DataHoraUTC)


class Categoria(CriadoAtualizado, Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    descricao: Mapped[str | None] = mapped_column(String(255))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Fornecedor(CriadoAtualizado, Base):
    __tablename__ = "fornecedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    razao_social: Mapped[str] = mapped_column(String(160))
    nome_fantasia: Mapped[str | None] = mapped_column(String(120))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    email: Mapped[str | None] = mapped_column(String(160))
    telefone: Mapped[str | None] = mapped_column(String(20))
    cidade: Mapped[str | None] = mapped_column(String(80))
    uf: Mapped[str | None] = mapped_column(String(2))
    prazo_entrega_dias: Mapped[int] = mapped_column(Integer, default=7)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Produto(CriadoAtualizado, Base):
    __tablename__ = "produto"
    __table_args__ = (
        CheckConstraint("preco_venda >= 0", name="preco_nao_negativo"),
        CheckConstraint("custo_medio >= 0", name="custo_nao_negativo"),
        CheckConstraint("estoque_minimo >= 0", name="minimo_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(30), unique=True)
    codigo_barras: Mapped[str | None] = mapped_column(String(14), unique=True)
    nome: Mapped[str] = mapped_column(String(160), index=True)
    descricao: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id", ondelete="RESTRICT"))
    fornecedor_id: Mapped[int | None] = mapped_column(ForeignKey("fornecedor.id", ondelete="SET NULL"))
    unidade: Mapped[Unidade] = mapped_column(_enum(Unidade, "unidade"), default=Unidade.UN)
    preco_venda: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    custo_medio: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    estoque_minimo: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    versao: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    categoria: Mapped[Categoria] = relationship(lazy="joined")
    fornecedor: Mapped[Fornecedor | None] = relationship(lazy="joined")
    saldos: Mapped[list["SaldoEstoque"]] = relationship(back_populates="produto", lazy="selectin")

    __mapper_args__ = {"version_id_col": versao}


class Deposito(CriadoAtualizado, Base):
    __tablename__ = "deposito"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    cidade: Mapped[str | None] = mapped_column(String(80))
    uf: Mapped[str | None] = mapped_column(String(2))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class SaldoEstoque(Base):
    __tablename__ = "saldo_estoque"
    __table_args__ = (
        CheckConstraint("quantidade >= 0", name="quantidade_nao_negativa"),
        CheckConstraint("reservado >= 0", name="reservado_nao_negativo"),
        CheckConstraint("reservado <= quantidade", name="reserva_ate_quantidade"),
    )

    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id", ondelete="CASCADE"), primary_key=True)
    deposito_id: Mapped[int] = mapped_column(ForeignKey("deposito.id", ondelete="RESTRICT"), primary_key=True)
    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    reservado: Mapped[int] = mapped_column(Integer, default=0)
    atualizado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc, onupdate=agora_utc)

    produto: Mapped[Produto] = relationship(back_populates="saldos")
    deposito: Mapped[Deposito] = relationship(lazy="joined")

    @property
    def disponivel(self) -> int:
        return self.quantidade - self.reservado


class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacao_estoque"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        Index("ix_movimentacao_produto_data", "produto_id", "criado_em"),
        Index("ix_movimentacao_origem", "origem", "origem_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id", ondelete="CASCADE"))
    deposito_id: Mapped[int] = mapped_column(ForeignKey("deposito.id", ondelete="RESTRICT"))
    tipo: Mapped[TipoMovimentacao] = mapped_column(_enum(TipoMovimentacao, "tipo_movimentacao"))
    quantidade: Mapped[int] = mapped_column(Integer)
    saldo_apos: Mapped[int] = mapped_column(Integer)
    reservado_apos: Mapped[int] = mapped_column(Integer, default=0)
    custo_unitario: Mapped[Decimal | None] = mapped_column(Dinheiro())
    origem: Mapped[OrigemMovimentacao] = mapped_column(_enum(OrigemMovimentacao, "origem_movimentacao"))
    origem_id: Mapped[int | None] = mapped_column(Integer)
    motivo: Mapped[str | None] = mapped_column(String(255))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc)

    produto: Mapped[Produto] = relationship(lazy="joined")
    deposito: Mapped[Deposito] = relationship(lazy="joined")
    usuario: Mapped[Usuario | None] = relationship(lazy="joined")


class Cliente(CriadoAtualizado, Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_pessoa: Mapped[TipoPessoa] = mapped_column(_enum(TipoPessoa, "tipo_pessoa"))
    nome: Mapped[str] = mapped_column(String(160), index=True)
    documento: Mapped[str] = mapped_column(String(14), unique=True)
    email: Mapped[str | None] = mapped_column(String(160))
    telefone: Mapped[str | None] = mapped_column(String(20))
    cep: Mapped[str | None] = mapped_column(String(8))
    logradouro: Mapped[str | None] = mapped_column(String(160))
    numero: Mapped[str | None] = mapped_column(String(10))
    complemento: Mapped[str | None] = mapped_column(String(60))
    bairro: Mapped[str | None] = mapped_column(String(80))
    cidade: Mapped[str | None] = mapped_column(String(80))
    uf: Mapped[str | None] = mapped_column(String(2))
    limite_credito: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class PedidoVenda(CriadoAtualizado, Base):
    __tablename__ = "pedido_venda"
    __table_args__ = (
        UniqueConstraint("vendedor_id", "chave_idempotencia", name="uq_pedido_venda_idempotencia"),
        Index("ix_pedido_venda_status_data", "status", "criado_em"),
        CheckConstraint("total >= 0", name="total_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str | None] = mapped_column(String(20), unique=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id", ondelete="RESTRICT"))
    deposito_id: Mapped[int] = mapped_column(ForeignKey("deposito.id", ondelete="RESTRICT"))
    vendedor_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    status: Mapped[StatusPedido] = mapped_column(_enum(StatusPedido, "status_pedido"), default=StatusPedido.RASCUNHO)
    subtotal: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    desconto_total: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    frete: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    observacoes: Mapped[str | None] = mapped_column(Text)
    codigo_rastreio: Mapped[str | None] = mapped_column(String(40))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    chave_idempotencia: Mapped[str | None] = mapped_column(String(80))
    confirmado_em: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    faturado_em: Mapped[datetime | None] = mapped_column(DataHoraUTC, index=True)
    enviado_em: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    entregue_em: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    cancelado_em: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    versao: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    deposito: Mapped[Deposito] = relationship(lazy="joined")
    vendedor: Mapped[Usuario | None] = relationship(lazy="joined")
    itens: Mapped[list["ItemPedidoVenda"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="ItemPedidoVenda.id", lazy="selectin"
    )
    historico: Mapped[list["HistoricoPedido"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="HistoricoPedido.id", lazy="selectin"
    )

    __mapper_args__ = {"version_id_col": versao}


class ItemPedidoVenda(Base):
    __tablename__ = "item_pedido_venda"
    __table_args__ = (
        UniqueConstraint("pedido_id", "produto_id", name="uq_item_pedido_produto"),
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        CheckConstraint("desconto_percentual >= 0 AND desconto_percentual <= 10000", name="desconto_valido"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido_venda.id", ondelete="CASCADE"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id", ondelete="RESTRICT"))
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario: Mapped[Decimal] = mapped_column(Dinheiro())
    desconto_percentual: Mapped[Decimal] = mapped_column(DecimalFixo(2), default=Decimal("0"))
    custo_unitario: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Dinheiro())

    pedido: Mapped[PedidoVenda] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship(lazy="joined")


class HistoricoPedido(Base):
    __tablename__ = "historico_pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido_venda.id", ondelete="CASCADE"), index=True)
    de_status: Mapped[StatusPedido | None] = mapped_column(_enum(StatusPedido, "status_pedido"))
    para_status: Mapped[StatusPedido] = mapped_column(_enum(StatusPedido, "status_pedido"))
    observacao: Mapped[str | None] = mapped_column(String(255))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc)

    pedido: Mapped[PedidoVenda] = relationship(back_populates="historico")
    usuario: Mapped[Usuario | None] = relationship(lazy="joined")


class PedidoCompra(CriadoAtualizado, Base):
    __tablename__ = "pedido_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str | None] = mapped_column(String(20), unique=True)
    fornecedor_id: Mapped[int] = mapped_column(ForeignKey("fornecedor.id", ondelete="RESTRICT"))
    deposito_id: Mapped[int] = mapped_column(ForeignKey("deposito.id", ondelete="RESTRICT"))
    status: Mapped[StatusCompra] = mapped_column(_enum(StatusCompra, "status_compra"), default=StatusCompra.RASCUNHO)
    previsao_entrega: Mapped[date | None] = mapped_column(Date)
    total: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal("0"))
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    enviado_em: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    recebido_em: Mapped[datetime | None] = mapped_column(DataHoraUTC)
    versao: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    fornecedor: Mapped[Fornecedor] = relationship(lazy="joined")
    deposito: Mapped[Deposito] = relationship(lazy="joined")
    criado_por: Mapped[Usuario | None] = relationship(lazy="joined")
    itens: Mapped[list["ItemPedidoCompra"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="ItemPedidoCompra.id", lazy="selectin"
    )

    __mapper_args__ = {"version_id_col": versao}


class ItemPedidoCompra(Base):
    __tablename__ = "item_pedido_compra"
    __table_args__ = (
        UniqueConstraint("pedido_id", "produto_id", name="uq_item_compra_produto"),
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        CheckConstraint("quantidade_recebida >= 0 AND quantidade_recebida <= quantidade", name="recebida_valida"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido_compra.id", ondelete="CASCADE"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id", ondelete="RESTRICT"))
    quantidade: Mapped[int] = mapped_column(Integer)
    quantidade_recebida: Mapped[int] = mapped_column(Integer, default=0)
    custo_unitario: Mapped[Decimal] = mapped_column(Dinheiro())

    pedido: Mapped[PedidoCompra] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship(lazy="joined")

    @property
    def pendente(self) -> int:
        return self.quantidade - self.quantidade_recebida


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (Index("ix_auditoria_entidade", "entidade", "entidade_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    acao: Mapped[str] = mapped_column(String(40), index=True)
    entidade: Mapped[str] = mapped_column(String(40))
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    detalhes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    origem_hash: Mapped[str | None] = mapped_column(String(16))
    criado_em: Mapped[datetime] = mapped_column(DataHoraUTC, default=agora_utc, index=True)

    usuario: Mapped[Usuario | None] = relationship(lazy="joined")


__all__ = [
    "Auditoria",
    "Categoria",
    "Cliente",
    "Deposito",
    "Fornecedor",
    "HistoricoPedido",
    "ItemPedidoCompra",
    "ItemPedidoVenda",
    "MovimentacaoEstoque",
    "PedidoCompra",
    "PedidoVenda",
    "Produto",
    "SaldoEstoque",
    "Usuario",
]
