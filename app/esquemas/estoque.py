from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.esquemas.comum import UF, Esquema, Valor, ValorEntrada, codigo_maiusculo
from app.modelos import MovimentacaoEstoque, SaldoEstoque
from app.modelos.enums import OrigemMovimentacao, TipoMovimentacao

Motivo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]
Quantidade = Annotated[int, Field(gt=0, le=1_000_000)]


class DepositoEntrada(Esquema):
    codigo: codigo_maiusculo(r"[A-Z0-9-]{2,12}", "Código: 2 a 12 letras, números ou hífen")
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    cidade: Annotated[str | None, StringConstraints(max_length=80)] = None
    uf: UF | None = None
    ativo: bool = True


class DepositoSaida(Esquema):
    id: int
    codigo: str
    nome: str
    cidade: str | None
    uf: str | None
    ativo: bool


class SaldoSaida(Esquema):
    produto_id: int
    sku: str
    produto: str
    deposito_id: int
    deposito: str
    quantidade: int
    reservado: int
    disponivel: int
    estoque_minimo: int
    abaixo_minimo: bool
    custo_medio: Valor
    valor_estoque: Valor

    @classmethod
    def de(cls, s: SaldoEstoque) -> "SaldoSaida":
        return cls(
            produto_id=s.produto_id,
            sku=s.produto.sku,
            produto=s.produto.nome,
            deposito_id=s.deposito_id,
            deposito=s.deposito.codigo,
            quantidade=s.quantidade,
            reservado=s.reservado,
            disponivel=s.disponivel,
            estoque_minimo=s.produto.estoque_minimo,
            abaixo_minimo=s.disponivel < s.produto.estoque_minimo,
            custo_medio=s.produto.custo_medio,
            valor_estoque=s.produto.custo_medio * s.quantidade,
        )


class EntradaEstoque(Esquema):
    produto_id: int
    deposito_id: int
    quantidade: Quantidade
    custo_unitario: ValorEntrada | None = None
    motivo: Motivo = "Entrada manual"


class AjusteEstoque(Esquema):
    produto_id: int
    deposito_id: int
    quantidade_contada: Annotated[int, Field(ge=0, le=1_000_000)]
    motivo: Motivo


class TransferenciaEstoque(Esquema):
    produto_id: int
    deposito_origem_id: int
    deposito_destino_id: int
    quantidade: Quantidade
    motivo: Motivo = "Transferência entre depósitos"

    @model_validator(mode="after")
    def _depositos_diferentes(self):
        if self.deposito_origem_id == self.deposito_destino_id:
            raise ValueError("Origem e destino precisam ser depósitos diferentes")
        return self


class MovimentacaoSaida(Esquema):
    id: int
    produto_id: int
    sku: str
    produto: str
    deposito: str
    tipo: TipoMovimentacao
    quantidade: int
    saldo_apos: int
    reservado_apos: int
    custo_unitario: Valor | None
    origem: OrigemMovimentacao
    origem_id: int | None
    motivo: str | None
    usuario: str | None
    criado_em: datetime

    @classmethod
    def de(cls, m: MovimentacaoEstoque) -> "MovimentacaoSaida":
        return cls(
            id=m.id,
            produto_id=m.produto_id,
            sku=m.produto.sku,
            produto=m.produto.nome,
            deposito=m.deposito.codigo,
            tipo=m.tipo,
            quantidade=m.quantidade,
            saldo_apos=m.saldo_apos,
            reservado_apos=m.reservado_apos,
            custo_unitario=m.custo_unitario,
            origem=m.origem,
            origem_id=m.origem_id,
            motivo=m.motivo,
            usuario=m.usuario.usuario if m.usuario else None,
            criado_em=m.criado_em,
        )
