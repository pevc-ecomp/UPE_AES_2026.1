import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from db import get_engine, init_db
from routers import agents

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())


def _seed_default_agent() -> None:
    from sqlmodel import Session, select
    from agents.article_evaluator import DEFAULT_SYSTEM_PROMPT, SEED_VERSION_NAME
    from models.agent import Agent, AgentVersion

    log = logging.getLogger(__name__)

    with Session(get_engine()) as session:
        agent = session.exec(select(Agent).where(Agent.name == "article-evaluator")).first()

        if not agent:
            agent = Agent(
                name="article-evaluator",
                description="Avalia a relevância de um artigo científico para um protocolo de pesquisa.",
            )
            session.add(agent)
            session.flush()
            log.info("Default agent 'article-evaluator' created.")

        existing_version = session.exec(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent.id)
            .where(AgentVersion.version_name == SEED_VERSION_NAME)
        ).first()

        if not existing_version:
            version = AgentVersion(
                agent_id=agent.id,
                version_name=SEED_VERSION_NAME,
                version_description=(
                    "Suporte a Protocolo de Pesquisa completo: critérios de exclusão "
                    "eliminatórios, critérios de inclusão com lógica configurável "
                    "(ANY/ALL/expressão), e objetivos gerais e específicos da pesquisa."
                ),
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                temperature=0.1,
                model_primary=settings.ollama_model_primary,
                model_fallback=settings.ollama_model_fallback,
                author="system",
            )
            session.add(version)
            session.flush()
            agent.active_version_id = version.id
            session.add(agent)
            session.commit()
            log.info("Seeded version '%s' for agent 'article-evaluator'.", SEED_VERSION_NAME)
        else:
            log.info("Version '%s' already exists, skipping seed.", SEED_VERSION_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_default_agent()
    yield


app = FastAPI(
    title="Research Assistant API",
    description="Backend de apoio à revisão de literatura científica.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/agents", tags=["agents"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
