from typing import Any

from sqlalchemy.orm import Session

from app.modelos import Auditoria, Usuario


def registrar(
    sessao: Session,
    usuario: Usuario | None,
    acao: str,
    entidade: str,
    entidade_id: int | None = None,
    detalhes: dict[str, Any] | None = None,
    origem: str | None = None,
) -> None:
    sessao.add(
        Auditoria(
            usuario_id=usuario.id if usuario else None,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhes=_serializavel(detalhes) if detalhes else None,
            origem_hash=origem,
        )
    )


def _serializavel(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {str(k): _serializavel(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_serializavel(v) for v in valor]
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return str(valor)


def diferencas(antes: dict[str, Any], depois: dict[str, Any]) -> dict[str, Any]:
    return {
        campo: {"de": _serializavel(antes.get(campo)), "para": _serializavel(valor)}
        for campo, valor in depois.items()
        if antes.get(campo) != valor
    }
