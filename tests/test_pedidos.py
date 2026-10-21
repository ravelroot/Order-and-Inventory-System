from decimal import Decimal

import pytest

from app.servicos.pedidos import calcular_total_item

URL = "/api/v1/pedidos"


def _criar(c, itens, headers=None, **extra):
    corpo = {"cliente_id": c.cliente.id, "deposito_id": c.principal.id, "itens": itens, **extra}
    r = c.http.post(URL, json=corpo, headers=headers or c.h_vendedor)
    assert r.status_code == 201, r.text
    return r.json()


def _saldo(c, produto, deposito=None):
    deposito = deposito or c.principal
    saldos = c.http.get(f"/api/v1/produtos/{produto.id}/saldos", headers=c.h_admin).json()
    return next(s for s in saldos if s["deposito_id"] == deposito.id)


def _acao(c, pedido_id, acao, headers, json=None):
    return c.http.post(f"{URL}/{pedido_id}/{acao}", json=json, headers=headers)


@pytest.mark.parametrize(
    ("quantidade", "preco", "desconto", "esperado"),
    [(1, "100.00", "0", "100.00"), (3, "19.90", "10", "53.73"), (7, "0.15", "33.33", "0.70")],
)
def test_calculo_do_item_arredonda_meio_para_cima(quantidade, preco, desconto, esperado):
    assert calcular_total_item(quantidade, Decimal(preco), Decimal(desconto)) == Decimal(esperado)


def test_criar_pedido_calcula_totais_e_numera(cenario):
    p1, p2, _ = cenario.produtos
    pedido = _criar(
        cenario,
        [{"produto_id": p1.id, "quantidade": 2, "desconto_percentual": 10}, {"produto_id": p2.id, "quantidade": 1}],
        frete="15.50",
    )
    assert pedido["status"] == "RASCUNHO"
    assert pedido["numero"].startswith("PV-")
    assert pedido["subtotal"] == 450.0
    assert pedido["desconto_total"] == 20.0
    assert pedido["total"] == 445.5
    assert "confirmar" in pedido["acoes_disponiveis"]
    assert pedido["historico"][0]["para_status"] == "RASCUNHO"


def test_ciclo_completo_movimenta_estoque(cenario):
    p1 = cenario.produtos[0]
    pedido = _criar(cenario, [{"produto_id": p1.id, "quantidade": 5}])
    pid = pedido["id"]

    r = _acao(cenario, pid, "confirmar", cenario.h_vendedor)
    assert r.status_code == 200, r.text
    saldo = _saldo(cenario, p1)
    assert (saldo["quantidade"], saldo["reservado"], saldo["disponivel"]) == (50, 5, 45)

    assert _acao(cenario, pid, "separar", cenario.h_estoquista).status_code == 200
    assert _acao(cenario, pid, "faturar", cenario.h_estoquista).status_code == 200
    saldo = _saldo(cenario, p1)
    assert (saldo["quantidade"], saldo["reservado"]) == (45, 0)

    r = _acao(cenario, pid, "enviar", cenario.h_estoquista, {"codigo_rastreio": "BR123456789"})
    assert r.status_code == 200
    r = _acao(cenario, pid, "entregar", cenario.h_estoquista)
    final = r.json()
    assert final["status"] == "ENTREGUE"
    assert [h["para_status"] for h in final["historico"]] == [
        "RASCUNHO",
        "CONFIRMADO",
        "SEPARADO",
        "FATURADO",
        "ENVIADO",
        "ENTREGUE",
    ]
    assert final["acoes_disponiveis"] == []

    movs = cenario.http.get(f"/api/v1/produtos/{p1.id}/movimentacoes", headers=cenario.h_admin).json()["itens"]
    tipos = [m["tipo"] for m in movs]
    assert tipos[:2] == ["SAIDA", "RESERVA"]


def test_confirmar_sem_estoque_e_atomico(cenario):
    p1, p2, _ = cenario.produtos
    pedido = _criar(cenario, [{"produto_id": p1.id, "quantidade": 10}, {"produto_id": p2.id, "quantidade": 51}])
    r = _acao(cenario, pedido["id"], "confirmar", cenario.h_vendedor)
    assert r.status_code == 409
    erro = r.json()["erro"]
    assert erro["codigo"] == "estoque_insuficiente"
    assert erro["detalhes"][0]["produto_id"] == p2.id
    assert erro["detalhes"][0]["disponivel"] == 50
    assert _saldo(cenario, p1)["reservado"] == 0


