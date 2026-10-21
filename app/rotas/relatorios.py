from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from sqlalchemy import select, text

from app.config import obter_config
from app.database import agora_utc
from app.dependencias import Admin, Gestor, Operacao, Sessao
from app.esquemas.comum import Pagina
from app.modelos import Auditoria
from app.servicos import relatorios
from app.utils.paginacao import ParametrosPagina, paginar

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])
auditoria_router = APIRouter(prefix="/auditoria", tags=["Administração"])
saude_router = APIRouter(tags=["Sistema"])

Agrupar = Literal["dia", "semana", "mes", "categoria", "produto", "vendedor", "cliente", "uf"]


def _periodo(inicio: date | None, fim: date | None, dias: int = 30) -> tuple[date, date]:
    hoje = agora_utc().astimezone(relatorios.FUSO).date()
    fim = fim or hoje
    return inicio or (fim - timedelta(days=dias - 1)), fim


def _csv(conteudo: str, nome: str) -> Response:
    return Response(
        conteudo, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{nome}"'}
    )


@router.get("/dashboard", summary="Indicadores do painel inicial")
def dashboard(_: Operacao, sessao: Sessao):
    return relatorios.dashboard(sessao)


@router.get("/vendas", summary="Vendas faturadas por período ou dimensão")
def vendas(
    _: Gestor,
    sessao: Sessao,
    inicio: date | None = None,
    fim: date | None = None,
    agrupar: Agrupar = "dia",
    formato: Literal["json", "csv"] = "json",
):
    ini, fim_ = _periodo(inicio, fim)
    dados = relatorios.vendas(sessao, ini, fim_, agrupar)
    if formato == "csv":
        colunas = [
            ("rotulo", agrupar.capitalize()),
            ("pedidos", "Pedidos"),
            ("quantidade", "Unidades"),
            ("receita", "Receita"),
            ("custo", "Custo"),
            ("margem", "Margem"),
            ("margem_percentual", "Margem %"),
        ]
        return _csv(relatorios.para_csv(dados["linhas"], colunas), f"vendas_{agrupar}_{ini}_{fim_}.csv")
    return dados


@router.get("/curva-abc", summary="Classificação ABC dos produtos por receita")
def curva_abc(
    _: Gestor,
    sessao: Sessao,
    inicio: date | None = None,
    fim: date | None = None,
    formato: Literal["json", "csv"] = "json",
):
    ini, fim_ = _periodo(inicio, fim, 90)
    dados = relatorios.curva_abc(sessao, ini, fim_)
    if formato == "csv":
        colunas = [
            ("classe", "Classe"),
            ("sku", "SKU"),
            ("produto", "Produto"),
            ("quantidade", "Unidades"),
            ("receita", "Receita"),
            ("participacao", "Participação %"),
            ("acumulado", "Acumulado %"),
        ]
        return _csv(relatorios.para_csv(dados["itens"], colunas), f"curva_abc_{ini}_{fim_}.csv")
    return dados


@router.get("/giro-estoque", summary="Giro, cobertura em dias e sugestão de reposição")
def giro(
    _: Operacao,
    sessao: Sessao,
    dias: Annotated[int, Query(ge=7, le=365)] = 90,
    formato: Literal["json", "csv"] = "json",
):
    dados = relatorios.giro_estoque(sessao, dias)
    if formato == "csv":
        colunas = [
            ("situacao", "Situação"),
            ("sku", "SKU"),
            ("produto", "Produto"),
            ("disponivel", "Disponível"),
            ("estoque_minimo", "Mínimo"),
            ("vendido_periodo", f"Vendido em {dias} dias"),
            ("demanda_diaria", "Demanda/dia"),
            ("cobertura_dias", "Cobertura (dias)"),
            ("sugestao_compra", "Sugestão de compra"),
        ]
        return _csv(relatorios.para_csv(dados["itens"], colunas), f"giro_{dias}d.csv")
    return dados


@auditoria_router.get("", summary="Trilha de auditoria (somente administradores)")
def listar_auditoria(
    _: Admin,
    sessao: Sessao,
    pag: ParametrosPagina,
    acao: str | None = None,
    entidade: str | None = None,
    usuario_id: int | None = None,
):
    consulta = select(Auditoria).order_by(Auditoria.criado_em.desc(), Auditoria.id.desc())
    if acao:
        consulta = consulta.where(Auditoria.acao == acao)
    if entidade:
        consulta = consulta.where(Auditoria.entidade == entidade)
    if usuario_id:
        consulta = consulta.where(Auditoria.usuario_id == usuario_id)
    itens, total = paginar(sessao, consulta, pag)
    linhas = [
        {
            "id": a.id,
            "criado_em": a.criado_em,
            "usuario": a.usuario.usuario if a.usuario else None,
            "acao": a.acao,
            "entidade": a.entidade,
            "entidade_id": a.entidade_id,
            "detalhes": a.detalhes,
        }
        for a in itens
    ]
    return Pagina[dict].montar(linhas, total, pag.pagina, pag.por_pagina)


@saude_router.get("/saude", summary="Verificação de saúde (sem dados sensíveis)")
def saude(sessao: Sessao):
    sessao.execute(text("SELECT 1"))
    return {"status": "ok", "versao": obter_config().versao}
