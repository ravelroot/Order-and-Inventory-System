from fastapi import APIRouter, Request, Response, status
from sqlalchemy import func, select

from app.config import obter_config
from app.database import agora_utc
from app.dependencias import NOME_COOKIE, Sessao, UsuarioAtual, origem_da_requisicao
from app.erros import NaoAutenticado, RegraViolada
from app.esquemas.comum import Mensagem
from app.esquemas.usuarios import LoginEntrada, TokenSaida, TrocarSenhaEntrada, UsuarioSaida
from app.modelos import Usuario
from app.seguranca import (
    criar_token,
    gastar_tempo_como_verificacao,
    gerar_hash_senha,
    limitador_login,
    validar_forca_senha,
    verificar_senha,
)
from app.servicos import auditoria

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _gravar_cookie(resposta: Response, token: str, segundos: int) -> None:
    resposta.set_cookie(
        NOME_COOKIE,
        token,
        max_age=segundos,
        httponly=True,
        secure=obter_config().cookie_seguro,
        samesite="strict",
        path="/",
    )


@router.post("/login", response_model=TokenSaida, summary="Entrar (cookie para o painel + token Bearer para a API)")
def login(dados: LoginEntrada, request: Request, resposta: Response, sessao: Sessao):
    origem = origem_da_requisicao(request)
    limitador_login.verificar(origem, dados.usuario)
    usuario = sessao.scalars(select(Usuario).where(func.lower(Usuario.usuario) == dados.usuario.lower())).first()
    if usuario is None:
        gastar_tempo_como_verificacao()
    if usuario is None or not usuario.ativo or not verificar_senha(dados.senha, usuario.senha_hash):
        limitador_login.falhou(origem, dados.usuario)
        auditoria.registrar(sessao, usuario, "login_falhou", "usuario", usuario.id if usuario else None, origem=origem)
        sessao.commit()
        raise NaoAutenticado("Usuário ou senha incorretos.", codigo="credenciais_invalidas")

    limitador_login.sucesso(origem, dados.usuario)
    usuario.ultimo_acesso = agora_utc()
    auditoria.registrar(sessao, usuario, "login", "usuario", usuario.id, origem=origem)
    sessao.commit()
    token, segundos = criar_token(usuario.id, usuario.papel.value, usuario.versao_token)
    _gravar_cookie(resposta, token, segundos)
    return TokenSaida(access_token=token, expira_em_segundos=segundos, usuario=UsuarioSaida.model_validate(usuario))


@router.post("/logout", response_model=Mensagem, summary="Sair (apaga o cookie do painel)")
def logout(resposta: Response):
    resposta.delete_cookie(NOME_COOKIE, path="/", httponly=True, samesite="strict", secure=obter_config().cookie_seguro)
    return Mensagem(mensagem="Sessão encerrada.")


@router.post("/sair-de-todos", response_model=Mensagem, summary="Revogar todas as sessões deste usuário")
def sair_de_todos(usuario: UsuarioAtual, resposta: Response, sessao: Sessao):
    usuario.versao_token += 1
    auditoria.registrar(sessao, usuario, "sessoes_revogadas", "usuario", usuario.id)
    sessao.commit()
    resposta.delete_cookie(NOME_COOKIE, path="/")
    return Mensagem(mensagem="Todas as sessões foram encerradas.")


@router.get("/eu", response_model=UsuarioSaida, summary="Usuário da sessão atual")
def eu(usuario: UsuarioAtual):
    return usuario


@router.post("/trocar-senha", response_model=TokenSaida, status_code=status.HTTP_200_OK)
def trocar_senha(dados: TrocarSenhaEntrada, request: Request, usuario: UsuarioAtual, resposta: Response, sessao: Sessao):
    origem = origem_da_requisicao(request)
    limitador_login.verificar(origem, usuario.usuario)
    if not verificar_senha(dados.senha_atual, usuario.senha_hash):
        limitador_login.falhou(origem, usuario.usuario)
        raise RegraViolada("A senha atual não confere.", codigo="senha_atual_incorreta")
    problemas = validar_forca_senha(dados.nova_senha, usuario.usuario)
    if problemas:
        raise RegraViolada("A nova senha precisa " + ", ".join(problemas) + ".", problemas, codigo="senha_fraca")
    if verificar_senha(dados.nova_senha, usuario.senha_hash):
        raise RegraViolada("A nova senha precisa ser diferente da atual.", codigo="senha_repetida")
    usuario.senha_hash = gerar_hash_senha(dados.nova_senha)
    usuario.trocar_senha = False
    usuario.versao_token += 1
    auditoria.registrar(sessao, usuario, "senha_trocada", "usuario", usuario.id, origem=origem)
    sessao.commit()
    token, segundos = criar_token(usuario.id, usuario.papel.value, usuario.versao_token)
    _gravar_cookie(resposta, token, segundos)
    return TokenSaida(access_token=token, expira_em_segundos=segundos, usuario=UsuarioSaida.model_validate(usuario))
