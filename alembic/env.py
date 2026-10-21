from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app import modelos
from app.config import obter_config
from app.database import Base, DataHoraUTC, DecimalFixo

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", obter_config().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def render_item(tipo, objeto, autogen_context):
    if tipo == "type" and isinstance(objeto, DecimalFixo):
        autogen_context.imports.add("from app.database import DecimalFixo")
        return f"DecimalFixo({objeto.casas})"
    if tipo == "type" and isinstance(objeto, DataHoraUTC):
        autogen_context.imports.add("from app.database import DataHoraUTC")
        return "DataHoraUTC()"
    return False


def _opcoes(url: str) -> dict:
    return {
        "target_metadata": target_metadata,
        "render_item": render_item,
        "render_as_batch": url.startswith("sqlite"),
        "compare_type": True,
    }


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **_opcoes(url))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conectavel = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with conectavel.connect() as conexao:
        context.configure(connection=conexao, **_opcoes(str(conectavel.url)))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
