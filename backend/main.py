import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from db import get_engine, init_db
from routers import agents

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())


def _seed_agent(
    *,
    name: str,
    agent_type: str,
    description: str,
    seed_version_name: str,
    version_description: str,
    system_prompt: str,
    temperature: float,
    model_primary: str,
    model_fallback: str,
    provider: str = "ollama",
) -> None:
    from sqlmodel import Session, select
    from models.agent import Agent, AgentVersion

    log = logging.getLogger(__name__)

    with Session(get_engine()) as session:
        agent = session.exec(select(Agent).where(Agent.name == name)).first()

        if not agent:
            agent = Agent(name=name, description=description, agent_type=agent_type)
            session.add(agent)
            session.flush()
            log.info("Default agent '%s' created.", name)
        elif agent.agent_type != agent_type:
            # Backfill agent_type for agents created before this field existed
            agent.agent_type = agent_type
            session.add(agent)

        existing_version = session.exec(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent.id)
            .where(AgentVersion.version_name == seed_version_name)
        ).first()

        if not existing_version:
            version = AgentVersion(
                agent_id=agent.id,
                version_name=seed_version_name,
                version_description=version_description,
                system_prompt=system_prompt,
                temperature=temperature,
                provider=provider,
                model_primary=model_primary,
                model_fallback=model_fallback,
                author="system",
            )
            session.add(version)
            session.flush()
            agent.active_version_id = version.id
            session.add(agent)
            session.commit()
            log.info("Seeded version '%s' for agent '%s'.", seed_version_name, name)
        else:
            session.commit()
            log.info("Version '%s' already exists for agent '%s', skipping seed.", seed_version_name, name)


def _seed_default_agents() -> None:
    from agents.article_evaluator import (
        DEFAULT_SYSTEM_PROMPT as ARTICLE_EVALUATOR_PROMPT,
        SEED_VERSION_NAME as ARTICLE_EVALUATOR_VERSION,
    )
    from agents.claude_article_evaluator import (
        DEFAULT_SYSTEM_PROMPT as CLAUDE_ARTICLE_EVALUATOR_PROMPT,
        SEED_VERSION_NAME as CLAUDE_ARTICLE_EVALUATOR_VERSION,
    )
    from agents.scopus_agent import (
        DEFAULT_SYSTEM_PROMPT as SCOPUS_AGENT_PROMPT,
        SEED_VERSION_NAME as SCOPUS_AGENT_VERSION,
    )

    _seed_agent(
        name="article-evaluator",
        agent_type="article-evaluator",
        description="Avalia a relevância de um artigo científico para um protocolo de pesquisa.",
        seed_version_name=ARTICLE_EVALUATOR_VERSION,
        version_description=(
            "Avaliação em duas etapas: triagem inicial por título (pente grosso, "
            "só rejeita com certeza) seguida de avaliação completa por título + "
            "abstract + palavras-chave (pente fino). Suporte a Protocolo de "
            "Pesquisa completo: critérios de exclusão eliminatórios, critérios de "
            "inclusão com lógica configurável (ANY/ALL/expressão), e objetivos "
            "gerais e específicos da pesquisa. Este system prompt rege apenas a "
            "etapa 2 (pente fino); a etapa 1 usa um prompt fixo definido no código."
        ),
        system_prompt=ARTICLE_EVALUATOR_PROMPT,
        temperature=0.1,
        provider="ollama",
        model_primary=settings.ollama_model_primary,
        model_fallback=settings.ollama_model_fallback,
    )

    _seed_agent(
        name="article-evaluator-claude",
        agent_type="article-evaluator",
        description=(
            "Avalia a relevância de um artigo científico para um protocolo de "
            "pesquisa usando a API da Claude (Anthropic) em vez do modelo local."
        ),
        seed_version_name=CLAUDE_ARTICLE_EVALUATOR_VERSION,
        version_description=(
            "Mesma lógica de avaliação em duas etapas do agente local (triagem "
            "por título, depois pente fino com título + abstract + palavras-chave), "
            "porém executada via API da Claude. Requer ANTHROPIC_API_KEY configurada."
        ),
        system_prompt=CLAUDE_ARTICLE_EVALUATOR_PROMPT,
        temperature=0.1,
        provider="anthropic",
        model_primary=settings.anthropic_model_primary,
        model_fallback=settings.anthropic_model_fallback,
    )

    _seed_agent(
        name="scopus-agent",
        agent_type="scopus-agent",
        description=(
            "Constrói strings de busca otimizadas para o Scopus, simula resultados "
            "e refina a busca iterativamente com base na seleção do usuário."
        ),
        seed_version_name=SCOPUS_AGENT_VERSION,
        version_description=(
            "Estrategista de busca acadêmica: extração de keywords, expansão de "
            "sinônimos, identificação de autores de referência e códigos de campo do Scopus."
        ),
        system_prompt=SCOPUS_AGENT_PROMPT,
        temperature=0.2,
        model_primary=settings.ollama_model_primary,
        model_fallback=settings.ollama_model_fallback,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_default_agents()
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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure any unexpected error still reaches the client as JSON with a
    `detail` field — the frontend always parses error bodies as JSON, and
    without this handler Starlette's default falls back to a plain-text
    body that breaks that parsing."""
    logging.getLogger(__name__).exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Erro interno inesperado: {exc}"})


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
