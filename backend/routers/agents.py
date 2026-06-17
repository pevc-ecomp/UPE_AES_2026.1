from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from agents.article_evaluator import evaluate_article as _evaluate
from db import get_session
from models.agent import Agent, AgentVersion
from schemas.agent import (
    AgentCreate,
    AgentRead,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionRead,
)
from schemas.evaluation import EvaluationRequest, EvaluationResponse

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_agent_read(agent: Agent, session: Session) -> AgentRead:
    versions = session.exec(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent.id)
        .order_by(AgentVersion.created_at.desc())
    ).all()

    active_version = None
    if agent.active_version_id:
        active_version = session.get(AgentVersion, agent.active_version_id)

    return AgentRead(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        agent_type=agent.agent_type,
        active_version_id=agent.active_version_id,
        active_version=AgentVersionRead.model_validate(active_version) if active_version else None,
        versions=[AgentVersionRead.model_validate(v) for v in versions],
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _get_agent_or_404(agent_id: str, session: Session) -> Agent:
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


# ── Agent CRUD ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AgentRead])
def list_agents(agent_type: Optional[str] = None, session: Session = Depends(get_session)):
    query = select(Agent).order_by(Agent.created_at)
    if agent_type:
        query = query.where(Agent.agent_type == agent_type)
    agents = session.exec(query).all()
    return [_build_agent_read(a, session) for a in agents]


@router.post("", response_model=AgentRead, status_code=201)
def create_agent(payload: AgentCreate, session: Session = Depends(get_session)):
    if session.exec(select(Agent).where(Agent.name == payload.name)).first():
        raise HTTPException(400, f"Agent '{payload.name}' already exists")

    agent = Agent(name=payload.name, description=payload.description, agent_type=payload.agent_type)
    session.add(agent)
    session.flush()

    version = AgentVersion(agent_id=agent.id, **payload.initial_version.model_dump())
    session.add(version)
    session.flush()

    agent.active_version_id = version.id
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return _build_agent_read(agent, session)


# NOTE: evaluate-article must be declared before /{agent_id} to avoid routing conflict
@router.post("/evaluate-article", response_model=EvaluationResponse)
async def evaluate_article_endpoint(
    request: EvaluationRequest,
    session: Session = Depends(get_session),
):
    if request.agent_id:
        agent = session.get(Agent, request.agent_id)
        if not agent:
            raise HTTPException(404, f"Agent '{request.agent_id}' not found")
    else:
        agent = session.exec(
            select(Agent).where(Agent.agent_type == "article-evaluator")
        ).first()
        if not agent:
            agent = session.exec(select(Agent).where(Agent.name == "article-evaluator")).first()
        if not agent:
            agent = session.exec(select(Agent).limit(1)).first()
        if not agent:
            raise HTTPException(503, "No agents configured. Create an agent first.")

    if not agent.active_version_id:
        raise HTTPException(422, f"Agent '{agent.name}' has no active version")

    agent_version = session.get(AgentVersion, agent.active_version_id)
    if not agent_version:
        raise HTTPException(500, "Active version record not found")

    try:
        return await _evaluate(request, agent_version)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(agent_id: str, session: Session = Depends(get_session)):
    return _build_agent_read(_get_agent_or_404(agent_id, session), session)


@router.put("/{agent_id}", response_model=AgentRead)
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    session: Session = Depends(get_session),
):
    agent = _get_agent_or_404(agent_id, session)

    if payload.name is not None:
        clash = session.exec(
            select(Agent).where(Agent.name == payload.name, Agent.id != agent_id)
        ).first()
        if clash:
            raise HTTPException(400, f"Name '{payload.name}' already in use")
        agent.name = payload.name

    if payload.description is not None:
        agent.description = payload.description

    if payload.agent_type is not None:
        agent.agent_type = payload.agent_type

    agent.updated_at = _now()
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return _build_agent_read(agent, session)


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: str, session: Session = Depends(get_session)):
    agent = _get_agent_or_404(agent_id, session)
    for v in session.exec(select(AgentVersion).where(AgentVersion.agent_id == agent_id)).all():
        session.delete(v)
    session.delete(agent)
    session.commit()


# ── Version management ────────────────────────────────────────────────────────

@router.get("/{agent_id}/versions", response_model=list[AgentVersionRead])
def list_versions(agent_id: str, session: Session = Depends(get_session)):
    _get_agent_or_404(agent_id, session)
    versions = session.exec(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.created_at.desc())
    ).all()
    return [AgentVersionRead.model_validate(v) for v in versions]


@router.post("/{agent_id}/versions", response_model=AgentVersionRead, status_code=201)
def create_version(
    agent_id: str,
    payload: AgentVersionCreate,
    session: Session = Depends(get_session),
):
    _get_agent_or_404(agent_id, session)
    version = AgentVersion(agent_id=agent_id, **payload.model_dump())
    session.add(version)
    session.commit()
    session.refresh(version)
    return AgentVersionRead.model_validate(version)


@router.put("/{agent_id}/versions/{version_id}/activate", response_model=AgentRead)
def activate_version(
    agent_id: str,
    version_id: str,
    session: Session = Depends(get_session),
):
    agent = _get_agent_or_404(agent_id, session)
    version = session.get(AgentVersion, version_id)
    if not version or version.agent_id != agent_id:
        raise HTTPException(404, "Version not found for this agent")

    agent.active_version_id = version_id
    agent.updated_at = _now()
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return _build_agent_read(agent, session)
