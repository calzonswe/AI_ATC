from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from .base import Base

engine = None
async_session_factory = None


def init_db(dsn: str, echo: bool = False):
    global engine, async_session_factory
    engine = create_async_engine(dsn, echo=echo, pool_size=10, max_overflow=20)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with async_session_factory() as session:
        yield session


async def create_tables():
    if engine is None:
        raise RuntimeError("Database not initialized.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    if engine is None:
        raise RuntimeError("Database not initialized.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
