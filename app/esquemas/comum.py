import math
import re
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

T = TypeVar("T")

Valor = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
ValorEntrada = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Texto = Annotated[str, StringConstraints(strip_whitespace=True)]


def codigo_maiusculo(padrao: str, descricao: str):
    regex = re.compile(padrao)

    def _validar(valor: str) -> str:
        if not regex.fullmatch(valor):
            raise ValueError(descricao)
        return valor

    return Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True), AfterValidator(_validar)]


UF = codigo_maiusculo(r"[A-Z]{2}", "UF precisa ter 2 letras")


class Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class Pagina(BaseModel, Generic[T]):
    itens: list[T]
    total: int
    pagina: int
    por_pagina: int
    paginas: int

    @classmethod
    def montar(cls, itens: list, total: int, pagina: int, por_pagina: int) -> "Pagina[T]":
        return cls(
            itens=itens,
            total=total,
            pagina=pagina,
            por_pagina=por_pagina,
            paginas=max(1, math.ceil(total / por_pagina)) if por_pagina else 1,
        )


class Mensagem(BaseModel):
    mensagem: str
