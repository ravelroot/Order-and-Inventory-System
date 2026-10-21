from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import obter_sessao
from app.erros import NaoAutenticado, SemPermissao
from app.modelos import Usuario
from app.modelos.enums import Papel
from app.seguranca import decodificar_token, hash_origem

NOME_COOKIE = "spe_sessao"

Sessao = Annotated[Session, Depends(obter_sessao)]


def extrair_token(request: Request) -> str | None:
    cabecalho = request.headers.get("authorization", "")
    if cabecalho.lower().startswith("bearer "):
        return cabecalho[7:].strip() or None
    return request.cookies.get(NOME_COOKIE)


def origem_da_requisicao(request: Request) -> str | None:
    return hash_origem(request.client.host if request.client else None)


def obter_usuario_atual(request: Request, sessao: Sessao) -> Usuario:
    token = extrair_token(request)
    if not token:
        raise NaoAutenticado("Autenticação necessária.")
    carga = decodificar_token(token)
    usuario = sessao.get(Usuario, int(carga["sub"]))
    if usuario is None or not usuario.ativo or usuario.versao_token != carga["ver"]:
        raise NaoAutenticado("Sessão encerrada. Entre novamente.", codigo="sessao_revogada")
    request.state.usuario_id = usuario.id
    return usuario


UsuarioAtual = Annotated[Usuario, Depends(obter_usuario_atual)]


def exigir(*papeis: Papel) -> Callable[[Usuario], Usuario]:
    permitidos = {Papel.ADMIN, *papeis}

    def _verificar(usuario: UsuarioAtual) -> Usuario:
        if usuario.papel not in permitidos:
            raise SemPermissao("Seu perfil não tem permissão para esta ação.")
        return usuario

    return _verificar


Admin = Annotated[Usuario, Depends(exigir())]
Gestor = Annotated[Usuario, Depends(exigir(Papel.GERENTE))]
Comercial = Annotated[Usuario, Depends(exigir(Papel.GERENTE, Papel.VENDEDOR))]
Logistica = Annotated[Usuario, Depends(exigir(Papel.GERENTE, Papel.ESTOQUISTA))]
Operacao = Annotated[Usuario, Depends(exigir(Papel.GERENTE, Papel.VENDEDOR, Papel.ESTOQUISTA))]
