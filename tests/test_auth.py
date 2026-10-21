from app.modelos.enums import Papel
from app.seguranca import gerar_hash_senha, validar_forca_senha, verificar_senha
from tests.conftest import SENHA_PADRAO


def test_hash_de_senha_confere_e_nao_guarda_texto():
    h = gerar_hash_senha("abc123XYZ!")
    assert "abc123XYZ!" not in h
    assert verificar_senha("abc123XYZ!", h)
    assert not verificar_senha("errada", h)
    assert gerar_hash_senha("abc123XYZ!") != h


def test_forca_de_senha():
    assert validar_forca_senha("curta1") == ["ter pelo menos 10 caracteres"]
    assert "misturar letras e números" in validar_forca_senha("somenteletras")
    assert "não conter o nome de usuário" in validar_forca_senha("maria12345678", "maria")
    assert validar_forca_senha("Cavalo-Bateria-42") == []


def test_login_devolve_token_e_cookie_httponly(fabrica, cliente_http):
    fabrica.usuario(Papel.VENDEDOR, "ana.vendas")
    r = cliente_http.post("/api/v1/auth/login", json={"usuario": "ANA.VENDAS", "senha": SENHA_PADRAO})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["usuario"]["papel"] == "vendedor"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie

    eu = cliente_http.get("/api/v1/auth/eu")
    assert eu.status_code == 200
    assert eu.json()["usuario"] == "ana.vendas"


def test_login_com_senha_errada_nao_revela_se_usuario_existe(fabrica, cliente_http):
    fabrica.usuario(Papel.VENDEDOR, "bruno")
    a = cliente_http.post("/api/v1/auth/login", json={"usuario": "bruno", "senha": "errada"})
    b = cliente_http.post("/api/v1/auth/login", json={"usuario": "ninguem", "senha": "errada"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_bloqueio_apos_varias_tentativas(fabrica, cliente_http):
    fabrica.usuario(Papel.VENDEDOR, "carla")
    for _ in range(5):
        cliente_http.post("/api/v1/auth/login", json={"usuario": "carla", "senha": "errada"})
    r = cliente_http.post("/api/v1/auth/login", json={"usuario": "carla", "senha": SENHA_PADRAO})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


def test_rotas_protegidas_exigem_autenticacao(cliente_http):
    for caminho in ("/api/v1/produtos", "/api/v1/pedidos", "/api/v1/relatorios/dashboard", "/api/v1/auth/eu"):
        assert cliente_http.get(caminho).status_code == 401


def test_token_adulterado_e_recusado(fabrica, cliente_http):
    usuario = fabrica.usuario(Papel.ADMIN)
    token = fabrica.cabecalho(usuario)["Authorization"]
    r = cliente_http.get("/api/v1/auth/eu", headers={"Authorization": token[:-3] + "abc"})
    assert r.status_code == 401


def test_trocar_senha_revoga_tokens_antigos(fabrica, cliente_http):
    usuario = fabrica.usuario(Papel.VENDEDOR, "duda")
    antigo = fabrica.cabecalho(usuario)
    r = cliente_http.post(
        "/api/v1/auth/trocar-senha",
        json={"senha_atual": SENHA_PADRAO, "nova_senha": "OutraSenha2026"},
        headers=antigo,
    )
    assert r.status_code == 200, r.text
    assert cliente_http.get("/api/v1/auth/eu", headers=antigo).status_code == 401
    novo = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert cliente_http.get("/api/v1/auth/eu", headers=novo).status_code == 200


def test_trocar_senha_recusa_senha_fraca(fabrica, cliente_http):
    usuario = fabrica.usuario(Papel.VENDEDOR, "edu")
    r = cliente_http.post(
        "/api/v1/auth/trocar-senha",
        json={"senha_atual": SENHA_PADRAO, "nova_senha": "aaaaaaaaaaaa"},
        headers=fabrica.cabecalho(usuario),
    )
    assert r.status_code == 422
    assert r.json()["erro"]["codigo"] == "senha_fraca"


def test_usuario_desativado_perde_acesso(fabrica, cliente_http):
    admin = fabrica.usuario(Papel.ADMIN)
    vendedor = fabrica.usuario(Papel.VENDEDOR)
    h = fabrica.cabecalho(vendedor)
    assert cliente_http.get("/api/v1/auth/eu", headers=h).status_code == 200
    r = cliente_http.patch(f"/api/v1/usuarios/{vendedor.id}", json={"ativo": False}, headers=fabrica.cabecalho(admin))
    assert r.status_code == 200
    assert cliente_http.get("/api/v1/auth/eu", headers=h).status_code == 401


def test_nao_permite_remover_ultimo_admin(fabrica, cliente_http):
    admin = fabrica.usuario(Papel.ADMIN)
    r = cliente_http.patch(f"/api/v1/usuarios/{admin.id}", json={"papel": "vendedor"}, headers=fabrica.cabecalho(admin))
    assert r.status_code == 422


def test_admin_cria_usuario_com_senha_inicial(fabrica, cliente_http):
    admin = fabrica.usuario(Papel.ADMIN)
    r = cliente_http.post(
        "/api/v1/usuarios",
        json={"nome": "Fernanda Estoque", "usuario": "fernanda", "papel": "estoquista"},
        headers=fabrica.cabecalho(admin),
    )
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["usuario"]["trocar_senha"] is True
    login = cliente_http.post("/api/v1/auth/login", json={"usuario": "fernanda", "senha": corpo["senha_inicial"]})
    assert login.status_code == 200


def test_cookie_nao_aceita_escrita_de_outra_origem(fabrica, cliente_http):
    fabrica.usuario(Papel.ADMIN, "chefe")
    cliente_http.post("/api/v1/auth/login", json={"usuario": "chefe", "senha": SENHA_PADRAO})
    r = cliente_http.post("/api/v1/categorias", json={"nome": "Invasora"}, headers={"Origin": "https://site-malicioso.example"})
    assert r.status_code == 403
    assert r.json()["erro"]["codigo"] == "origem_cruzada"
