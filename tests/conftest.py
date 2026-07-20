"""Configura o sys.path para importar os módulos do frontend e do backend
sem instalação: os testes importam `scopus_agent`/`csv_utils` (frontend) e
`agents.evaluation_core`/`schemas.evaluation` (backend) exatamente como os
próprios serviços fazem dentro dos containers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# backend primeiro na lista de inserções para que, ao final, frontend/ fique
# à frente: `import scopus_agent` deve resolver para frontend/scopus_agent.py
# (o backend também tem um scopus_agent.py, mas só com o prompt de seed).
for folder in ("backend", "frontend"):
    path = str(ROOT / folder)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
