import os

os.environ["AMBIENTE"] = "teste"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CHAVE_SECRETA"] = "chave-de-teste-" + "x" * 40
os.environ["CRIAR_TABELAS"] = "false"
os.environ["LIMITE_REQUISICOES_MINUTO"] = "0"
os.environ["DOCS_PUBLICAS"] = "true"

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, obter_sessao
from app.main import app
from app.modelos import Categoria, Cliente, Deposito, Fornecedor, Produto, Usuario
from app.modelos.enums import Papel, TipoPessoa
from app.seguranca import criar_token, gerar_hash_senha, limitador_login
from app.utils.documentos import completar_cpf

URL_TESTE = os.environ.get("TEST_DATABASE_URL", "")
EH_POSTGRES = URL_TESTE.startswith("postgresql")
SENHA_PADRAO = "SenhaForte123"


def _criar_engine():
    if EH_POSTGRES:
        return create_engine(URL_TESTE.replace("postgresql://", "postgresql+psycopg://", 1), pool_size=10, max_overflow=25)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    return engine


engine_teste = _criar_engine()
FabricaSessao = sessionmaker(bind=engine_teste, autoflush=False, expire_on_commit=False)


def pytest_collection_modifyitems(config, items):
    if EH_POSTGRES:
        return
    pular = pytest.mark.skip(reason="precisa de PostgreSQL (defina TEST_DATABASE_URL)")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(pular)


@pytest.fixture
def banco():
    Base.metadata.drop_all(engine_teste)
    Base.metadata.create_all(engine_teste)
    yield engine_teste
    Base.metadata.drop_all(engine_teste)


@pytest.fixture
def sessao(banco):
    s = FabricaSessao()
    yield s
    s.close()


@pytest.fixture
def cliente_http(banco):
    def _sessao():
        s = FabricaSessao()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[obter_sessao] = _sessao
    limitador_login.limpar()
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


class Fabrica:
    def __init__(self, sessao):
        self.s = sessao
        self._n = 0

    def _seq(self) -> int:
        self._n += 1
        return self._n

    def usuario(self, papel: Papel = Papel.ADMIN, usuario: str | None = None, senha: str = SENHA_PADRAO) -> Usuario:
        u = Usuario(
            nome=f"Pessoa {papel.value.title()}",
            usuario=usuario or f"{papel.value}{self._seq()}",
            papel=papel,
            senha_hash=gerar_hash_senha(senha),
        )
        self.s.add(u)
        self.s.commit()
        return u

    def cabecalho(self, usuario: Usuario) -> dict:
        token, _ = criar_token(usuario.id, usuario.papel.value, usuario.versao_token)
        return {"Authorization": f"Bearer {token}"}

    def categoria(self, nome: str | None = None) -> Categoria:
        c = Categoria(nome=nome or f"Categoria {self._seq()}")
        self.s.add(c)
        self.s.commit()
        return c

    def fornecedor(self) -> Fornecedor:
        f = Fornecedor(razao_social=f"Fornecedor Exemplo {self._seq()} Ltda", cnpj=f"{11222333000181 + self._n * 100}"[:14])
        self.s.add(f)
        self.s.commit()
        return f

    def deposito(self, codigo: str | None = None) -> Deposito:
        d = Deposito(codigo=codigo or f"DP{self._seq()}", nome="Depósito de teste", uf="SP")
        self.s.add(d)
        self.s.commit()
        return d

    def produto(self, categoria: Categoria, preco: str = "100.00", minimo: int = 0, custo: str = "60.00", **extra) -> Produto:
        n = self._seq()
        p = Produto(
            sku=f"SKU-{n:04d}",
            nome=f"Produto de teste {n}",
            categoria_id=categoria.id,
            preco_venda=Decimal(preco),
            custo_medio=Decimal(custo),
            estoque_minimo=minimo,
            **extra,
        )
        self.s.add(p)
        self.s.commit()
        return p

    def cliente(self, limite: str = "0") -> Cliente:
        self._clientes = getattr(self, "_clientes", 0) + 1
        n = self._seq()
        c = Cliente(
            tipo_pessoa=TipoPessoa.FISICA,
            nome=f"Cliente Fictício {n}",
            documento="52998224725" if self._clientes == 1 else completar_cpf(f"{n:09d}"),
            cidade="Campinas",
            uf="SP",
            limite_credito=Decimal(limite),
        )
        self.s.add(c)
        self.s.commit()
        return c


@pytest.fixture
def fabrica(sessao):
    return Fabrica(sessao)


@pytest.fixture
def cenario(fabrica, cliente_http):
    admin = fabrica.usuario(Papel.ADMIN, "admin")
    vendedor = fabrica.usuario(Papel.VENDEDOR, "vendedor")
    estoquista = fabrica.usuario(Papel.ESTOQUISTA, "estoquista")
    gerente = fabrica.usuario(Papel.GERENTE, "gerente")
    categoria = fabrica.categoria("Informática")
    principal = fabrica.deposito("CD-SP")
    filial = fabrica.deposito("CD-RJ")
    produtos = [fabrica.produto(categoria, preco=p) for p in ("100.00", "250.00", "19.90")]
    cliente = fabrica.cliente()
    h_admin = fabrica.cabecalho(admin)
    for p in produtos:
        r = cliente_http.post(
            "/api/v1/estoque/entradas",
            json={
                "produto_id": p.id,
                "deposito_id": principal.id,
                "quantidade": 50,
                "custo_unitario": "60.00",
                "motivo": "Carga inicial",
            },
            headers=h_admin,
        )
        assert r.status_code == 201, r.text

    class Cenario:
        pass

    c = Cenario()
    c.http = cliente_http
    c.fabrica = fabrica
    c.admin, c.vendedor, c.estoquista, c.gerente = admin, vendedor, estoquista, gerente
    c.h_admin = h_admin
    c.h_vendedor = fabrica.cabecalho(vendedor)
    c.h_estoquista = fabrica.cabecalho(estoquista)
    c.h_gerente = fabrica.cabecalho(gerente)
    c.categoria, c.principal, c.filial, c.produtos, c.cliente = categoria, principal, filial, produtos, cliente
    return c
