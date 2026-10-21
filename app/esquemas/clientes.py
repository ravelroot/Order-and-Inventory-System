from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import EmailStr, StringConstraints, field_validator, model_validator

from app.esquemas.comum import UF, Esquema, Valor, ValorEntrada
from app.modelos import Cliente
from app.modelos.enums import TipoPessoa
from app.utils.documentos import cnpj_valido, cpf_valido, formatar_documento, mascarar_documento, so_digitos

Curto = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=80)]


class ClienteEntrada(Esquema):
    tipo_pessoa: TipoPessoa
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    documento: str
    email: EmailStr | None = None
    telefone: Annotated[str | None, StringConstraints(max_length=20)] = None
    cep: str | None = None
    logradouro: Annotated[str | None, StringConstraints(max_length=160)] = None
    numero: Annotated[str | None, StringConstraints(max_length=10)] = None
    complemento: Annotated[str | None, StringConstraints(max_length=60)] = None
    bairro: Curto = None
    cidade: Curto = None
    uf: UF | None = None
    limite_credito: ValorEntrada = Decimal("0")
    ativo: bool = True

    @field_validator("cep")
    @classmethod
    def _cep(cls, valor: str | None) -> str | None:
        if not valor:
            return None
        digitos = so_digitos(valor)
        if len(digitos) != 8:
            raise ValueError("CEP precisa ter 8 dígitos")
        return digitos

    @field_validator("telefone")
    @classmethod
    def _telefone(cls, valor: str | None) -> str | None:
        if not valor:
            return None
        digitos = so_digitos(valor)
        if len(digitos) not in (10, 11):
            raise ValueError("Telefone precisa ter DDD + número (10 ou 11 dígitos)")
        return digitos

    @model_validator(mode="after")
    def _documento(self):
        digitos = so_digitos(self.documento)
        if self.tipo_pessoa == TipoPessoa.FISICA and not cpf_valido(digitos):
            raise ValueError("CPF inválido")
        if self.tipo_pessoa == TipoPessoa.JURIDICA and not cnpj_valido(digitos):
            raise ValueError("CNPJ inválido")
        self.documento = digitos
        return self


class ClienteSaida(Esquema):
    id: int
    tipo_pessoa: TipoPessoa
    nome: str
    documento: str
    email: str | None
    telefone: str | None
    cep: str | None
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    cidade: str | None
    uf: str | None
    limite_credito: Valor
    ativo: bool
    criado_em: datetime

    @classmethod
    def de(cls, c: Cliente, mascarar: bool) -> "ClienteSaida":
        saida = cls.model_validate(c)
        saida.documento = mascarar_documento(c.documento) if mascarar else formatar_documento(c.documento)
        return saida


class ClienteResumo(Esquema):
    id: int
    nome: str
    cidade: str | None
    uf: str | None
