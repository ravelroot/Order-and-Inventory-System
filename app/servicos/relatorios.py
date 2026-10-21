import csv
import io
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, type_coerce
from sqlalchemy.orm import Session

from app.database import Dinheiro, agora_utc
from app.erros import RegraViolada
from app.modelos import (
    Categoria,
    Cliente,
    Fornecedor,
    ItemPedidoVenda,
    MovimentacaoEstoque,
    PedidoVenda,
    Produto,
    SaldoEstoque,
    Usuario,
)
from app.modelos.enums import STATUS_FATURADOS, StatusPedido, TipoMovimentacao

FUSO = ZoneInfo("America/Sao_Paulo")
ZERO = Decimal("0")


def intervalo_utc(inicio: date, fim: date, limite_dias: int | None = 731) -> tuple[datetime, datetime]:
    if fim < inicio:
        raise RegraViolada("A data final precisa ser igual ou depois da inicial.")
    if limite_dias is not None and (fim - inicio).days > limite_dias:
        raise RegraViolada("O período máximo é de 2 anos.")
    return (
        datetime.combine(inicio, time.min, FUSO).astimezone(ZoneInfo("UTC")),
        datetime.combine(fim + timedelta(days=1), time.min, FUSO).astimezone(ZoneInfo("UTC")),
    )


def _custo_itens():
    return type_coerce(func.sum(ItemPedidoVenda.custo_unitario * ItemPedidoVenda.quantidade), Dinheiro())


def _filtro_faturados(ini: datetime, fim: datetime):
    return (PedidoVenda.status.in_(STATUS_FATURADOS), PedidoVenda.faturado_em >= ini, PedidoVenda.faturado_em < fim)


def _pedidos_faturados(sessao: Session, ini: datetime, fim: datetime) -> list[tuple]:
    consulta = (
        select(
            PedidoVenda.id,
            PedidoVenda.faturado_em,
            func.sum(ItemPedidoVenda.total),
            _custo_itens(),
            func.sum(ItemPedidoVenda.quantidade),
        )
        .join(ItemPedidoVenda, ItemPedidoVenda.pedido_id == PedidoVenda.id)
        .where(*_filtro_faturados(ini, fim))
        .group_by(PedidoVenda.id, PedidoVenda.faturado_em)
    )
    return list(sessao.execute(consulta).all())


def _linha(chave, rotulo, pedidos: int, quantidade: int, receita: Decimal, custo: Decimal) -> dict:
    receita = receita or ZERO
    custo = custo or ZERO
    margem = receita - custo
    return {
        "chave": chave,
        "rotulo": rotulo,
        "pedidos": pedidos,
        "quantidade": int(quantidade or 0),
        "receita": float(receita),
        "custo": float(custo),
        "margem": float(margem),
        "margem_percentual": round(float(margem / receita * 100), 1) if receita else None,
    }


def _chave_tempo(momento: datetime, agrupar: str) -> tuple[str, str]:
    local = momento.astimezone(FUSO).date()
    if agrupar == "dia":
        return local.isoformat(), local.strftime("%d/%m")
    if agrupar == "semana":
        inicio = local - timedelta(days=local.weekday())
        return inicio.isoformat(), f"Sem. {inicio.strftime('%d/%m')}"
    return local.strftime("%Y-%m"), local.strftime("%m/%Y")


def _serie_vazia(inicio: date, fim: date, agrupar: str) -> dict[str, str]:
    chaves: dict[str, str] = {}
    atual = inicio
    while atual <= fim:
        momento = datetime.combine(atual, time(12), FUSO)
        chave, rotulo = _chave_tempo(momento, agrupar)
        chaves.setdefault(chave, rotulo)
        atual += timedelta(days=1)
    return chaves


AGRUPAMENTOS_SQL = {
    "categoria": (Categoria.id, Categoria.nome),
    "produto": (Produto.id, Produto.nome),
    "vendedor": (Usuario.id, Usuario.nome),
    "cliente": (Cliente.id, Cliente.nome),
    "uf": (Cliente.uf, Cliente.uf),
}


