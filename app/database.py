from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import BigInteger, DateTime, MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import obter_config

CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO_NOMES)


def agora_utc() -> datetime:
    return datetime.now(UTC)


class DecimalFixo(TypeDecorator):
    impl = BigInteger
    cache_ok = True

    def __init__(self, casas: int = 2, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.casas = casas
        self.fator = Decimal(10) ** casas
        self.quantum = Decimal(1).scaleb(-casas)

    def process_bind_param(self, valor, dialect):
        if valor is None:
            return None
        decimal = Decimal(str(valor)).quantize(self.quantum, rounding=ROUND_HALF_UP)
        return int(decimal * self.fator)

    def process_result_value(self, valor, dialect):
        if valor is None:
            return None
        return (Decimal(int(valor)) / self.fator).quantize(self.quantum)

    @property
    def python_type(self):
        return Decimal


class Dinheiro(DecimalFixo):
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(2, *args, **kwargs)


class DataHoraUTC(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, valor, dialect):
        if valor is None:
            return None
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=UTC)
        return valor.astimezone(UTC)

    def process_result_value(self, valor, dialect):
        if valor is None:
            return None
        if valor.tzinfo is None:
            return valor.replace(tzinfo=UTC)
        return valor.astimezone(UTC)


def criar_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _pragmas(conexao, _):
            cursor = conexao.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10, pool_recycle=1800)


_config = obter_config()
if _config.eh_sqlite and ":memory:" not in _config.database_url:
    from app.config import PASTA_DADOS

    PASTA_DADOS.mkdir(parents=True, exist_ok=True)

engine = criar_engine(_config.database_url)
SessaoLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obter_sessao() -> Iterator[Session]:
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()