def test_reserva_impede_vender_o_mesmo_estoque_duas_vezes(cenario):
    p1 = cenario.produtos[0]
    a = _criar(cenario, [{"produto_id": p1.id, "quantidade": 30}])
    b = _criar(cenario, [{"produto_id": p1.id, "quantidade": 30}])
    assert _acao(cenario, a["id"], "confirmar", cenario.h_vendedor).status_code == 200
    assert _acao(cenario, b["id"], "confirmar", cenario.h_vendedor).status_code == 409


def test_cancelar_confirmado_libera_reserva(cenario):
    p1 = cenario.produtos[0]
    pedido = _criar(cenario, [{"produto_id": p1.id, "quantidade": 8}])
    _acao(cenario, pedido["id"], "confirmar", cenario.h_vendedor)
    r = _acao(cenario, pedido["id"], "cancelar", cenario.h_vendedor, {"motivo": "Cliente desistiu"})
    assert r.status_code == 200
    assert r.json()["motivo_cancelamento"] == "Cliente desistiu"
    assert _saldo(cenario, p1)["reservado"] == 0


def test_cancelar_faturado_estorna_e_exige_gestor(cenario):
    p1 = cenario.produtos[0]
    pedido = _criar(cenario, [{"produto_id": p1.id, "quantidade": 4}])
    pid = pedido["id"]
    _acao(cenario, pid, "confirmar", cenario.h_vendedor)
    _acao(cenario, pid, "separar", cenario.h_estoquista)
    _acao(cenario, pid, "faturar", cenario.h_estoquista)
    assert _saldo(cenario, p1)["quantidade"] == 46

    negado = _acao(cenario, pid, "cancelar", cenario.h_vendedor, {"motivo": "Devolução total"})
    assert negado.status_code == 403
    ok = _acao(cenario, pid, "cancelar", cenario.h_gerente, {"motivo": "Devolução total"})
    assert ok.status_code == 200
    assert _saldo(cenario, p1)["quantidade"] == 50


def test_transicao_invalida(cenario):
    pedido = _criar(cenario, [{"produto_id": cenario.produtos[0].id, "quantidade": 1}])
    r = _acao(cenario, pedido["id"], "faturar", cenario.h_estoquista)
    assert r.status_code == 409
    assert r.json()["erro"]["codigo"] == "transicao_invalida"


def test_vendedor_nao_separa_e_estoquista_nao_cria(cenario):
    pedido = _criar(cenario, [{"produto_id": cenario.produtos[0].id, "quantidade": 1}])
    _acao(cenario, pedido["id"], "confirmar", cenario.h_vendedor)
    assert _acao(cenario, pedido["id"], "separar", cenario.h_vendedor).status_code == 403
    r = cenario.http.post(
        URL,
        json={
            "cliente_id": cenario.cliente.id,
            "deposito_id": cenario.principal.id,
            "itens": [{"produto_id": cenario.produtos[0].id, "quantidade": 1}],
        },
        headers=cenario.h_estoquista,
    )
    assert r.status_code == 403


def test_vendedor_nao_mexe_em_pedido_de_outro_vendedor(cenario):
    from app.modelos.enums import Papel

    outro = cenario.fabrica.usuario(Papel.VENDEDOR, "outro.vendedor")
    pedido = _criar(cenario, [{"produto_id": cenario.produtos[0].id, "quantidade": 1}])
    h = cenario.fabrica.cabecalho(outro)
    assert _acao(cenario, pedido["id"], "confirmar", h).status_code == 403
    r = cenario.http.patch(f"{URL}/{pedido['id']}", json={"frete": "10"}, headers=h)
    assert r.status_code == 409


def test_limite_de_desconto_por_perfil(cenario):
    corpo = {
        "cliente_id": cenario.cliente.id,
        "deposito_id": cenario.principal.id,
        "itens": [{"produto_id": cenario.produtos[0].id, "quantidade": 1, "desconto_percentual": 15}],
    }
    assert cenario.http.post(URL, json=corpo, headers=cenario.h_vendedor).status_code == 422
    assert cenario.http.post(URL, json=corpo, headers=cenario.h_gerente).status_code == 201


