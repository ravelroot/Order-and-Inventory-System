from decimal import Decimal

from app.modelos import Produto
from app.servicos.estoque import recalcular_custo_medio


def _saldos(c, produto):
    return {s["deposito"]: s for s in c.http.get(f"/api/v1/produtos/{produto.id}/saldos", headers=c.h_admin).json()}


def test_custo_medio_ponderado():
    p = Produto(custo_medio=Decimal("10.00"))
    recalcular_custo_medio(p, estoque_anterior=10, quantidade=30, custo=Decimal("14.00"))
    assert p.custo_medio == Decimal("13.00")
    vazio = Produto(custo_medio=Decimal("0"))
    recalcular_custo_medio(vazio, estoque_anterior=0, quantidade=5, custo=Decimal("7.33"))
    assert vazio.custo_medio == Decimal("7.33")


def test_entrada_atualiza_saldo_e_custo(cenario):
    p = cenario.produtos[0]
    r = cenario.http.post(
        "/api/v1/estoque/entradas",
        json={"produto_id": p.id, "deposito_id": cenario.principal.id, "quantidade": 50, "custo_unitario": "80.00"},
        headers=cenario.h_estoquista,
    )
    assert r.status_code == 201
    assert r.json()["saldo_apos"] == 100
    produto = cenario.http.get(f"/api/v1/produtos/{p.id}", headers=cenario.h_admin).json()
    assert produto["custo_medio"] == 70.0
    assert produto["estoque_total"] == 100


def test_vendedor_nao_lanca_entrada(cenario):
    r = cenario.http.post(
        "/api/v1/estoque/entradas",
        json={"produto_id": cenario.produtos[0].id, "deposito_id": cenario.principal.id, "quantidade": 1},
        headers=cenario.h_vendedor,
    )
    assert r.status_code == 403


def test_ajuste_por_contagem(cenario):
    p = cenario.produtos[0]
    corpo = {"produto_id": p.id, "deposito_id": cenario.principal.id, "quantidade_contada": 47, "motivo": "Inventário mensal"}
    r = cenario.http.post("/api/v1/estoque/ajustes", json=corpo, headers=cenario.h_estoquista)
    assert r.status_code == 200
    assert r.json()["tipo"] == "AJUSTE_NEGATIVO" and r.json()["quantidade"] == 3
    assert _saldos(cenario, p)["CD-SP"]["quantidade"] == 47
    repetido = cenario.http.post("/api/v1/estoque/ajustes", json=corpo, headers=cenario.h_estoquista)
    assert repetido.status_code == 200 and repetido.json() is None


def test_ajuste_nao_fica_abaixo_do_reservado(cenario):
    p = cenario.produtos[0]
    pedido = cenario.http.post(
        "/api/v1/pedidos",
        json={
            "cliente_id": cenario.cliente.id,
            "deposito_id": cenario.principal.id,
            "itens": [{"produto_id": p.id, "quantidade": 20}],
        },
        headers=cenario.h_vendedor,
    ).json()
    cenario.http.post(f"/api/v1/pedidos/{pedido['id']}/confirmar", headers=cenario.h_vendedor)
    r = cenario.http.post(
        "/api/v1/estoque/ajustes",
        json={"produto_id": p.id, "deposito_id": cenario.principal.id, "quantidade_contada": 10, "motivo": "Contagem"},
        headers=cenario.h_estoquista,
    )
    assert r.status_code == 422
    assert r.json()["erro"]["detalhes"]["reservado"] == 20


def test_transferencia_entre_depositos(cenario):
    p = cenario.produtos[1]
    r = cenario.http.post(
        "/api/v1/estoque/transferencias",
        json={
            "produto_id": p.id,
            "deposito_origem_id": cenario.principal.id,
            "deposito_destino_id": cenario.filial.id,
            "quantidade": 12,
        },
        headers=cenario.h_estoquista,
    )
    assert r.status_code == 201, r.text
    assert [m["tipo"] for m in r.json()] == ["TRANSFERENCIA_SAIDA", "TRANSFERENCIA_ENTRADA"]
    saldos = _saldos(cenario, p)
    assert saldos["CD-SP"]["quantidade"] == 38
    assert saldos["CD-RJ"]["quantidade"] == 12


def test_transferencia_sem_saldo(cenario):
    r = cenario.http.post(
        "/api/v1/estoque/transferencias",
        json={
            "produto_id": cenario.produtos[1].id,
            "deposito_origem_id": cenario.filial.id,
            "deposito_destino_id": cenario.principal.id,
            "quantidade": 1,
        },
        headers=cenario.h_estoquista,
    )
    assert r.status_code == 409
    assert r.json()["erro"]["codigo"] == "estoque_insuficiente"


def test_transferencia_para_o_mesmo_deposito_e_invalida(cenario):
    r = cenario.http.post(
        "/api/v1/estoque/transferencias",
        json={
            "produto_id": cenario.produtos[1].id,
            "deposito_origem_id": cenario.principal.id,
            "deposito_destino_id": cenario.principal.id,
            "quantidade": 1,
        },
        headers=cenario.h_estoquista,
    )
    assert r.status_code == 422


def test_listar_saldos_e_movimentacoes_com_filtros(cenario):
    r = cenario.http.get("/api/v1/estoque/saldos", params={"deposito_id": cenario.principal.id}, headers=cenario.h_vendedor)
    assert r.json()["total"] == 3
    r = cenario.http.get("/api/v1/estoque/movimentacoes", params={"tipo": "ENTRADA"}, headers=cenario.h_vendedor)
    assert r.json()["total"] == 3
    assert all(m["tipo"] == "ENTRADA" for m in r.json()["itens"])


def test_banco_impede_saldo_negativo(sessao, fabrica):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.modelos import SaldoEstoque

    categoria = fabrica.categoria()
    produto = fabrica.produto(categoria)
    deposito = fabrica.deposito()
    sessao.add(SaldoEstoque(produto_id=produto.id, deposito_id=deposito.id, quantidade=5, reservado=6))
    with pytest.raises(IntegrityError):
        sessao.commit()
