from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import or_, select

from app.dependencias import Gestor, Logistica, Operacao, Sessao
from app.erros import Conflito, NaoEncontrado
from app.esquemas.comum import Pagina
from app.esquemas.estoque import (
    AjusteEstoque,
    DepositoEntrada,
    DepositoSaida,
    EntradaEstoque,
    MovimentacaoSaida,
    SaldoSaida,
    TransferenciaEstoque,
)
from app.modelos import Deposito, MovimentacaoEstoque, Produto, SaldoEstoque
from app.modelos.enums import OrigemMovimentacao, TipoMovimentacao
from app.servicos import auditoria, estoque
from app.servicos.estoque import Contexto
from app.servicos.relatorios import intervalo_utc
from app.utils.paginacao import ParametrosPagina, paginar, termo_like

depositos = APIRouter(prefix="/depositos", tags=["Estoque"])
router = APIRouter(prefix="/estoque", tags=["Estoque"])


@depositos.get("", response_model=list[DepositoSaida])
def listar_depositos(_: Operacao, sessao: Sessao, ativo: bool | None = None):
    consulta = select(Deposito).order_by(Deposito.codigo)
    if ativo is not None:
        consulta = consulta.where(Deposito.ativo.is_(ativo))
    return sessao.scalars(consulta).all()


@depositos.post("", response_model=DepositoSaida, status_code=status.HTTP_201_CREATED)
def criar_deposito(dados: DepositoEntrada, usuario: Gestor, sessao: Sessao):
    if sessao.scalars(select(Deposito.id).where(Deposito.codigo == dados.codigo)).first():
        raise Conflito("Já existe um depósito com esse código.")
    deposito = Deposito(**dados.model_dump())
    sessao.add(deposito)
    sessao.flush()
    auditoria.registrar(sessao, usuario, "deposito_criado", "deposito", deposito.id)
    sessao.commit()
    return deposito


@depositos.put("/{deposito_id}", response_model=DepositoSaida)
def atualizar_deposito(deposito_id: int, dados: DepositoEntrada, usuario: Gestor, sessao: Sessao):
    deposito = sessao.get(Deposito, deposito_id)
    if deposito is None:
        raise NaoEncontrado("Depósito não encontrado.")
    for campo, valor in dados.model_dump().items():
        setattr(deposito, campo, valor)
    auditoria.registrar(sessao, usuario, "deposito_alterado", "deposito", deposito.id)
    sessao.commit()
    return deposito


@router.get("/saldos", response_model=Pagina[SaldoSaida])
def listar_saldos(
    _: Operacao,
    sessao: Sessao,
    pag: ParametrosPagina,
    deposito_id: int | None = None,
    produto_id: int | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    abaixo_minimo: bool = False,
    com_saldo: bool = False,
):
    consulta = (
        select(SaldoEstoque)
        .join(Produto, Produto.id == SaldoEstoque.produto_id)
        .join(Deposito, Deposito.id == SaldoEstoque.deposito_id)
        .order_by(Produto.nome, Deposito.codigo)
    )
    if deposito_id:
        consulta = consulta.where(SaldoEstoque.deposito_id == deposito_id)
    if produto_id:
        consulta = consulta.where(SaldoEstoque.produto_id == produto_id)
    if q:
        termo = termo_like(q)
        consulta = consulta.where(or_(Produto.nome.ilike(termo, escape="\\"), Produto.sku.ilike(termo, escape="\\")))
    if abaixo_minimo:
        consulta = consulta.where((SaldoEstoque.quantidade - SaldoEstoque.reservado) < Produto.estoque_minimo)
    if com_saldo:
        consulta = consulta.where(SaldoEstoque.quantidade > 0)
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar([SaldoSaida.de(s) for s in itens], total, pag.pagina, pag.por_pagina)


@router.post("/entradas", response_model=MovimentacaoSaida, status_code=status.HTTP_201_CREATED)
def registrar_entrada(dados: EntradaEstoque, usuario: Logistica, sessao: Sessao):
    ctx = Contexto(usuario, OrigemMovimentacao.MANUAL, motivo=dados.motivo)
    movimentacao = estoque.entrada(sessao, dados.produto_id, dados.deposito_id, dados.quantidade, ctx, dados.custo_unitario)
    sessao.flush()
    auditoria.registrar(sessao, usuario, "estoque_entrada", "produto", dados.produto_id, dados.model_dump())
    sessao.commit()
    return MovimentacaoSaida.de(movimentacao)


@router.post("/ajustes", response_model=MovimentacaoSaida | None, summary="Ajuste por contagem (inventário)")
def registrar_ajuste(dados: AjusteEstoque, usuario: Logistica, sessao: Sessao):
    ctx = Contexto(usuario, OrigemMovimentacao.INVENTARIO, motivo=dados.motivo)
    movimentacao = estoque.ajustar(sessao, dados.produto_id, dados.deposito_id, dados.quantidade_contada, ctx)
    if movimentacao is None:
        return None
    sessao.flush()
    auditoria.registrar(sessao, usuario, "estoque_ajuste", "produto", dados.produto_id, dados.model_dump())
    sessao.commit()
    return MovimentacaoSaida.de(movimentacao)


@router.post("/transferencias", response_model=list[MovimentacaoSaida], status_code=status.HTTP_201_CREATED)
def registrar_transferencia(dados: TransferenciaEstoque, usuario: Logistica, sessao: Sessao):
    ctx = Contexto(usuario, OrigemMovimentacao.TRANSFERENCIA, motivo=dados.motivo)
    movimentacoes = estoque.transferir(
        sessao, dados.produto_id, dados.deposito_origem_id, dados.deposito_destino_id, dados.quantidade, ctx
    )
    sessao.flush()
    for m in movimentacoes:
        m.origem_id = movimentacoes[0].id
    auditoria.registrar(sessao, usuario, "estoque_transferencia", "produto", dados.produto_id, dados.model_dump())
    sessao.commit()
    return [MovimentacaoSaida.de(m) for m in movimentacoes]


@router.get("/movimentacoes", response_model=Pagina[MovimentacaoSaida])
def listar_movimentacoes(
    _: Operacao,
    sessao: Sessao,
    pag: ParametrosPagina,
    produto_id: int | None = None,
    deposito_id: int | None = None,
    tipo: Annotated[list[TipoMovimentacao] | None, Query()] = None,
    origem: OrigemMovimentacao | None = None,
    inicio: date | None = None,
    fim: date | None = None,
):
    consulta = select(MovimentacaoEstoque).order_by(MovimentacaoEstoque.criado_em.desc(), MovimentacaoEstoque.id.desc())
    if produto_id:
        consulta = consulta.where(MovimentacaoEstoque.produto_id == produto_id)
    if deposito_id:
        consulta = consulta.where(MovimentacaoEstoque.deposito_id == deposito_id)
    if tipo:
        consulta = consulta.where(MovimentacaoEstoque.tipo.in_(tipo))
    if origem:
        consulta = consulta.where(MovimentacaoEstoque.origem == origem)
    if inicio or fim:
        ini, fim_utc = intervalo_utc(inicio or date(2000, 1, 1), fim or date(2999, 12, 31), None)
        consulta = consulta.where(MovimentacaoEstoque.criado_em >= ini, MovimentacaoEstoque.criado_em < fim_utc)
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar([MovimentacaoSaida.de(m) for m in itens], total, pag.pagina, pag.por_pagina)
