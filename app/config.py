import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"
PASTA_WEB = RAIZ / "web"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nome_app: str = "Sistema de Pedidos e Estoque"
    versao: str = "1.0.0"
    ambiente: Literal["dev", "teste", "producao"] = "dev"

    database_url: str = f"sqlite:///{(PASTA_DADOS / 'estoque.db').as_posix()}"
    criar_tabelas: bool = True

    chave_secreta: str = ""
    token_minutos: int = 30
    cookie_seguro: bool = False

    admin_usuario: str = "admin"
    admin_senha: str = ""
    senha_demo: str = ""

    login_max_tentativas: int = 5
    login_janela_segundos: int = 600
    login_bloqueio_segundos: int = 300
    limite_requisicoes_minuto: int = 300

    docs_publicas: bool = True
    cors_origens: list[str] = []

    @field_validator("database_url")
    @classmethod
    def normalizar_url(cls, valor: str) -> str:
        if valor.startswith("postgres://"):
            valor = "postgresql://" + valor[len("postgres://") :]
        if valor.startswith("postgresql://"):
            valor = "postgresql+psycopg://" + valor[len("postgresql://") :]
        return valor

    @field_validator("admin_usuario")
    @classmethod
    def usuario_padrao(cls, valor: str) -> str:
        return valor.strip().lower() or "admin"

    @model_validator(mode="after")
    def validar_producao(self) -> "Config":
        if self.ambiente == "producao":
            if len(self.chave_secreta) < 32:
                raise ValueError("Em produção, CHAVE_SECRETA precisa ter pelo menos 32 caracteres.")
            if not self.cookie_seguro:
                raise ValueError("Em produção, COOKIE_SEGURO precisa ser true (HTTPS).")
        return self

    @property
    def eh_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def chave(self) -> str:
        if self.chave_secreta:
            return self.chave_secreta
        return _chave_local()


@lru_cache
def _chave_local() -> str:
    arquivo = PASTA_DADOS / ".chave_secreta"
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    if arquivo.exists():
        return arquivo.read_text(encoding="utf-8").strip()
    chave = secrets.token_urlsafe(48)
    arquivo.write_text(chave, encoding="utf-8")
    return chave


@lru_cache
def obter_config() -> Config:
    return Config()
