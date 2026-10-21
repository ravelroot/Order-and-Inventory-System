URL = "/api/v1/compras"


def _compra(c, itens):
    fornecedor = c.fabrica.fornecedor()
    r = c.http.post(
        URL,
        json={"fornecedor_id": fornecedor.id, "deposito_id": c.filial.id, "previsao_entrega": "2030-01-15", "itens": itens},
        headers=c.h_gerente,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_fluxo_de_compra_com_recebimento_parcial(cenario):
    p1, p2, _ = cenario.produtos
    compra = _compra(
        cenario,
        [
            {"produto_id": p1.id, "quantidade": 10, "custo_unitario": "90.00"},
            {"produto_id": p2.id, "quantidade": 4, "custo_unitario": "150.00"},
        ],
    )
    assert compra["status"] == "RASCUNHO"
    assert compra["total"] == 1500.0
    assert compra["numero"].startswith("PC-")

    nao_enviado = cenario.http.post(f"{URL}/{compra['id']}/receber", headers=cenario.h_estoquista)
    assert nao_enviado.status_code == 409

    assert cenario.http.post(f"{URL}/{compra['id']}/enviar", headers=cenario.h_gerente).json()["status"] == "ENVIADO"

    item1 = compra["itens"][0]["id"]
    parcial = cenario.http.post(
        f"{URL}/{compra['id']}/receber", json={"itens": [{"item_id": item1, "quantidade": 6}]}, headers=cenario.h_estoquista
    )
    assert parcial.status_code == 200, parcial.text
    assert parcial.json()["status"] == "RECEBIDO_PARCIAL"

    excesso = cenario.http.post(
        f"{URL}/{compra['id']}/receber", json={"itens": [{"item_id": item1, "quantidade": 5}]}, headers=cenario.h_estoquista
    )
    assert excesso.status_code == 422

    total = cenario.http.post(f"{URL}/{compra['id']}/receber", headers=cenario.h_estoquista)
    assert total.json()["status"] == "RECEBIDO"
    assert total.json()["percentual_recebido"] == 100.0

    produto = cenario.http.get(f"/api/v1/produtos/{p1.id}", headers=cenario.h_admin).json()
    assert produto["estoque_total"] == 60
    assert produto["custo_medio"] == 65.0


def test_cancelar_compra(cenario):
    compra = _compra(cenario, [{"produto_id": cenario.produtos[0].id, "quantidade": 1, "custo_unitario": "1.00"}])
    r = cenario.http.post(f"{URL}/{compra['id']}/cancelar", headers=cenario.h_gerente)
    assert r.json()["status"] == "CANCELADO"
    assert cenario.http.post(f"{URL}/{compra['id']}/enviar", headers=cenario.h_gerente).status_code == 409


def test_vendedor_nao_cria_compra(cenario):
    fornecedor = cenario.fabrica.fornecedor()
    r = cenario.http.post(
        URL,
        json={
            "fornecedor_id": fornecedor.id,
            "deposito_id": cenario.principal.id,
            "itens": [{"produto_id": cenario.produtos[0].id, "quantidade": 1, "custo_unitario": "1"}],
        },
        headers=cenario.h_vendedor,
    )
    assert r.status_code == 403
