import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import obter_config
from app.seguranca import hash_origem

log = logging.getLogger("app.requisicoes")

CSP_PAINEL = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
CSP_DOCS = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; frame-ancestors 'none'"
)
METODOS_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}


class SegurancaMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._janelas: dict[str, deque[float]] = defaultdict(deque)
        self._trava = threading.Lock()

    def _excedeu_limite(self, chave: str) -> bool:
        limite = obter_config().limite_requisicoes_minuto
        if limite <= 0:
            return False
        agora = time.monotonic()
        with self._trava:
            janela = self._janelas[chave]
            while janela and janela[0] < agora - 60:
                janela.popleft()
            if len(janela) >= limite:
                return True
            janela.append(agora)
            return False

    @staticmethod
    def _origem_cruzada(request: Request) -> bool:
        if request.method not in METODOS_ESCRITA:
            return False
        if request.headers.get("authorization", "").lower().startswith("bearer "):
            return False
        if request.headers.get("sec-fetch-site") == "cross-site":
            return True
        origem = request.headers.get("origin")
        if not origem:
            return False
        return urlsplit(origem).netloc != request.headers.get("host", "")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        id_requisicao = secrets.token_hex(6)
        inicio = time.perf_counter()
        chave = hash_origem(request.client.host if request.client else None) or "-"

        if request.url.path.startswith("/api/") and self._excedeu_limite(chave):
            resposta: Response = JSONResponse(
                {"erro": {"codigo": "limite_requisicoes", "mensagem": "Muitas requisições. Aguarde um minuto."}},
                429,
                headers={"Retry-After": "60"},
            )
        elif self._origem_cruzada(request):
            resposta = JSONResponse(
                {"erro": {"codigo": "origem_cruzada", "mensagem": "Requisição de outra origem bloqueada."}}, 403
            )
        else:
            resposta = await call_next(request)

        caminho = request.url.path
        eh_docs = caminho in ("/docs", "/redoc") or caminho.startswith("/docs/")
        resposta.headers.setdefault("Content-Security-Policy", CSP_DOCS if eh_docs else CSP_PAINEL)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        resposta.headers.setdefault("Referrer-Policy", "no-referrer")
        resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        resposta.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resposta.headers["X-Request-ID"] = id_requisicao
        if caminho.startswith("/api/"):
            resposta.headers.setdefault("Cache-Control", "no-store")
        if obter_config().cookie_seguro:
            resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        duracao = (time.perf_counter() - inicio) * 1000
        log.info("%s %s %s %.1fms id=%s", request.method, caminho, resposta.status_code, duracao, id_requisicao)
        return resposta
