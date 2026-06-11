from sqlmodel import SQLModel, Session, create_engine

from core.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, echo=False)
    return _engine


def _migrate_agent_type_column() -> None:
    """Add the agent_type column to pre-existing 'agent' tables (no Alembic in this project)."""
    engine = get_engine()
    with engine.connect() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(agent)").fetchall()
        col_names = {c[1] for c in cols}
        if "agent_type" not in col_names:
            conn.exec_driver_sql(
                "ALTER TABLE agent ADD COLUMN agent_type TEXT DEFAULT 'general'"
            )
            conn.commit()


def init_db():
    from models.agent import Agent, AgentVersion  # noqa: F401 — registers tables
    SQLModel.metadata.create_all(get_engine())
    _migrate_agent_type_column()


def get_session():
    with Session(get_engine()) as session:
        yield session
