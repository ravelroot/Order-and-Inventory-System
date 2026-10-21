from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import or_, select

from app.dependencias import Admin, Sessao
from app.erros import Conflito, NaoEncontrado, RegraViolada
from app.esquemas.comum import Pagina
from app.esquemas.usuarios import UsuarioAtualizar, UsuarioCriado, UsuarioCriar, UsuarioSaida
from app.modelos import Usuario
from app.modelos.enums import Papel
from app.seguranca import gerar_hash_senha, gerar_senha_aleatoria, validar_forca_senha
from app.servicos import auditoria
from app.utils.paginacao import ParametrosPagina, paginar, termo_like

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


def _obter(sessao, usuario_id: int) -> Usuario:
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise NaoEncontrado("Usuário não encontrado.")
    return usuario


def _restam_admins(sessao, exceto: int) -> bool:
    return (
        sessao.scalars(
            select(Usuario.id).where(Usuario.papel == Papel.ADMIN, Usuario.ativo.is_(True), Usuario.id != exceto)
        ).first()
        is not None
    )


@router.get("", response_model=Pagina[UsuarioSaida])
def listar(
    _: Admin,
    sessao: Sessao,
    pag: ParametrosPagina,
    q: Annotated[str | None, Query(max_length=60)] = None,
    papel: Papel | None = None,
    ativo: bool | None = None,
):
    consulta = select(Usuario).order_by(Usuario.nome)
    if q:
        termo = termo_like(q)
        consulta = consulta.where(or_(Usuario.nome.ilike(termo, escape="\\"), Usuario.usuario.ilike(termo, escape="\\")))
    if papel:
        consulta = consulta.where(Usuario.papel == papel)
    if ativo is not None:
        consulta = consulta.where(Usuario.ativo.is_(ativo))
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar(itens, total, pag.pagina, pag.por_pagina)


@router.post("", response_model=UsuarioCriado, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, admin: Admin, sessao: Sessao):
    if sessao.scalars(select(Usuario.id).where(Usuario.usuario == dados.usuario)).first():
        raise Conflito("Já existe um usuário com esse login.")
    senha = dados.senha or gerar_senha_aleatoria()
    if dados.senha:
        problemas = validar_forca_senha(dados.senha, dados.usuario)
        if problemas:
            raise RegraViolada("A senha precisa " + ", ".join(problemas) + ".", problemas)
    usuario = Usuario(
        nome=dados.nome,
        usuario=dados.usuario,
        email=dados.email,
        papel=dados.papel,
        senha_hash=gerar_hash_senha(senha),
        trocar_senha=True,
    )
    sessao.add(usuario)
    sessao.flush()
    auditoria.registrar(
        sessao, admin, "usuario_criado", "usuario", usuario.id, {"usuario": usuario.usuario, "papel": usuario.papel}
    )
    sessao.commit()
    return UsuarioCriado(usuario=UsuarioSaida.model_validate(usuario), senha_inicial=None if dados.senha else senha)


@router.patch("/{usuario_id}", response_model=UsuarioSaida)
def atualizar(usuario_id: int, dados: UsuarioAtualizar, admin: Admin, sessao: Sessao):
    usuario = _obter(sessao, usuario_id)
    campos = dados.model_dump(exclude_unset=True)
    perde_admin = usuario.papel == Papel.ADMIN and (
        campos.get("ativo") is False or ("papel" in campos and campos["papel"] != Papel.ADMIN)
    )
    if perde_admin and not _restam_admins(sessao, usuario.id):
        raise RegraViolada("É preciso manter pelo menos um administrador ativo.")
    antes = {c: getattr(usuario, c) for c in campos}
    for campo, valor in campos.items():
        if valor is not None or campo == "email":
            setattr(usuario, campo, valor)
    if campos.get("ativo") is False or "papel" in campos:
        usuario.versao_token += 1
    auditoria.registrar(sessao, admin, "usuario_alterado", "usuario", usuario.id, auditoria.diferencas(antes, campos))
    sessao.commit()
    return usuario


@router.post("/{usuario_id}/redefinir-senha", response_model=UsuarioCriado)
def redefinir_senha(usuario_id: int, admin: Admin, sessao: Sessao):
    usuario = _obter(sessao, usuario_id)
    senha = gerar_senha_aleatoria()
    usuario.senha_hash = gerar_hash_senha(senha)
    usuario.trocar_senha = True
    usuario.versao_token += 1
    auditoria.registrar(sessao, admin, "senha_redefinida", "usuario", usuario.id)
    sessao.commit()
    return UsuarioCriado(usuario=UsuarioSaida.model_validate(usuario), senha_inicial=senha)
