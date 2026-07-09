import os
from datetime import datetime

import httpx
import streamlit as st

st.set_page_config(page_title="Agentes", page_icon="🤖", layout="wide")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
DEFAULT_AUTHOR = "pevc-ecomp"
MODELS_BY_PROVIDER = {
    "ollama": ["phi3:mini", "llama3.2:1b", "mistral", "llama3:8b", "gemma2:2b"],
    "anthropic": ["claude-sonnet-5", "claude-haiku-4-5-20251001", "claude-opus-4-8"],
}
PROVIDERS = ["ollama", "anthropic"]
PROVIDER_LABELS = {
    "ollama": "Ollama (local)",
    "anthropic": "Claude API (Anthropic)",
}
AGENT_TYPES = ["article-evaluator", "scopus-agent", "general"]
AGENT_TYPE_LABELS = {
    "article-evaluator": "Avaliador de Artigos",
    "scopus-agent": "Scopus Agent",
    "general": "Geral / outro",
}


# ── API helpers ───────────────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs):
    try:
        resp = httpx.request(method, f"{BACKEND_URL}{path}", timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else None
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.error(f"Erro da API: {detail}")
        return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None


def _fmt_ts(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso


# ── Dialogs ───────────────────────────────────────────────────────────────────

@st.dialog("Criar Agente", width="large")
def _dialog_create_agent():
    st.markdown("Preencha os dados do novo agente e sua versão inicial.")

    name = st.text_input("Nome do agente *", placeholder="Ex: article-evaluator-v2")
    description = st.text_area("Descrição", height=80,
                                placeholder="Descreva o propósito deste agente")
    agent_type = st.selectbox(
        "Página / tipo de agente *",
        AGENT_TYPES,
        format_func=lambda t: AGENT_TYPE_LABELS.get(t, t),
    )

    st.divider()
    st.markdown("**Versão inicial**")
    v_name = st.text_input("Nome da versão *", value="v1.0 - Inicial")
    v_desc = st.text_area("Descrição da versão", height=60)
    system_prompt = st.text_area("System Prompt *", height=300,
                                  placeholder="Insira o system prompt completo do agente...")
    provider = st.selectbox("Provedor do LLM", PROVIDERS,
                             format_func=lambda p: PROVIDER_LABELS.get(p, p))
    model_options = MODELS_BY_PROVIDER[provider]
    col_t, col_m1, col_m2 = st.columns(3)
    with col_t:
        temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0,
                                       value=0.1, step=0.05)
    with col_m1:
        model_primary = st.selectbox("Modelo primário", model_options, index=0)
    with col_m2:
        model_fallback = st.selectbox(
            "Modelo fallback", model_options,
            index=1 if len(model_options) > 1 else 0,
        )
    author = st.text_input("Autor *", value=DEFAULT_AUTHOR)

    if st.button("Criar Agente", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Nome obrigatório.")
            return
        if not system_prompt.strip():
            st.error("System Prompt obrigatório.")
            return
        if not author.strip():
            st.error("Autor obrigatório.")
            return
        payload = {
            "name": name.strip(),
            "description": description.strip(),
            "agent_type": agent_type,
            "initial_version": {
                "version_name": v_name.strip() or "v1.0",
                "version_description": v_desc.strip(),
                "system_prompt": system_prompt.strip(),
                "temperature": temperature,
                "provider": provider,
                "model_primary": model_primary,
                "model_fallback": model_fallback,
                "author": author.strip(),
            },
        }
        result = _api("POST", "/agents", json=payload)
        if result:
            st.success(f"Agente '{name}' criado!")
            st.rerun()


@st.dialog("Editar Agente")
def _dialog_edit_agent(agent_id: str, current_name: str, current_description: str,
                        current_agent_type: str = "general"):
    name = st.text_input("Nome *", value=current_name)
    description = st.text_area("Descrição", value=current_description, height=100)
    agent_type = st.selectbox(
        "Página / tipo de agente *",
        AGENT_TYPES,
        index=AGENT_TYPES.index(current_agent_type) if current_agent_type in AGENT_TYPES else len(AGENT_TYPES) - 1,
        format_func=lambda t: AGENT_TYPE_LABELS.get(t, t),
    )

    if st.button("Salvar", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Nome obrigatório.")
            return
        result = _api("PUT", f"/agents/{agent_id}",
                      json={"name": name.strip(), "description": description.strip(),
                            "agent_type": agent_type})
        if result:
            st.success("Agente atualizado!")
            st.rerun()


@st.dialog("Nova Versão", width="large")
def _dialog_create_version(
    agent_id: str,
    agent_name: str,
    base_system_prompt: str = "",
    base_temperature: float = 0.1,
    base_provider: str = "ollama",
    base_model_primary: str = "phi3:mini",
    base_model_fallback: str = "llama3.2:1b",
    base_label: str = "",
):
    if base_label:
        st.info(f"Editando a partir de: **{base_label}**")
    else:
        st.markdown(f"Nova versão para **{agent_name}**")

    v_name = st.text_input("Nome da versão *", placeholder="Ex: v2.0 - Guardrails aprimorados")
    v_desc = st.text_area("Descrição das mudanças", height=70)
    system_prompt = st.text_area("System Prompt *", value=base_system_prompt, height=350)
    provider = st.selectbox(
        "Provedor do LLM", PROVIDERS,
        index=PROVIDERS.index(base_provider) if base_provider in PROVIDERS else 0,
        format_func=lambda p: PROVIDER_LABELS.get(p, p),
    )
    model_options = MODELS_BY_PROVIDER[provider]
    col_t, col_m1, col_m2 = st.columns(3)
    with col_t:
        temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0,
                                       value=base_temperature, step=0.05)
    with col_m1:
        idx1 = model_options.index(base_model_primary) if base_model_primary in model_options else 0
        model_primary = st.selectbox("Modelo primário", model_options, index=idx1)
    with col_m2:
        default_idx2 = 1 if len(model_options) > 1 else 0
        idx2 = model_options.index(base_model_fallback) if base_model_fallback in model_options else default_idx2
        model_fallback = st.selectbox("Modelo fallback", model_options, index=idx2)
    author = st.text_input("Autor *", value=DEFAULT_AUTHOR)
    activate = st.checkbox("Ativar esta versão imediatamente", value=False)

    if st.button("Salvar versão", type="primary", use_container_width=True):
        if not v_name.strip():
            st.error("Nome da versão obrigatório.")
            return
        if not system_prompt.strip():
            st.error("System Prompt obrigatório.")
            return
        if not author.strip():
            st.error("Autor obrigatório.")
            return
        payload = {
            "version_name": v_name.strip(),
            "version_description": v_desc.strip(),
            "system_prompt": system_prompt.strip(),
            "temperature": temperature,
            "provider": provider,
            "model_primary": model_primary,
            "model_fallback": model_fallback,
            "author": author.strip(),
        }
        version = _api("POST", f"/agents/{agent_id}/versions", json=payload)
        if version:
            if activate:
                _api("PUT", f"/agents/{agent_id}/versions/{version['id']}/activate")
            st.success(f"Versão '{v_name}' salva!" + (" (ativa)" if activate else ""))
            st.rerun()


@st.dialog("Confirmar Exclusão")
def _dialog_delete_agent(agent_id: str, agent_name: str):
    st.warning(f"Tem certeza que deseja excluir o agente **{agent_name}**?")
    st.caption("Todas as versões serão apagadas permanentemente.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sim, excluir", type="primary", use_container_width=True):
            try:
                r = httpx.delete(f"{BACKEND_URL}/agents/{agent_id}", timeout=10)
                if r.status_code in (200, 204):
                    st.success(f"Agente '{agent_name}' excluído.")
                    st.rerun()
                else:
                    st.error(f"Erro {r.status_code}: {r.text}")
            except Exception as e:
                st.error(str(e))
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Status")
    try:
        _r = httpx.get(f"{BACKEND_URL}/health", timeout=5)
        backend_ok = _r.status_code == 200
        if backend_ok:
            st.success(f"✅ Backend online\n\n`{BACKEND_URL}`")
        else:
            st.error("❌ Backend retornou erro")
    except Exception:
        st.error(f"❌ Backend offline\n\n`{BACKEND_URL}`")
        backend_ok = False

# ── Page ─────────────────────────────────────────────────────────────────────

st.title("🤖 Gerenciamento de Agentes")
st.markdown("Crie, edite e versione os agentes de IA disponíveis na plataforma.")
st.divider()

if not backend_ok:
    st.error("Backend offline. Inicie os containers antes de gerenciar agentes.")
    st.stop()

agents_data = _api("GET", "/agents") or []

col_btn, _ = st.columns([1, 5])
with col_btn:
    if st.button("➕ Criar Agente", type="primary", use_container_width=True):
        _dialog_create_agent()

if not agents_data:
    st.info("Nenhum agente cadastrado. Clique em **Criar Agente** para começar.")
    st.stop()

st.markdown(f"**{len(agents_data)} agente(s) cadastrado(s)**")
st.divider()

# ── Agent cards ───────────────────────────────────────────────────────────────
for agent in agents_data:
    active_ver = agent.get("active_version")
    versions = agent.get("versions", [])

    with st.container(border=True):
        # ── Header ────────────────────────────────────────────────────────────
        col_info, col_actions = st.columns([4, 1])

        with col_info:
            st.markdown(f"### {agent['name']}")
            st.caption(
                f"📄 {AGENT_TYPE_LABELS.get(agent.get('agent_type', 'general'), agent.get('agent_type', 'general'))}"
            )
            if agent.get("description"):
                st.markdown(agent["description"])
            if active_ver:
                st.caption(
                    f"Versão ativa: **{active_ver['version_name']}** · "
                    f"por {active_ver['author']} · "
                    f"{_fmt_ts(active_ver['created_at'])}"
                )
            else:
                st.caption(":orange[Nenhuma versão ativa]")

        with col_actions:
            if st.button("✏️ Editar", key=f"edit_{agent['id']}", use_container_width=True):
                _dialog_edit_agent(agent["id"], agent["name"], agent.get("description", ""),
                                   agent.get("agent_type", "general"))

            if st.button("🗑️ Excluir", key=f"del_{agent['id']}", use_container_width=True):
                _dialog_delete_agent(agent["id"], agent["name"])

            base = active_ver or {}
            if st.button("➕ Nova Versão", key=f"newver_{agent['id']}", use_container_width=True):
                _dialog_create_version(
                    agent_id=agent["id"],
                    agent_name=agent["name"],
                    base_system_prompt=base.get("system_prompt", ""),
                    base_temperature=base.get("temperature", 0.1),
                    base_provider=base.get("provider", "ollama"),
                    base_model_primary=base.get("model_primary", "phi3:mini"),
                    base_model_fallback=base.get("model_fallback", "llama3.2:1b"),
                )

        # ── Version history ───────────────────────────────────────────────────
        if versions:
            with st.expander(f"📋 Histórico de versões ({len(versions)})"):
                for ver in versions:
                    is_active = ver["id"] == agent.get("active_version_id")
                    badge = ":green[● ATIVA]" if is_active else ""

                    col_v, col_va = st.columns([5, 1])
                    with col_v:
                        st.markdown(f"**{ver['version_name']}** {badge}")
                        if ver.get("version_description"):
                            st.caption(ver["version_description"])
                        st.caption(
                            f"por {ver['author']} · {_fmt_ts(ver['created_at'])} · "
                            f"temp={ver['temperature']} · "
                            f"{PROVIDER_LABELS.get(ver.get('provider', 'ollama'), ver.get('provider', 'ollama'))} · "
                            f"{ver['model_primary']}"
                        )

                    with col_va:
                        if not is_active:
                            if st.button("Ativar", key=f"act_{ver['id']}", use_container_width=True):
                                result = _api(
                                    "PUT",
                                    f"/agents/{agent['id']}/versions/{ver['id']}/activate",
                                )
                                if result:
                                    st.rerun()

                        if st.button("✏️ Editar a partir desta",
                                     key=f"fork_{ver['id']}", use_container_width=True):
                            _dialog_create_version(
                                agent_id=agent["id"],
                                agent_name=agent["name"],
                                base_system_prompt=ver.get("system_prompt", ""),
                                base_temperature=ver.get("temperature", 0.1),
                                base_provider=ver.get("provider", "ollama"),
                                base_model_primary=ver.get("model_primary", "phi3:mini"),
                                base_model_fallback=ver.get("model_fallback", "llama3.2:1b"),
                                base_label=ver["version_name"],
                            )

                    st.divider()
