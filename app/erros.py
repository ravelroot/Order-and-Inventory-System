import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.erros")


class ErroNegocio(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    codigo = "erro_negocio"

    def __init__(self, mensagem: str, detalhes: Any = None, codigo: str | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes
        if codigo:
            self.codigo = codigo


class NaoEncontrado(ErroNegocio):
    status_code = status.HTTP_404_NOT_FOUND
    codigo = "nao_encontrado"


class Conflito(ErroNegocio):
    status_code = status.HTTP_409_CONFLICT
    codigo = "conflito"


class RegraViolada(ErroNegocio):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    codigo = "regra_violada"


class EstoqueInsuficiente(Conflito):
    codigo = "estoque_insuficiente"


class TransicaoInvalida(Conflito):
    codigo = "transicao_invalida"


class NaoAutenticado(ErroNegocio):
    status_code = status.HTTP_401_UNAUTHORIZED
    codigo = "nao_autenticado"


class SemPermissao(ErroNegocio):
    status_code = status.HTTP_403_FORBIDDEN
    codigo = "sem_permissao"


class MuitasTentativas(ErroNegocio):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    codigo = "muitas_tentativas"

    def __init__(self, mensagem: str, segundos: int):
        super().__init__(mensagem, {"tentar_novamente_em": segundos})
        self.segundos = segundos


def _corpo(codigo: str, mensagem: str, detalhes: Any = None) -> dict:
    erro: dict[str, Any] = {"codigo": codigo, "mensagem": mensagem}
    if detalhes is not None:
        erro["detalhes"] = detalhes
    return {"erro": erro}


_MENSAGENS_HTTP = {
    404: "Recurso não encontrado.",
    405: "Método não permitido.",
    401: "Autenticação necessária.",
    403: "Acesso negado.",
}


_TRADUCOES = {
    "missing": "Campo obrigatório.",
    "string_too_short": "Precisa ter pelo menos {min_length} caractere(s).",
    "string_too_long": "Pode ter no máximo {max_length} caracteres.",
    "string_pattern_mismatch": "Formato inválido.",
    "string_type": "Precisa ser um texto.",
    "int_parsing": "Precisa ser um número inteiro.",
    "int_type": "Precisa ser um número inteiro.",
    "decimal_parsing": "Precisa ser um número.",
    "float_parsing": "Precisa ser um número.",
    "greater_than": "Precisa ser maior que {gt}.",
    "greater_than_equal": "Precisa ser maior ou igual a {ge}.",
    "less_than_equal": "Precisa ser menor ou igual a {le}.",
    "decimal_max_places": "Use no máximo {decimal_places} casas decimais.",
    "too_short": "Informe pelo menos {min_length} item(ns).",
    "too_long": "Informe no máximo {max_length} item(ns).",
    "enum": "Valor inválido. Use: {expected}.",
    "literal_error": "Valor inválido. Use: {expected}.",
    "bool_parsing": "Precisa ser verdadeiro ou falso.",
    "date_from_datetime_parsing": "Data inválida (use AAAA-MM-DD).",
    "date_parsing": "Data inválida (use AAAA-MM-DD).",
    "json_invalid": "JSON inválido.",
    "model_attributes_type": "Formato do corpo inválido.",
    "dict_type": "Formato do corpo inválido.",
}


def _mensagem_validacao(erro: dict) -> str:
    tipo = erro.get("type", "")
    if tipo == "value_error":
        mensagem = str(erro.get("msg", ""))
        if "email address" in mensagem:
            return "E-mail inválido."
        return mensagem.removeprefix("Value error, ")
    modelo = _TRADUCOES.get(tipo)
    if not modelo:
        return erro.get("msg", "Valor inválido.")
    try:
        return modelo.format(**(erro.get("ctx") or {}))
    except (KeyError, IndexError):
        return modelo


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(ErroNegocio)
    async def _negocio(_: Request, exc: ErroNegocio):
        cabecalhos = {}
        if isinstance(exc, MuitasTentativas):
            cabecalhos["Retry-After"] = str(exc.segundos)
        if isinstance(exc, NaoAutenticado):
            cabecalhos["WWW-Authenticate"] = "Bearer"
        return JSONResponse(_corpo(exc.codigo, exc.mensagem, exc.detalhes), exc.status_code, headers=cabecalhos)

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError):
        detalhes = [
            {
                "campo": ".".join(str(p) for p in erro["loc"] if p not in ("body", "query", "path")),
                "mensagem": _mensagem_validacao(erro),
            }
            for erro in exc.errors()
        ]
        return JSONResponse(_corpo("validacao", "Dados inválidos.", detalhes), status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        mensagem = exc.detail if isinstance(exc.detail, str) else _MENSAGENS_HTTP.get(exc.status_code, "Erro.")
        return JSONResponse(_corpo(f"http_{exc.status_code}", mensagem), exc.status_code, headers=exc.headers)

    @app.exception_handler(IntegrityError)
    async def _integridade(_: Request, exc: IntegrityError):
        log.info("Violação de integridade: %s", exc.orig)
        return JSONResponse(
            _corpo("integridade", "A operação viola uma regra de integridade (registro duplicado ou em uso)."),
            status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(StaleDataError)
    async def _concorrencia(_: Request, exc: StaleDataError):
        return JSONResponse(
            _corpo("concorrencia", "O registro foi alterado por outra pessoa. Recarregue e tente de novo."),
            status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(OperationalError)
    async def _banco(_: Request, exc: OperationalError):
        log.error("Banco indisponível: %s", exc.orig)
        return JSONResponse(_corpo("banco_indisponivel", "Banco de dados indisponível."), status.HTTP_503_SERVICE_UNAVAILABLE)

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, exc: Exception):
        log.exception("Erro inesperado")
        return JSONResponse(_corpo("erro_interno", "Erro interno."), status.HTTP_500_INTERNAL_SERVER_ERROR)
