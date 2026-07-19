"""Persistência simples do histórico de execuções das páginas do frontend.

Cada execução vira um registro JSON em /app/data/history/<kind>/<id>/record.json,
com arquivos auxiliares (ex.: CSV de entrada e de saída do Avaliador de Artigos)
salvos na mesma pasta. O volume ./data é compartilhado entre os containers, então
o histórico sobrevive a reinícios da sessão e do Streamlit.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_ROOT = Path("/app/data/history")

KIND_STRING_OPTIMIZER = "string_optimizer"
KIND_ARTICLE_EVALUATOR = "article_evaluator"
KIND_AI_JUDGE = "ai_judge"


def save_record(kind: str, record: dict, files: dict[str, bytes] | None = None) -> str | None:
    """Salva um registro de histórico e retorna seu id (None se falhar).

    `record` é serializado como JSON; `files` mapeia nome do arquivo → bytes e
    é salvo na pasta do registro. Falhas são engolidas com log: o histórico
    nunca deve derrubar o fluxo principal da página.
    """
    try:
        record_id = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{uuid.uuid4().hex[:6]}"
        record_dir = HISTORY_ROOT / kind / record_id
        record_dir.mkdir(parents=True, exist_ok=True)

        record = dict(record)
        record["id"] = record_id
        record["timestamp"] = datetime.now().isoformat(timespec="seconds")
        record["files"] = sorted((files or {}).keys())

        for filename, content in (files or {}).items():
            (record_dir / filename).write_bytes(content)

        (record_dir / "record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return record_id
    except Exception as exc:
        logger.warning("Falha ao salvar histórico (%s): %s", kind, exc)
        return None


def add_file(kind: str, record_id: str, filename: str, content: bytes) -> bool:
    """Anexa (ou substitui) um arquivo em um registro já existente."""
    record_dir = HISTORY_ROOT / kind / record_id
    record_file = record_dir / "record.json"
    try:
        if not record_file.is_file():
            return False
        (record_dir / filename).write_bytes(content)
        record = json.loads(record_file.read_text(encoding="utf-8"))
        if filename not in record.get("files", []):
            record["files"] = sorted(record.get("files", []) + [filename])
        record_file.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return True
    except Exception as exc:
        logger.warning("Falha ao anexar arquivo ao histórico (%s/%s): %s", kind, record_id, exc)
        return False


def list_records(kind: str) -> list[dict]:
    """Lista os registros de um tipo, do mais recente para o mais antigo."""
    kind_dir = HISTORY_ROOT / kind
    if not kind_dir.exists():
        return []

    records = []
    for record_dir in sorted(kind_dir.iterdir(), reverse=True):
        record_file = record_dir / "record.json"
        if not record_file.is_file():
            continue
        try:
            records.append(json.loads(record_file.read_text(encoding="utf-8")))
        except Exception as exc:
            logger.warning("Registro de histórico ilegível (%s): %s", record_file, exc)
    return records


def load_file(kind: str, record_id: str, filename: str) -> bytes | None:
    """Lê um arquivo auxiliar de um registro (None se não existir)."""
    path = HISTORY_ROOT / kind / record_id / filename
    try:
        return path.read_bytes() if path.is_file() else None
    except Exception as exc:
        logger.warning("Falha ao ler arquivo de histórico (%s): %s", path, exc)
        return None


def delete_record(kind: str, record_id: str) -> bool:
    """Remove um registro inteiro (pasta com JSON e arquivos)."""
    record_dir = HISTORY_ROOT / kind / record_id
    try:
        if not record_dir.is_dir():
            return False
        for item in record_dir.iterdir():
            item.unlink()
        record_dir.rmdir()
        return True
    except Exception as exc:
        logger.warning("Falha ao excluir registro de histórico (%s): %s", record_dir, exc)
        return False
