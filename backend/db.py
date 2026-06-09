from sqlmodel import SQLModel, Session, create_engine

from core.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, echo=False)
    return _engine


def init_db():
    from models.agent import Agent, AgentVersion  # noqa: F401 — registers tables
    SQLModel.metadata.create_all(get_engine())


def get_session():
    with Session(get_engine()) as session:
        yield session