def test_idempotencia_nao_duplica_pedido(cenario):
    corpo = {
        "cliente_id": cenario.cliente.id,
        "deposito_id": cenario.principal.id,
        "itens": [{"produto_id": cenario.produtos[0].id, "quantidade": 1}],
    }
    h = {**cenario.h_vendedor, "Idempotency-Key": "pedido-abc-123"}
    a = cenario.http.post(URL, json=corpo, headers=h)
    b = cenario.http.post(URL, json=corpo, headers=h)
    assert a.status_code == 201
    assert b.status_code == 200
    assert b.headers["idempotent-replay"] == "true"
    assert a.json()["id"] == b.json()["id"]
    assert cenario.http.get(URL, headers=cenario.h_admin).json()["total"] == 1


def test_produto_repetido_no_pedido_e_recusado(cenario):
    p = cenario.produtos[0].id
    corpo = {
        "cliente_id": cenario.cliente.id,
        "deposito_id": cenario.principal.id,
        "itens": [{"produto_id": p, "quantidade": 1}, {"produto_id": p, "quantidade": 2}],
    }
    assert cenario.http.post(URL, json=corpo, headers=cenario.h_vendedor).status_code == 422


def test_editar_itens_do_rascunho(cenario):
    p1, p2, p3 = cenario.produtos
    pedido = _criar(cenario, [{"produto_id": p1.id, "quantidade": 1}])
    r = cenario.http.put(
        f"{URL}/{pedido['id']}/itens",
        json={"itens": [{"produto_id": p2.id, "quantidade": 2}, {"produto_id": p3.id, "quantidade": 10}]},
        headers=cenario.h_vendedor,
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 699.0
    _acao(cenario, pedido["id"], "confirmar", cenario.h_vendedor)
    r = cenario.http.put(
        f"{URL}/{pedido['id']}/itens", json={"itens": [{"produto_id": p1.id, "quantidade": 1}]}, headers=cenario.h_vendedor
    )
    assert r.status_code == 409


def test_limite_de_credito(cenario):
    cliente = cenario.fabrica.cliente(limite="300.00")
    corpo = {
        "cliente_id": cliente.id,
        "deposito_id": cenario.principal.id,
        "itens": [{"produto_id": cenario.produtos[1].id, "quantidade": 2}],
    }
    pedido = cenario.http.post(URL, json=corpo, headers=cenario.h_vendedor).json()
    r = _acao(cenario, pedido["id"], "confirmar", cenario.h_vendedor)
    assert r.status_code == 422
    assert r.json()["erro"]["codigo"] == "limite_credito"
    r = _acao(cenario, pedido["id"], "confirmar", cenario.h_gerente)
    assert r.status_code == 200
    assert "liberado pela gestão" in r.json()["historico"][-1]["observacao"]


def test_filtros_da_listagem(cenario):
    a = _criar(cenario, [{"produto_id": cenario.produtos[0].id, "quantidade": 1}])
    _criar(cenario, [{"produto_id": cenario.produtos[1].id, "quantidade": 1}])
    _acao(cenario, a["id"], "confirmar", cenario.h_vendedor)
    r = cenario.http.get(URL, params={"status": "CONFIRMADO"}, headers=cenario.h_admin).json()
    assert r["total"] == 1 and r["itens"][0]["id"] == a["id"]
    r = cenario.http.get(URL, params={"q": a["numero"]}, headers=cenario.h_admin).json()
    assert r["total"] == 1
    r = cenario.http.get(URL, params={"meus": True}, headers=cenario.h_vendedor).json()
    assert r["total"] == 2


def test_exportar_csv(cenario):
    _criar(cenario, [{"produto_id": cenario.produtos[0].id, "quantidade": 1}])
    r = cenario.http.get(f"{URL}/exportar", headers=cenario.h_admin)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    linhas = r.text.lstrip("﻿").splitlines()
    assert linhas[0].startswith("Número;Status")
    assert len(linhas) == 2
