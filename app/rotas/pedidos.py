from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Response, status
from sqlalchemy import or_, select

from app.dependencias import Comercial, Operacao, Sessao
from app.esquemas.comum import Pagina
from app.esquemas.pedidos import (
    AcaoPedido,
    CancelamentoPedido,
    EnvioPedido,
    ItensSubstituir,
    PedidoAtualizar,
    PedidoCriar,
    PedidoResumo,
    PedidoSaida,
)
from app.modelos import Cliente, PedidoVenda, Usuario
from app.modelos.enums import StatusPedido
from app.servicos import auditoria
from app.servicos import pedidos as servico
from app.servicos.relatorios import intervalo_utc, para_csv
from app.utils.paginacao import ParametrosPagina, ordenar, paginar, termo_like

router = APIRouter(prefix="/pedidos", tags=["Pedidos de venda"])

ORDENACAO = {"criado": PedidoVenda.criado_em, "total": PedidoVenda.total, "numero": PedidoVenda.id}
ChaveIdempotencia = Annotated[
    str | None,
    Header(alias="Idempotency-Key", max_length=80, description="Repetir a mesma chave não duplica o pedido"),
]


def _saida(pedido: PedidoVenda, usuario: Usuario) -> PedidoSaida:
    return PedidoSaida.de(pedido, servico.acoes_disponiveis(pedido, usuario))


def _consulta(usuario, q, status_, cliente_id, vendedor_id, deposito_id, inicio, fim, meus, ordem):
    consulta = select(PedidoVenda).join(Cliente, Cliente.id == PedidoVenda.cliente_id)
    if q:
        termo = termo_like(q)
        consulta = consulta.where(or_(PedidoVenda.numero.ilike(termo, escape="\\"), Cliente.nome.ilike(termo, escape="\\")))
    if status_:
        consulta = consulta.where(PedidoVenda.status.in_(status_))
    if cliente_id:
        consulta = consulta.where(PedidoVenda.cliente_id == cliente_id)
    if vendedor_id:
        consulta = consulta.where(PedidoVenda.vendedor_id == vendedor_id)
    if meus:
        consulta = consulta.where(PedidoVenda.vendedor_id == usuario.id)
    if deposito_id:
        consulta = consulta.where(PedidoVenda.deposito_id == deposito_id)
    if inicio or fim:
        ini, fim_utc = intervalo_utc(inicio or date(2000, 1, 1), fim or date(2999, 12, 31), None)
        consulta = consulta.where(PedidoVenda.criado_em >= ini, PedidoVenda.criado_em < fim_utc)
    return ordenar(consulta, ordem, ORDENACAO, "-criado").order_by(PedidoVenda.id.desc())


StatusFiltro = Annotated[list[StatusPedido] | None, Query(alias="status")]


@router.get("", response_model=Pagina[PedidoResumo])
def listar(
    usuario: Operacao,
    sessao: Sessao,
    pag: ParametrosPagina,
    q: Annotated[str | None, Query(max_length=80)] = None,
    status_: StatusFiltro = None,
    cliente_id: int | None = None,
    vendedor_id: int | None = None,
    deposito_id: int | None = None,
    inicio: date | None = None,
    fim: date | None = None,
    meus: bool = False,
    ordem: str | None = None,
):
    consulta = _consulta(usuario, q, status_, cliente_id, vendedor_id, deposito_id, inicio, fim, meus, ordem)
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar([PedidoResumo.de(p) for p in itens], total, pag.pagina, pag.por_pagina)


@router.get("/exportar", summary="Exportar pedidos filtrados em CSV")
def exportar(
    usuario: Operacao,
    sessao: Sessao,
    q: Annotated[str | None, Query(max_length=80)] = None,
    status_: StatusFiltro = None,
    cliente_id: int | None = None,
    inicio: date | None = None,
    fim: date | None = None,
    meus: bool = False,
    formato: Literal["csv"] = "csv",
):
    consulta = _consulta(usuario, q, status_, cliente_id, None, None, inicio, fim, meus, None)
    linhas = [PedidoResumo.de(p).model_dump(mode="json") for p in sessao.scalars(consulta.limit(20_000)).unique()]
    conteudo = para_csv(
        linhas,
        [
            ("numero", "Número"),
            ("status", "Status"),
            ("cliente", "Cliente"),
            ("vendedor", "Vendedor"),
            ("deposito", "Depósito"),
            ("quantidade_itens", "Itens"),
            ("total", "Total"),
            ("criado_em", "Criado em"),
            ("faturado_em", "Faturado em"),
        ],
    )
    return Response(
        conteudo, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="pedidos.csv"'}
    )


