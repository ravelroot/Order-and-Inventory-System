from datetime import date

import pytest

from app.servicos.relatorios import intervalo_utc


def _vender(c, itens):
    pedido = c.http.post(
        "/api/v1/pedidos",
        json={"cliente_id": c.cliente.id, "deposito_id": c.principal.id, "itens": itens},
        headers=c.h_gerente,
    ).json()
    for acao in ("confirmar", "separar", "faturar"):
        r = c.http.post(f"/api/v1/pedidos/{pedido['id']}/{acao}", headers=c.h_gerente)
        assert r.status_code == 200, r.text
    return pedido


@pytest.fixture
def vendas(cenario):
    p1, p2, p3 = cenario.produtos
    _vender(cenario, [{"produto_id": p1.id, "quantidade": 10}, {"produto_id": p2.id, "quantidade": 1}])
    _vender(cenario, [{"produto_id": p1.id, "quantidade": 5}, {"produto_id": p3.id, "quantidade": 10}])
    return cenario


def test_intervalo_usa_fuso_de_brasilia():
    ini, fim = intervalo_utc(date(2026, 3, 1), date(2026, 3, 1))
    assert (ini.hour, fim.hour) == (3, 3)


def test_vendas_por_dia_e_por_produto(vendas):
    r = vendas.http.get("/api/v1/relatorios/vendas", params={"agrupar": "produto"}, headers=vendas.h_gerente).json()
    assert r["totais"]["receita"] == 1949.0
    assert r["totais"]["pedidos"] == 2
    primeiro = r["linhas"][0]
    assert primeiro["rotulo"] == vendas.produtos[0].nome
    assert primeiro["receita"] == 1500.0 and primeiro["custo"] == 900.0 and primeiro["margem_percentual"] == 40.0

    por_dia = vendas.http.get("/api/v1/relatorios/vendas", params={"agrupar": "dia"}, headers=vendas.h_gerente).json()
    assert len(por_dia["linhas"]) == 30
    assert por_dia["totais"]["receita"] == 1949.0
    assert por_dia["totais"]["ticket_medio"] == 974.5


def test_curva_abc(vendas):
    r = vendas.http.get("/api/v1/relatorios/curva-abc", headers=vendas.h_gerente).json()
    classes = {i["sku"]: i["classe"] for i in r["itens"]}
    assert classes[vendas.produtos[0].sku] == "A"
    assert r["itens"][-1]["acumulado"] == 100.0
    assert sum(v["produtos"] for v in r["resumo"].values()) == 3


def test_giro_e_sugestao_de_compra(vendas):
    r = vendas.http.get("/api/v1/relatorios/giro-estoque", params={"dias": 30}, headers=vendas.h_estoquista).json()
    por_sku = {i["sku"]: i for i in r["itens"]}
    item = por_sku[vendas.produtos[0].sku]
    assert item["vendido_periodo"] == 15
    assert item["demanda_diaria"] == 0.5
    assert item["cobertura_dias"] == 70.0
    assert item["situacao"] == "ok"


def test_dashboard(vendas):
    r = vendas.http.get("/api/v1/relatorios/dashboard", headers=vendas.h_vendedor)
    assert r.status_code == 200
    d = r.json()
    assert d["pedidos_por_status"]["FATURADO"] == 2
    assert d["receita_mes"] == 1949.0
    assert d["unidades_em_estoque"] == 150 - 26
    assert len(d["vendas_30_dias"]) == 30
    assert d["top_produtos"][0]["receita"] == 1500.0


def test_relatorio_de_vendas_exige_gestao(cenario):
    assert cenario.http.get("/api/v1/relatorios/vendas", headers=cenario.h_vendedor).status_code == 403


def test_periodo_invalido(cenario):
    r = cenario.http.get(
        "/api/v1/relatorios/vendas", params={"inicio": "2026-05-10", "fim": "2026-05-01"}, headers=cenario.h_gerente
    )
    assert r.status_code == 422


def test_vendas_em_csv(vendas):
    r = vendas.http.get("/api/v1/relatorios/vendas", params={"agrupar": "categoria", "formato": "csv"}, headers=vendas.h_gerente)
    linhas = r.text.lstrip("﻿").splitlines()
    assert linhas[0].startswith("Categoria;Pedidos")
    assert len(linhas) == 2 and linhas[1].startswith("Informática;2;")