def vendas(sessao: Session, inicio: date, fim: date, agrupar: str = "dia") -> dict:
    ini, fim_utc = intervalo_utc(inicio, fim)
    if agrupar in ("dia", "semana", "mes"):
        grupos: dict[str, list] = {c: [r, 0, 0, ZERO, ZERO] for c, r in _serie_vazia(inicio, fim, agrupar).items()}
        for _, faturado_em, receita, custo, quantidade in _pedidos_faturados(sessao, ini, fim_utc):
            chave, rotulo = _chave_tempo(faturado_em, agrupar)
            grupo = grupos.setdefault(chave, [rotulo, 0, 0, ZERO, ZERO])
            grupo[1] += 1
            grupo[2] += quantidade or 0
            grupo[3] += receita or ZERO
            grupo[4] += custo or ZERO
        linhas = [_linha(c, g[0], g[1], g[2], g[3], g[4]) for c, g in sorted(grupos.items())]
    elif agrupar in AGRUPAMENTOS_SQL:
        chave_col, rotulo_col = AGRUPAMENTOS_SQL[agrupar]
        consulta = (
            select(
                chave_col,
                rotulo_col,
                func.count(func.distinct(PedidoVenda.id)),
                func.sum(ItemPedidoVenda.quantidade),
                func.sum(ItemPedidoVenda.total),
                _custo_itens(),
            )
            .select_from(ItemPedidoVenda)
            .join(PedidoVenda, PedidoVenda.id == ItemPedidoVenda.pedido_id)
            .join(Produto, Produto.id == ItemPedidoVenda.produto_id)
            .join(Categoria, Categoria.id == Produto.categoria_id)
            .join(Cliente, Cliente.id == PedidoVenda.cliente_id)
            .outerjoin(Usuario, Usuario.id == PedidoVenda.vendedor_id)
            .where(*_filtro_faturados(ini, fim_utc))
            .group_by(chave_col, rotulo_col)
            .order_by(func.sum(ItemPedidoVenda.total).desc())
        )
        linhas = [_linha(c, r or "—", p, q, rec, cus) for c, r, p, q, rec, cus in sessao.execute(consulta).all()]
    else:
        raise RegraViolada("Agrupamento inválido.")

    receita = sum(Decimal(str(linha["receita"])) for linha in linhas)
    custo = sum(Decimal(str(linha["custo"])) for linha in linhas)
    pedidos = sum(linha["pedidos"] for linha in linhas) if agrupar in ("dia", "semana", "mes") else None
    if pedidos is None:
        pedidos = sessao.scalar(select(func.count(PedidoVenda.id)).where(*_filtro_faturados(ini, fim_utc))) or 0
    totais = _linha("total", "Total", pedidos, sum(linha["quantidade"] for linha in linhas), receita, custo)
    totais["ticket_medio"] = round(float(receita) / pedidos, 2) if pedidos else 0
    return {"inicio": inicio, "fim": fim, "agrupar": agrupar, "linhas": linhas, "totais": totais}


def curva_abc(sessao: Session, inicio: date, fim: date) -> dict:
    ini, fim_utc = intervalo_utc(inicio, fim)
    consulta = (
        select(Produto.id, Produto.sku, Produto.nome, func.sum(ItemPedidoVenda.quantidade), func.sum(ItemPedidoVenda.total))
        .select_from(ItemPedidoVenda)
        .join(PedidoVenda, PedidoVenda.id == ItemPedidoVenda.pedido_id)
        .join(Produto, Produto.id == ItemPedidoVenda.produto_id)
        .where(*_filtro_faturados(ini, fim_utc))
        .group_by(Produto.id, Produto.sku, Produto.nome)
        .order_by(func.sum(ItemPedidoVenda.total).desc(), Produto.id)
    )
    linhas = sessao.execute(consulta).all()
    total = sum((r[4] or ZERO for r in linhas), ZERO)
    acumulado = ZERO
    itens = []
    resumo = {"A": {"produtos": 0, "receita": ZERO}, "B": {"produtos": 0, "receita": ZERO}, "C": {"produtos": 0, "receita": ZERO}}
    for produto_id, sku, nome, quantidade, receita in linhas:
        participacao = (receita / total * 100) if total else ZERO
        inicio_faixa = acumulado
        acumulado += participacao
        classe = "A" if inicio_faixa < 80 else "B" if inicio_faixa < 95 else "C"
        resumo[classe]["produtos"] += 1
        resumo[classe]["receita"] += receita
        itens.append(
            {
                "produto_id": produto_id,
                "sku": sku,
                "produto": nome,
                "quantidade": int(quantidade),
                "receita": float(receita),
                "participacao": round(float(participacao), 2),
                "acumulado": round(float(acumulado), 2),
                "classe": classe,
            }
        )
    return {
        "inicio": inicio,
        "fim": fim,
        "receita_total": float(total),
        "resumo": {k: {"produtos": v["produtos"], "receita": float(v["receita"])} for k, v in resumo.items()},
        "itens": itens,
    }


