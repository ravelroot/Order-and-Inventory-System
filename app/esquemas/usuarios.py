from datetime import datetime
from typing import Annotated

from pydantic import EmailStr, Field, StringConstraints

from app.esquemas.comum import Esquema
from app.modelos.enums import Papel

NomeUsuario = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9._-]{3,40}$")]


class LoginEntrada(Esquema):
    usuario: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    senha: Annotated[str, Field(min_length=1, max_length=128)]


class UsuarioSaida(Esquema):
    id: int
    nome: str
    usuario: str
    email: str | None
    papel: Papel
    ativo: bool
    trocar_senha: bool
    ultimo_acesso: datetime | None
    criado_em: datetime


class TokenSaida(Esquema):
    access_token: str
    token_type: str = "bearer"
    expira_em_segundos: int
    usuario: UsuarioSaida


class TrocarSenhaEntrada(Esquema):
    senha_atual: Annotated[str, Field(min_length=1, max_length=128)]
    nova_senha: Annotated[str, Field(min_length=10, max_length=128)]


class UsuarioCriar(Esquema):
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    usuario: NomeUsuario
    email: EmailStr | None = None
    papel: Papel = Papel.VENDEDOR
    senha: Annotated[str | None, Field(min_length=10, max_length=128)] = None


class UsuarioAtualizar(Esquema):
    nome: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)] = None
    email: EmailStr | None = None
    papel: Papel | None = None
    ativo: bool | None = None


class UsuarioCriado(Esquema):
    usuario: UsuarioSaida
    senha_inicial: str | None = None