@router.post("", response_model=PedidoSaida, status_code=status.HTTP_201_CREATED)
def criar(dados: PedidoCriar, usuario: Comercial, sessao: Sessao, resposta: Response, chave: ChaveIdempotencia = None):
    pedido, novo = servico.criar(sessao, dados, usuario, chave)
    if not novo:
        resposta.status_code = status.HTTP_200_OK
        resposta.headers["Idempotent-Replay"] = "true"
        return _saida(pedido, usuario)
    auditoria.registrar(
        sessao, usuario, "pedido_criado", "pedido_venda", pedido.id, {"numero": pedido.numero, "total": pedido.total}
    )
    sessao.commit()
    return _saida(pedido, usuario)


@router.get("/{pedido_id}", response_model=PedidoSaida)
def obter(pedido_id: int, usuario: Operacao, sessao: Sessao):
    return _saida(servico.obter_pedido(sessao, pedido_id), usuario)


@router.patch("/{pedido_id}", response_model=PedidoSaida)
def atualizar(pedido_id: int, dados: PedidoAtualizar, usuario: Comercial, sessao: Sessao):
    pedido = servico.atualizar(sessao, servico.obter_pedido(sessao, pedido_id, travar=True), dados, usuario)
    auditoria.registrar(sessao, usuario, "pedido_alterado", "pedido_venda", pedido.id, dados.model_dump(exclude_unset=True))
    sessao.commit()
    return _saida(pedido, usuario)


@router.put("/{pedido_id}/itens", response_model=PedidoSaida, summary="Substituir os itens de um pedido em rascunho")
def substituir_itens(pedido_id: int, dados: ItensSubstituir, usuario: Comercial, sessao: Sessao):
    pedido = servico.substituir_itens(sessao, servico.obter_pedido(sessao, pedido_id, travar=True), dados.itens, usuario)
    auditoria.registrar(
        sessao, usuario, "pedido_itens", "pedido_venda", pedido.id, {"itens": len(dados.itens), "total": pedido.total}
    )
    sessao.commit()
    return _saida(pedido, usuario)


def _transicao(acao: str, pedido_id: int, usuario: Usuario, sessao, **extras) -> PedidoSaida:
    pedido = servico.obter_pedido(sessao, pedido_id, travar=True)
    servico.transicionar(sessao, pedido, acao, usuario, **extras)
    auditoria.registrar(sessao, usuario, f"pedido_{acao}", "pedido_venda", pedido.id, {"status": pedido.status})
    sessao.commit()
    return _saida(pedido, usuario)


@router.post("/{pedido_id}/confirmar", response_model=PedidoSaida, summary="Confirmar e reservar o estoque")
def confirmar(pedido_id: int, usuario: Operacao, sessao: Sessao, dados: AcaoPedido | None = None):
    return _transicao("confirmar", pedido_id, usuario, sessao, observacao=dados.observacao if dados else None)


@router.post("/{pedido_id}/separar", response_model=PedidoSaida)
def separar(pedido_id: int, usuario: Operacao, sessao: Sessao, dados: AcaoPedido | None = None):
    return _transicao("separar", pedido_id, usuario, sessao, observacao=dados.observacao if dados else None)


@router.post("/{pedido_id}/faturar", response_model=PedidoSaida, summary="Faturar e baixar o estoque reservado")
def faturar(pedido_id: int, usuario: Operacao, sessao: Sessao, dados: AcaoPedido | None = None):
    return _transicao("faturar", pedido_id, usuario, sessao, observacao=dados.observacao if dados else None)


@router.post("/{pedido_id}/enviar", response_model=PedidoSaida)
def enviar(pedido_id: int, dados: EnvioPedido, usuario: Operacao, sessao: Sessao):
    return _transicao("enviar", pedido_id, usuario, sessao, observacao=dados.observacao, codigo_rastreio=dados.codigo_rastreio)


@router.post("/{pedido_id}/entregar", response_model=PedidoSaida)
def entregar(pedido_id: int, usuario: Operacao, sessao: Sessao, dados: AcaoPedido | None = None):
    return _transicao("entregar", pedido_id, usuario, sessao, observacao=dados.observacao if dados else None)


@router.post("/{pedido_id}/cancelar", response_model=PedidoSaida, summary="Cancelar (libera reserva ou estorna o faturado)")
def cancelar(pedido_id: int, dados: CancelamentoPedido, usuario: Operacao, sessao: Sessao):
    return _transicao("cancelar", pedido_id, usuario, sessao, motivo=dados.motivo)