def giro_estoque(sessao: Session, dias: int = 90, agora: datetime | None = None) -> dict:
    momento = agora or agora_utc()
    desde = momento - timedelta(days=dias)
    saidas = dict(
        sessao.execute(
            select(MovimentacaoEstoque.produto_id, func.sum(MovimentacaoEstoque.quantidade))
            .where(MovimentacaoEstoque.tipo == TipoMovimentacao.SAIDA, MovimentacaoEstoque.criado_em >= desde)
            .group_by(MovimentacaoEstoque.produto_id)
        ).all()
    )
    estoques = {
        pid: (q or 0, r or 0)
        for pid, q, r in sessao.execute(
            select(SaldoEstoque.produto_id, func.sum(SaldoEstoque.quantidade), func.sum(SaldoEstoque.reservado)).group_by(
                SaldoEstoque.produto_id
            )
        ).all()
    }
    produtos = sessao.execute(
        select(Produto, Fornecedor.prazo_entrega_dias)
        .outerjoin(Fornecedor, Fornecedor.id == Produto.fornecedor_id)
        .where(Produto.ativo.is_(True))
        .order_by(Produto.nome)
    ).all()
    itens = []
    contagem: dict[str, int] = defaultdict(int)
    for produto, prazo in produtos:
        quantidade, reservado = estoques.get(produto.id, (0, 0))
        disponivel = quantidade - reservado
        vendido = int(saidas.get(produto.id, 0) or 0)
        demanda = vendido / dias
        prazo = prazo if prazo is not None else 7
        cobertura = round(disponivel / demanda, 1) if demanda > 0 else None
        if vendido == 0:
            situacao = "parado" if quantidade > 0 else "sem_movimento"
        elif disponivel <= 0:
            situacao = "ruptura"
        elif cobertura is not None and cobertura < prazo:
            situacao = "critico"
        elif cobertura is not None and cobertura > 180:
            situacao = "excesso"
        else:
            situacao = "ok"
        alvo = demanda * (prazo + 15) + produto.estoque_minimo
        sugestao = max(0, math.ceil(alvo - disponivel)) if (vendido > 0 or disponivel < produto.estoque_minimo) else 0
        giro = round(vendido / quantidade, 2) if quantidade else None
        contagem[situacao] += 1
        itens.append(
            {
                "produto_id": produto.id,
                "sku": produto.sku,
                "produto": produto.nome,
                "estoque": quantidade,
                "disponivel": disponivel,
                "estoque_minimo": produto.estoque_minimo,
                "vendido_periodo": vendido,
                "demanda_diaria": round(demanda, 2),
                "cobertura_dias": cobertura,
                "giro": giro,
                "prazo_fornecedor_dias": prazo,
                "sugestao_compra": sugestao,
                "situacao": situacao,
                "valor_estoque": float(produto.custo_medio * quantidade),
            }
        )
    ordem = {"ruptura": 0, "critico": 1, "ok": 2, "excesso": 3, "parado": 4, "sem_movimento": 5}
    itens.sort(key=lambda i: (ordem[i["situacao"]], -(i["sugestao_compra"]), i["produto"]))
    return {"dias": dias, "resumo": dict(contagem), "itens": itens}


