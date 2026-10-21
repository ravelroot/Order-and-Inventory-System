import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

import jwt

from app.config import obter_config
from app.database import agora_utc
from app.erros import MuitasTentativas, NaoAutenticado

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_ALGORITMO_JWT = "HS256"


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def gerar_hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    chave = hashlib.scrypt(senha.encode(), salt=sal, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(sal)}${_b64(chave)}"


def verificar_senha(senha: str, hash_salvo: str) -> bool:
    try:
        algoritmo, n, r, p, sal, chave = hash_salvo.split("$")
        if algoritmo != "scrypt":
            return False
        calculada = hashlib.scrypt(senha.encode(), salt=_de_b64(sal), n=int(n), r=int(r), p=int(p), dklen=len(_de_b64(chave)))
        return hmac.compare_digest(calculada, _de_b64(chave))
    except (ValueError, TypeError):
        return False


_HASH_FALSO = gerar_hash_senha(secrets.token_urlsafe(16))


def gastar_tempo_como_verificacao() -> None:
    verificar_senha("senha-inexistente", _HASH_FALSO)


def validar_forca_senha(senha: str, usuario: str | None = None) -> list[str]:
    problemas = []
    if len(senha) < 10:
        problemas.append("ter pelo menos 10 caracteres")
    if not any(c.isalpha() for c in senha) or not any(c.isdigit() for c in senha):
        problemas.append("misturar letras e números")
    if usuario and usuario.lower() in senha.lower():
        problemas.append("não conter o nome de usuário")
    return problemas


def gerar_senha_aleatoria() -> str:
    alfabeto = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    while True:
        grupos = ["".join(secrets.choice(alfabeto) for _ in range(4)) for _ in range(3)]
        senha = "-".join(grupos)
        if any(c.isdigit() for c in senha) and any(c.isalpha() for c in senha):
            return senha


def criar_token(usuario_id: int, papel: str, versao_token: int) -> tuple[str, int]:
    config = obter_config()
    agora = agora_utc()
    expira = agora + timedelta(minutes=config.token_minutos)
    carga = {
        "sub": str(usuario_id),
        "papel": papel,
        "ver": versao_token,
        "iat": int(agora.timestamp()),
        "exp": int(expira.timestamp()),
        "jti": secrets.token_urlsafe(12),
        "iss": "sistema-pedidos-estoque",
    }
    return jwt.encode(carga, config.chave(), algorithm=_ALGORITMO_JWT), config.token_minutos * 60


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            obter_config().chave(),
            algorithms=[_ALGORITMO_JWT],
            issuer="sistema-pedidos-estoque",
            options={"require": ["sub", "exp", "iat", "ver"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise NaoAutenticado("Sessão expirada. Entre novamente.", codigo="sessao_expirada") from exc
    except jwt.InvalidTokenError as exc:
        raise NaoAutenticado("Token inválido.") from exc


def hash_origem(ip: str | None) -> str | None:
    if not ip:
        return None
    return hmac.new(obter_config().chave().encode(), ip.encode(), hashlib.sha256).hexdigest()[:16]


class LimitadorLogin:
    def __init__(self):
        self._falhas: dict[str, deque[float]] = defaultdict(deque)
        self._bloqueado_ate: dict[str, float] = {}
        self._trava = threading.Lock()

    def _chaves(self, origem: str | None, usuario: str) -> list[str]:
        return [f"o:{origem or '-'}", f"u:{usuario.lower()}"]

    def verificar(self, origem: str | None, usuario: str) -> None:
        agora = time.monotonic()
        with self._trava:
            for chave in self._chaves(origem, usuario):
                ate = self._bloqueado_ate.get(chave, 0)
                if ate > agora:
                    segundos = int(ate - agora) + 1
                    raise MuitasTentativas(f"Muitas tentativas. Tente novamente em {segundos} segundos.", segundos)

    def falhou(self, origem: str | None, usuario: str) -> None:
        config = obter_config()
        agora = time.monotonic()
        with self._trava:
            for chave in self._chaves(origem, usuario):
                fila = self._falhas[chave]
                fila.append(agora)
                while fila and fila[0] < agora - config.login_janela_segundos:
                    fila.popleft()
                if len(fila) >= config.login_max_tentativas:
                    self._bloqueado_ate[chave] = agora + config.login_bloqueio_segundos
                    fila.clear()

    def sucesso(self, origem: str | None, usuario: str) -> None:
        with self._trava:
            for chave in self._chaves(origem, usuario):
                self._falhas.pop(chave, None)
                self._bloqueado_ate.pop(chave, None)

    def limpar(self) -> None:
        with self._trava:
            self._falhas.clear()
            self._bloqueado_ate.clear()


limitador_login = LimitadorLogin()
