from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import EmailStr, Field, StringConstraints, field_validator

from app.esquemas.comum import UF, Esquema, Valor, ValorEntrada, codigo_maiusculo
from app.modelos import Produto
from app.modelos.enums import Unidade
from app.utils.documentos import cnpj_valido, ean13_valido, formatar_documento, so_digitos


def _validar_ean(valor: str | None) -> str | None:
    if not valor:
        return None
    if not ean13_valido(valor):
        raise ValueError("Código de barras EAN-13 inválido")
    return so_digitos(valor)


Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]


class CategoriaEntrada(Esquema):
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    descricao: Annotated[str | None, StringConstraints(max_length=255)] = None
    ativo: bool = True


class CategoriaSaida(Esquema):
    id: int
    nome: str
    descricao: str | None
    ativo: bool


class FornecedorEntrada(Esquema):
    razao_social: Nome
    nome_fantasia: Annotated[str | None, StringConstraints(max_length=120)] = None
    cnpj: str
    email: EmailStr | None = None
    telefone: Annotated[str | None, StringConstraints(max_length=20)] = None
    cidade: Annotated[str | None, StringConstraints(max_length=80)] = None
    uf: UF | None = None
    prazo_entrega_dias: Annotated[int, Field(ge=0, le=365)] = 7
    ativo: bool = True

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, valor: str) -> str:
        if not cnpj_valido(valor):
            raise ValueError("CNPJ inválido")
        return so_digitos(valor)


class FornecedorSaida(Esquema):
    id: int
    razao_social: str
    nome_fantasia: str | None
    cnpj: str
    cnpj_formatado: str = ""
    email: str | None
    telefone: str | None
    cidade: str | None
    uf: str | None
    prazo_entrega_dias: int
    ativo: bool

    def model_post_init(self, _):
        self.cnpj_formatado = formatar_documento(self.cnpj)


class ProdutoEntrada(Esquema):
    sku: codigo_maiusculo(r"[A-Z0-9-]{3,30}", "SKU: 3 a 30 letras, números ou hífen")
    nome: Nome
    descricao: str | None = None
    codigo_barras: str | None = None
    categoria_id: int
    fornecedor_id: int | None = None
    unidade: Unidade = Unidade.UN
    preco_venda: ValorEntrada
    estoque_minimo: Annotated[int, Field(ge=0)] = 0
    ativo: bool = True

    @field_validator("codigo_barras")
    @classmethod
    def _ean(cls, valor: str | None) -> str | None:
        return _validar_ean(valor)


class ProdutoAtualizar(Esquema):
    nome: Nome | None = None
    descricao: str | None = None
    codigo_barras: str | None = None
    categoria_id: int | None = None
    fornecedor_id: int | None = None
    unidade: Unidade | None = None
    preco_venda: ValorEntrada | None = None
    estoque_minimo: Annotated[int | None, Field(ge=0)] = None
    ativo: bool | None = None
    versao: int | None = Field(None, description="Versão lida; se informada, evita sobrescrever alterações de outra pessoa")

    @field_validator("codigo_barras")
    @classmethod
    def _ean(cls, valor: str | None) -> str | None:
        return _validar_ean(valor)


class ProdutoSaida(Esquema):
    id: int
    sku: str
    codigo_barras: str | None
    nome: str
    descricao: str | None
    categoria_id: int
    categoria: str
    fornecedor_id: int | None
    fornecedor: str | None
    unidade: Unidade
    preco_venda: Valor
    custo_medio: Valor
    margem_percentual: float | None
    estoque_minimo: int
    estoque_total: int
    reservado_total: int
    disponivel_total: int
    abaixo_minimo: bool
    ativo: bool
    versao: int
    atualizado_em: datetime

    @classmethod
    def de(cls, p: Produto) -> "ProdutoSaida":
        total = sum(s.quantidade for s in p.saldos)
        reservado = sum(s.reservado for s in p.saldos)
        margem = None
        if p.preco_venda and p.preco_venda > 0 and p.custo_medio:
            margem = float(round((p.preco_venda - p.custo_medio) / p.preco_venda * 100, 1))
        return cls(
            id=p.id,
            sku=p.sku,
            codigo_barras=p.codigo_barras,
            nome=p.nome,
            descricao=p.descricao,
            categoria_id=p.categoria_id,
            categoria=p.categoria.nome,
            fornecedor_id=p.fornecedor_id,
            fornecedor=(p.fornecedor.nome_fantasia or p.fornecedor.razao_social) if p.fornecedor else None,
            unidade=p.unidade,
            preco_venda=p.preco_venda,
            custo_medio=p.custo_medio or Decimal("0"),
            margem_percentual=margem,
            estoque_minimo=p.estoque_minimo,
            estoque_total=total,
            reservado_total=reservado,
            disponivel_total=total - reservado,
            abaixo_minimo=(total - reservado) < p.estoque_minimo,
            ativo=p.ativo,
            versao=p.versao,
            atualizado_em=p.atualizado_em,
        )