def dashboard(sessao: Session, agora: datetime | None = None) -> dict:
    momento = agora or agora_utc()
    hoje = momento.astimezone(FUSO).date()
    inicio_mes = hoje.replace(day=1)
    fim_mes_anterior = inicio_mes - timedelta(days=1)
    inicio_mes_anterior = fim_mes_anterior.replace(day=1)

    def receita_periodo(ini: date, fim: date) -> tuple[Decimal, int]:
        a, b = intervalo_utc(ini, fim)
        linha = sessao.execute(
            select(func.coalesce(func.sum(PedidoVenda.total), 0), func.count(PedidoVenda.id)).where(*_filtro_faturados(a, b))
        ).one()
        return Decimal(linha[0] or 0), linha[1]

    receita_mes, pedidos_mes = receita_periodo(inicio_mes, hoje)
    dia_equivalente = min(hoje.day, fim_mes_anterior.day)
    receita_ant, _ = receita_periodo(inicio_mes_anterior, inicio_mes_anterior.replace(day=dia_equivalente))

    por_status = dict(sessao.execute(select(PedidoVenda.status, func.count(PedidoVenda.id)).group_by(PedidoVenda.status)).all())
    valor_estoque = (
        sessao.scalar(
            select(type_coerce(func.coalesce(func.sum(SaldoEstoque.quantidade * Produto.custo_medio), 0), Dinheiro())).join(
                Produto, Produto.id == SaldoEstoque.produto_id
            )
        )
        or ZERO
    )
    unidades = sessao.scalar(select(func.coalesce(func.sum(SaldoEstoque.quantidade), 0))) or 0

    disponivel_por_produto = (
        select(
            Produto.id.label("pid"),
            (func.coalesce(func.sum(SaldoEstoque.quantidade - SaldoEstoque.reservado), 0)).label("disp"),
            Produto.estoque_minimo.label("minimo"),
        )
        .outerjoin(SaldoEstoque, SaldoEstoque.produto_id == Produto.id)
        .where(Produto.ativo.is_(True))
        .group_by(Produto.id, Produto.estoque_minimo)
        .subquery()
    )
    abaixo_minimo = (
        sessao.scalar(
            select(func.count())
            .select_from(disponivel_por_produto)
            .where(disponivel_por_produto.c.disp < disponivel_por_produto.c.minimo)
        )
        or 0
    )
    ruptura = (
        sessao.scalar(select(func.count()).select_from(disponivel_por_produto).where(disponivel_por_produto.c.disp <= 0)) or 0
    )

    serie = vendas(sessao, hoje - timedelta(days=29), hoje, "dia")
    top = vendas(sessao, hoje - timedelta(days=29), hoje, "produto")["linhas"][:5]
    categorias = vendas(sessao, hoje - timedelta(days=29), hoje, "categoria")["linhas"][:6]

    ultimos = sessao.scalars(select(PedidoVenda).order_by(PedidoVenda.criado_em.desc(), PedidoVenda.id.desc()).limit(6)).all()

    variacao = None
    if receita_ant:
        variacao = round(float((receita_mes - receita_ant) / receita_ant * 100), 1)
    return {
        "referencia": hoje,
        "receita_mes": float(receita_mes),
        "receita_mes_anterior_mesmo_periodo": float(receita_ant),
        "variacao_percentual": variacao,
        "pedidos_faturados_mes": pedidos_mes,
        "ticket_medio_mes": round(float(receita_mes) / pedidos_mes, 2) if pedidos_mes else 0,
        "pedidos_por_status": {s.value: int(por_status.get(s, 0)) for s in StatusPedido},
        "valor_estoque": float(valor_estoque),
        "unidades_em_estoque": int(unidades),
        "produtos_abaixo_minimo": int(abaixo_minimo),
        "produtos_em_ruptura": int(ruptura),
        "vendas_30_dias": [
            {"data": linha["chave"], "rotulo": linha["rotulo"], "receita": linha["receita"], "pedidos": linha["pedidos"]}
            for linha in serie["linhas"]
        ],
        "top_produtos": top,
        "categorias": categorias,
        "ultimos_pedidos": [
            {
                "id": p.id,
                "numero": p.numero,
                "cliente": p.cliente.nome,
                "status": p.status.value,
                "total": float(p.total),
                "criado_em": p.criado_em,
            }
            for p in ultimos
        ],
    }


def para_csv(linhas: list[dict], colunas: list[tuple[str, str]]) -> str:
    saida = io.StringIO()
    saida.write("﻿")
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow([titulo for _, titulo in colunas])
    for linha in linhas:
        valores = []
        for chave, _ in colunas:
            valor = linha.get(chave)
            if isinstance(valor, float):
                valor = f"{valor:.2f}".replace(".", ",")
            valores.append("" if valor is None else valor)
        escritor.writerow(valores)
    return saida.getvalue()
