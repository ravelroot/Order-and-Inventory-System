from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.dependencias import Gestor, Logistica, Operacao, Sessao
from app.esquemas.comum import Pagina
from app.esquemas.pedidos import CompraCriar, CompraSaida, RecebimentoEntrada
from app.modelos import PedidoCompra
from app.modelos.enums import StatusCompra
from app.servicos import auditoria
from app.servicos import compras as servico
from app.utils.paginacao import ParametrosPagina, paginar

router = APIRouter(prefix="/compras", tags=["Pedidos de compra"])


@router.get("", response_model=Pagina[CompraSaida])
def listar(
    _: Operacao,
    sessao: Sessao,
    pag: ParametrosPagina,
    status_: Annotated[list[StatusCompra] | None, Query(alias="status")] = None,
    fornecedor_id: int | None = None,
):
    consulta = select(PedidoCompra).order_by(PedidoCompra.criado_em.desc(), PedidoCompra.id.desc())
    if status_:
        consulta = consulta.where(PedidoCompra.status.in_(status_))
    if fornecedor_id:
        consulta = consulta.where(PedidoCompra.fornecedor_id == fornecedor_id)
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar([CompraSaida.de(c) for c in itens], total, pag.pagina, pag.por_pagina)


@router.get("/{compra_id}", response_model=CompraSaida)
def obter(compra_id: int, _: Operacao, sessao: Sessao):
    return CompraSaida.de(servico.obter_compra(sessao, compra_id))


@router.post("", response_model=CompraSaida, status_code=status.HTTP_201_CREATED)
def criar(dados: CompraCriar, usuario: Gestor, sessao: Sessao):
    compra = servico.criar(sessao, dados, usuario)
    auditoria.registrar(
        sessao, usuario, "compra_criada", "pedido_compra", compra.id, {"numero": compra.numero, "total": compra.total}
    )
    sessao.commit()
    return CompraSaida.de(compra)


@router.post("/{compra_id}/enviar", response_model=CompraSaida, summary="Marcar como enviado ao fornecedor")
def enviar(compra_id: int, usuario: Gestor, sessao: Sessao):
    compra = servico.enviar(servico.obter_compra(sessao, compra_id, travar=True))
    auditoria.registrar(sessao, usuario, "compra_enviada", "pedido_compra", compra.id)
    sessao.commit()
    return CompraSaida.de(compra)


@router.post("/{compra_id}/receber", response_model=CompraSaida, summary="Receber mercadoria (total ou parcial)")
def receber(compra_id: int, usuario: Logistica, sessao: Sessao, dados: RecebimentoEntrada | None = None):
    compra = servico.obter_compra(sessao, compra_id, travar=True)
    servico.receber(sessao, compra, usuario, dados.itens if dados else None)
    auditoria.registrar(sessao, usuario, "compra_recebida", "pedido_compra", compra.id, {"status": compra.status})
    sessao.commit()
    return CompraSaida.de(compra)


@router.post("/{compra_id}/cancelar", response_model=CompraSaida)
def cancelar(compra_id: int, usuario: Gestor, sessao: Sessao):
    compra = servico.cancelar(servico.obter_compra(sessao, compra_id, travar=True))
    auditoria.registrar(sessao, usuario, "compra_cancelada", "pedido_compra", compra.id)
    sessao.commit()
    return CompraSaida.de(compra)
