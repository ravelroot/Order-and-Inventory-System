from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, or_, select

from app.dependencias import Comercial, Operacao, Sessao, origem_da_requisicao
from app.erros import Conflito, NaoEncontrado
from app.esquemas.clientes import ClienteEntrada, ClienteSaida
from app.esquemas.comum import Pagina
from app.modelos import Cliente, PedidoVenda, Usuario
from app.modelos.enums import STATUS_FATURADOS, Papel, TipoPessoa
from app.servicos import auditoria
from app.utils.documentos import formatar_documento, so_digitos
from app.utils.paginacao import ParametrosPagina, ordenar, paginar, termo_like

router = APIRouter(prefix="/clientes", tags=["Clientes"])

ORDENACAO = {"nome": Cliente.nome, "cidade": Cliente.cidade, "criado": Cliente.criado_em}


def _ve_documento(usuario: Usuario) -> bool:
    return usuario.papel in (Papel.ADMIN, Papel.GERENTE)


def _obter(sessao, cliente_id: int) -> Cliente:
    cliente = sessao.get(Cliente, cliente_id)
    if cliente is None:
        raise NaoEncontrado("Cliente não encontrado.")
    return cliente


@router.get("", response_model=Pagina[ClienteSaida])
def listar(
    usuario: Operacao,
    sessao: Sessao,
    pag: ParametrosPagina,
    q: Annotated[str | None, Query(max_length=80, description="Nome, cidade ou documento")] = None,
    tipo_pessoa: TipoPessoa | None = None,
    uf: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    ativo: bool | None = None,
    ordem: str | None = None,
):
    consulta = select(Cliente)
    if q:
        termo = termo_like(q)
        filtros = [Cliente.nome.ilike(termo, escape="\\"), Cliente.cidade.ilike(termo, escape="\\")]
        digitos = so_digitos(q)
        if len(digitos) >= 4:
            filtros.append(Cliente.documento.like(f"%{digitos}%"))
        consulta = consulta.where(or_(*filtros))
    if tipo_pessoa:
        consulta = consulta.where(Cliente.tipo_pessoa == tipo_pessoa)
    if uf:
        consulta = consulta.where(Cliente.uf == uf.upper())
    if ativo is not None:
        consulta = consulta.where(Cliente.ativo.is_(ativo))
    consulta = ordenar(consulta, ordem, ORDENACAO, "nome").order_by(Cliente.id)
    itens, total = paginar(sessao, consulta, pag)
    mascarar = not _ve_documento(usuario)
    return Pagina.montar([ClienteSaida.de(c, mascarar) for c in itens], total, pag.pagina, pag.por_pagina)


@router.get("/{cliente_id}", response_model=ClienteSaida)
def obter(cliente_id: int, usuario: Operacao, sessao: Sessao):
    return ClienteSaida.de(_obter(sessao, cliente_id), not _ve_documento(usuario))


@router.get("/{cliente_id}/documento", summary="Revelar CPF/CNPJ completo (fica registrado na auditoria)")
def revelar_documento(cliente_id: int, request: Request, usuario: Comercial, sessao: Sessao):
    cliente = _obter(sessao, cliente_id)
    auditoria.registrar(sessao, usuario, "documento_revelado", "cliente", cliente.id, origem=origem_da_requisicao(request))
    sessao.commit()
    return {"documento": formatar_documento(cliente.documento)}


@router.get("/{cliente_id}/resumo", summary="Indicadores de compra do cliente")
def resumo(cliente_id: int, _: Operacao, sessao: Sessao):
    cliente = _obter(sessao, cliente_id)
    linha = sessao.execute(
        select(
            func.count(PedidoVenda.id),
            func.coalesce(func.sum(PedidoVenda.total), 0),
            func.max(PedidoVenda.faturado_em),
        ).where(PedidoVenda.cliente_id == cliente.id, PedidoVenda.status.in_(STATUS_FATURADOS))
    ).one()
    pedidos, total, ultimo = linha
    return {
        "cliente_id": cliente.id,
        "pedidos_faturados": pedidos,
        "total_comprado": float(total or 0),
        "ticket_medio": round(float(total or 0) / pedidos, 2) if pedidos else 0,
        "ultima_compra": ultimo,
    }


@router.post("", response_model=ClienteSaida, status_code=status.HTTP_201_CREATED)
def criar(dados: ClienteEntrada, usuario: Comercial, sessao: Sessao):
    if sessao.scalars(select(Cliente.id).where(Cliente.documento == dados.documento)).first():
        raise Conflito("Já existe um cliente com esse documento.")
    cliente = Cliente(**dados.model_dump())
    sessao.add(cliente)
    sessao.flush()
    auditoria.registrar(sessao, usuario, "cliente_criado", "cliente", cliente.id)
    sessao.commit()
    return ClienteSaida.de(cliente, not _ve_documento(usuario))


@router.put("/{cliente_id}", response_model=ClienteSaida)
def atualizar(cliente_id: int, dados: ClienteEntrada, usuario: Comercial, sessao: Sessao):
    cliente = _obter(sessao, cliente_id)
    if (
        dados.documento != cliente.documento
        and sessao.scalars(select(Cliente.id).where(Cliente.documento == dados.documento, Cliente.id != cliente.id)).first()
    ):
        raise Conflito("Já existe outro cliente com esse documento.")
    novos = dados.model_dump()
    antes = {c: getattr(cliente, c) for c in novos}
    for campo, valor in novos.items():
        setattr(cliente, campo, valor)
    mudancas = auditoria.diferencas(antes, novos)
    mudancas.pop("documento", None)
    auditoria.registrar(sessao, usuario, "cliente_alterado", "cliente", cliente.id, {"campos": sorted(mudancas)})
    sessao.commit()
    return ClienteSaida.de(cliente, not _ve_documento(usuario))
