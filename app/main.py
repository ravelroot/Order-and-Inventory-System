import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app import modelos
from app.config import PASTA_DADOS, PASTA_WEB, obter_config
from app.database import Base, SessaoLocal, engine
from app.erros import registrar_tratadores
from app.middleware import SegurancaMiddleware
from app.modelos import Usuario
from app.modelos.enums import Papel
from app.rotas import auth, catalogo, clientes, compras, estoque, pedidos, relatorios, usuarios
from app.seguranca import gerar_hash_senha, gerar_senha_aleatoria

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


def garantir_admin() -> None:
    config = obter_config()
    with SessaoLocal() as sessao:
        if sessao.scalars(select(Usuario.id).limit(1)).first() is not None:
            return
        senha = config.admin_senha or gerar_senha_aleatoria()
        sessao.add(
            Usuario(
                nome="Administrador",
                usuario=config.admin_usuario,
                papel=Papel.ADMIN,
                senha_hash=gerar_hash_senha(senha),
                trocar_senha=not config.admin_senha,
            )
        )
        sessao.commit()
        if not config.admin_senha:
            PASTA_DADOS.mkdir(parents=True, exist_ok=True)
            arquivo = PASTA_DADOS / "senha_inicial_admin.txt"
            arquivo.write_text(f"usuario: {config.admin_usuario}\nsenha: {senha}\n", encoding="utf-8")
            log.warning("Usuário '%s' criado. Senha inicial gravada em %s", config.admin_usuario, arquivo.name)


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    config = obter_config()
    if config.criar_tabelas:
        Base.metadata.create_all(engine)
    if config.ambiente != "teste":
        garantir_admin()
    yield
    engine.dispose()


def criar_app() -> FastAPI:
    config = obter_config()
    docs = config.docs_publicas
    app = FastAPI(
        title=config.nome_app,
        version=config.versao,
        description=(
            "API de pedidos de venda, compras e controle de estoque multi-depósito. "
            "Autentique em **POST /api/v1/auth/login** e use o `access_token` como Bearer."
        ),
        lifespan=ciclo_de_vida,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    registrar_tratadores(app)
    app.add_middleware(SegurancaMiddleware)
    if config.cors_origens:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origens,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    api = APIRouter(prefix="/api/v1")
    for router in (
        auth.router,
        usuarios.router,
        catalogo.categorias,
        catalogo.fornecedores,
        catalogo.produtos,
        estoque.depositos,
        estoque.router,
        clientes.router,
        pedidos.router,
        compras.router,
        relatorios.router,
        relatorios.auditoria_router,
    ):
        api.include_router(router)
    app.include_router(api)
    app.include_router(relatorios.saude_router, prefix="/api")

    app.mount("/static", StaticFiles(directory=PASTA_WEB), name="static")

    @app.get("/", include_in_schema=False)
    def painel():
        return FileResponse(PASTA_WEB / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/login", include_in_schema=False)
    def tela_login():
        return FileResponse(PASTA_WEB / "login.html", headers={"Cache-Control": "no-cache"})

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return RedirectResponse("/static/img/icone.svg")

    return app


app = criar_app()
