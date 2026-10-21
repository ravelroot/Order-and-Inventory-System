import pytest

from app.utils.documentos import (
    cnpj_valido,
    completar_cnpj,
    completar_cpf,
    cpf_valido,
    ean13_digito,
    ean13_valido,
    formatar_documento,
    mascarar_documento,
)


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", completar_cpf("123456789")])
def test_cpf_valido(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize("cpf", ["111.111.111-11", "529.982.247-24", "123", ""])
def test_cpf_invalido(cpf):
    assert not cpf_valido(cpf)


def test_cnpj_e_ean():
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-82")
    assert cnpj_valido(completar_cnpj("123456780001"))
    codigo = "200000000001"
    assert ean13_valido(codigo + ean13_digito(codigo))


def test_formatar_e_mascarar():
    assert formatar_documento("52998224725") == "529.982.247-25"
    assert mascarar_documento("52998224725") == "***.982.***-25"
    assert formatar_documento("11222333000181") == "11.222.333/0001-81"


def test_criar_produto_e_conflito_de_sku(cenario):
    corpo = {
        "sku": "teclado-01",
        "nome": "Teclado mecânico ABNT2",
        "categoria_id": cenario.categoria.id,
        "preco_venda": "349.90",
        "estoque_minimo": 5,
    }
    r = cenario.http.post("/api/v1/produtos", json=corpo, headers=cenario.h_gerente)
    assert r.status_code == 201, r.text
    assert r.json()["sku"] == "TECLADO-01"
    assert r.json()["abaixo_minimo"] is True
    assert cenario.http.post("/api/v1/produtos", json=corpo, headers=cenario.h_gerente).status_code == 409
    assert cenario.http.post("/api/v1/produtos", json={**corpo, "sku": "OUTRO"}, headers=cenario.h_vendedor).status_code == 403


def test_codigo_de_barras_invalido(cenario):
    corpo = {
        "sku": "X-1",
        "nome": "Produto X",
        "categoria_id": cenario.categoria.id,
        "preco_venda": "1",
        "codigo_barras": "2000000000010",
    }
    r = cenario.http.post("/api/v1/produtos", json=corpo, headers=cenario.h_gerente)
    assert r.status_code == 422


def test_atualizar_produto_com_controle_de_versao(cenario):
    p = cenario.produtos[0]
    atual = cenario.http.get(f"/api/v1/produtos/{p.id}", headers=cenario.h_admin).json()
    ok = cenario.http.patch(
        f"/api/v1/produtos/{p.id}", json={"preco_venda": "120.00", "versao": atual["versao"]}, headers=cenario.h_gerente
    )
    assert ok.status_code == 200
    assert ok.json()["preco_venda"] == 120.0
    velho = cenario.http.patch(
        f"/api/v1/produtos/{p.id}", json={"preco_venda": "130.00", "versao": atual["versao"]}, headers=cenario.h_gerente
    )
    assert velho.status_code == 409
    assert velho.json()["erro"]["codigo"] == "concorrencia"


def test_filtros_de_produtos(cenario):
    cenario.http.patch(f"/api/v1/produtos/{cenario.produtos[2].id}", json={"estoque_minimo": 80}, headers=cenario.h_gerente)
    r = cenario.http.get("/api/v1/produtos", params={"abaixo_minimo": True}, headers=cenario.h_vendedor).json()
    assert [i["id"] for i in r["itens"]] == [cenario.produtos[2].id]
    r = cenario.http.get(
        "/api/v1/produtos", params={"q": "SKU-", "ordem": "-preco", "por_pagina": 2}, headers=cenario.h_vendedor
    ).json()
    assert r["total"] == 3 and r["paginas"] == 2
    assert r["itens"][0]["preco_venda"] == 250.0


def test_busca_com_curinga_nao_quebra(cenario):
    r = cenario.http.get("/api/v1/produtos", params={"q": "%_%"}, headers=cenario.h_vendedor)
    assert r.status_code == 200
    r = cenario.http.get("/api/v1/clientes", params={"q": "100%"}, headers=cenario.h_vendedor)
    assert r.status_code == 200 and r.json()["total"] == 0


def test_exportar_produtos_csv(cenario):
    r = cenario.http.get("/api/v1/produtos/exportar", headers=cenario.h_vendedor)
    assert r.status_code == 200
    assert r.text.lstrip("﻿").splitlines()[0].startswith("SKU;Produto")


def test_cliente_valida_documento(cenario):
    base = {"tipo_pessoa": "F", "nome": "Joana Exemplo", "documento": "111.111.111-11"}
    assert cenario.http.post("/api/v1/clientes", json=base, headers=cenario.h_vendedor).status_code == 422
    cpf = completar_cpf("987654321")
    r = cenario.http.post(
        "/api/v1/clientes", json={**base, "documento": cpf, "cep": "01001-000", "uf": "sp"}, headers=cenario.h_vendedor
    )
    assert r.status_code == 201, r.text
    assert r.json()["uf"] == "SP" and r.json()["cep"] == "01001000"
    assert cenario.http.post("/api/v1/clientes", json={**base, "documento": cpf}, headers=cenario.h_vendedor).status_code == 409


def test_documento_mascarado_para_vendedor_e_revelacao_auditada(cenario):
    cid = cenario.cliente.id
    vendedor = cenario.http.get(f"/api/v1/clientes/{cid}", headers=cenario.h_vendedor).json()
    gerente = cenario.http.get(f"/api/v1/clientes/{cid}", headers=cenario.h_gerente).json()
    assert vendedor["documento"] == "***.982.***-25"
    assert gerente["documento"] == "529.982.247-25"
    revelado = cenario.http.get(f"/api/v1/clientes/{cid}/documento", headers=cenario.h_vendedor).json()
    assert revelado["documento"] == "529.982.247-25"
    trilha = cenario.http.get("/api/v1/auditoria", params={"acao": "documento_revelado"}, headers=cenario.h_admin).json()
    assert trilha["total"] == 1 and trilha["itens"][0]["usuario"] == "vendedor"


def test_auditoria_so_para_admin(cenario):
    assert cenario.http.get("/api/v1/auditoria", headers=cenario.h_gerente).status_code == 403


def test_fornecedor_valida_cnpj(cenario):
    corpo = {"razao_social": "Distribuidora Exemplo Ltda", "cnpj": "11.222.333/0001-82"}
    assert cenario.http.post("/api/v1/fornecedores", json=corpo, headers=cenario.h_gerente).status_code == 422
    r = cenario.http.post("/api/v1/fornecedores", json={**corpo, "cnpj": "11.222.333/0001-81"}, headers=cenario.h_gerente)
    assert r.status_code == 201
    assert r.json()["cnpj_formatado"] == "11.222.333/0001-81"
