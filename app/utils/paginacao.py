from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


@dataclass
class Paginacao:
    pagina: int
    por_pagina: int

    @property
    def deslocamento(self) -> int:
        return (self.pagina - 1) * self.por_pagina


def _paginacao(
    pagina: Annotated[int, Query(ge=1, description="Página (começa em 1)")] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200, description="Itens por página")] = 20,
) -> Paginacao:
    return Paginacao(pagina, por_pagina)


ParametrosPagina = Annotated[Paginacao, Depends(_paginacao)]


def paginar(sessao: Session, consulta: Select, pag: Paginacao) -> tuple[list, int]:
    total = sessao.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
    itens = sessao.scalars(consulta.limit(pag.por_pagina).offset(pag.deslocamento)).unique().all()
    return list(itens), total


def ordenar(consulta: Select, campo: str | None, permitidos: dict, padrao: str) -> Select:
    chave = campo or padrao
    descendente = chave.startswith("-")
    coluna = permitidos.get(chave.lstrip("-")) or permitidos[padrao.lstrip("-")]
    return consulta.order_by(coluna.desc() if descendente else coluna.asc())


def termo_like(texto: str) -> str:
    escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"
