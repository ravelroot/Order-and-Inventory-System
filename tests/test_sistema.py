def test_saude_nao_expoe_detalhes(cliente_http):
    r = cliente_http.get("/api/saude")
    assert r.status_code == 200
    assert set(r.json()) == {"status", "versao"}


def test_cabecalhos_de_seguranca(cliente_http):
    r = cliente_http.get("/login")
    assert r.status_code == 200
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "x-request-id" in r.headers


def test_respostas_da_api_nao_vao_para_cache(cenario):
    r = cenario.http.get("/api/v1/produtos", headers=cenario.h_vendedor)
    assert r.headers["cache-control"] == "no-store"


def test_painel_e_arquivos_estaticos(cliente_http):
    assert cliente_http.get("/").status_code == 200
    assert cliente_http.get("/static/js/app.js").status_code == 200
    assert cliente_http.get("/static/fonts/archivo.woff2").status_code == 200


def test_erro_padronizado_e_traduzido(cenario):
    r = cenario.http.get("/api/v1/pedidos", params={"status": "INEXISTENTE"}, headers=cenario.h_admin)
    assert r.status_code == 422
    erro = r.json()["erro"]
    assert erro["codigo"] == "validacao"
    assert erro["detalhes"][0]["mensagem"].startswith("Valor inválido")

    r = cenario.http.get("/api/v1/produtos/999999", headers=cenario.h_admin)
    assert r.status_code == 404
    assert r.json()["erro"]["codigo"] == "nao_encontrado"


def test_documentacao_openapi(cliente_http):
    esquema = cliente_http.get("/openapi.json").json()
    assert "/api/v1/pedidos/{pedido_id}/confirmar" in esquema["paths"]
    assert cliente_http.get("/docs").status_code == 200


def test_fluxo_de_compra_venda_mantem_livro_coerente(cenario, sessao):
    from sqlalchemy import select

    from app.modelos import MovimentacaoEstoque, SaldoEstoque

    p = cenario.produtos[0]
    pedido = cenario.http.post(
        "/api/v1/pedidos",
        json={
            "cliente_id": cenario.cliente.id,
            "deposito_id": cenario.principal.id,
            "itens": [{"produto_id": p.id, "quantidade": 7}],
        },
        headers=cenario.h_gerente,
    ).json()
    for acao in ("confirmar", "separar", "faturar"):
        cenario.http.post(f"/api/v1/pedidos/{pedido['id']}/{acao}", headers=cenario.h_gerente)
    cenario.http.post(
        f"/api/v1/pedidos/{pedido['id']}/cancelar", json={"motivo": "Devolução de teste"}, headers=cenario.h_gerente
    )

    sessao.expire_all()
    saldo = sessao.get(SaldoEstoque, (p.id, cenario.principal.id))
    ultima = sessao.scalars(
        select(MovimentacaoEstoque)
        .where(MovimentacaoEstoque.produto_id == p.id, MovimentacaoEstoque.deposito_id == cenario.principal.id)
        .order_by(MovimentacaoEstoque.id.desc())
    ).first()
    assert (saldo.quantidade, saldo.reservado) == (50, 0)
    assert (ultima.saldo_apos, ultima.reservado_apos, ultima.tipo.value) == (50, 0, "ESTORNO")
