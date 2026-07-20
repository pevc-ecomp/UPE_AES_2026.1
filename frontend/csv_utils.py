"""Utilidades de CSV compartilhadas entre as páginas do frontend.

Centraliza a leitura robusta de CSVs enviados pelo usuário (exports do
Scopus/WoS, "CSV UTF-8" do Excel, nosso próprio export ';;') e a
serialização com separador ';;', usadas pelo Article Evaluator e pelo
String Optimizer.
"""

import pandas as pd

CSV_EXPORT_SEP = ";;"


def to_delimited_csv(df: pd.DataFrame, sep: str = CSV_EXPORT_SEP) -> bytes:
    """Serialize a DataFrame with a two-character delimiter instead of pandas'
    default single-character separator. Justification/reason columns are free
    text that may contain commas or semicolons, so a single-char delimiter
    risks false-positive column splits; every field is also quoted so the
    delimiter itself can never be mistaken for one inside a value."""
    def _escape(value) -> str:
        text = "" if pd.isna(value) else str(value)
        return '"' + text.replace('"', '""') + '"'

    lines = [sep.join(_escape(c) for c in df.columns)]
    for row in df.itertuples(index=False, name=None):
        lines.append(sep.join(_escape(v) for v in row))
    return ("\r\n".join(lines)).encode("utf-8")


def read_uploaded_csv(uploaded) -> pd.DataFrame:
    """Read an uploaded CSV trying to auto-detect its separator/encoding.
    Real-world exports (Scopus, WoS, Excel "CSV UTF-8", our own ';;'-delimited
    export) use a variety of delimiters — hardcoding ',' broke on any file
    that used ';' or a multi-char separator, since commas inside abstract
    text get misread as extra column boundaries."""
    # Separadores explícitos primeiro — o auto-sniff fica por último porque:
    # (a) ele confunde nosso export ';;' com ';' e cria colunas fantasma
    #     "Unnamed: N" entre as colunas reais;
    # (b) em arquivos de coluna única ele chega a inventar separadores
    #     absurdos (uma letra qualquer), produzindo colunas sem sentido.
    attempts = [
        {"sep": CSV_EXPORT_SEP, "engine": "python"},
        {"sep": ";"},
        {"sep": ","},
        {"sep": "\t"},
        {"sep": None, "engine": "python"},  # auto-sniff (último recurso)
    ]
    last_error: Exception | None = None
    for encoding in ("utf-8", "latin-1"):
        for kwargs in attempts:
            uploaded.seek(0)
            try:
                df = pd.read_csv(uploaded, encoding=encoding, **kwargs)
            except Exception as exc:
                last_error = exc
                continue
            sniffed = kwargs.get("sep") is None
            degenerate = sniffed and any(
                str(c).startswith("Unnamed:") for c in df.columns
            )
            if len(df.columns) > 1 and not degenerate:
                if kwargs.get("sep") == CSV_EXPORT_SEP:
                    df = _strip_outer_quotes(df)
                return df
            last_error = ValueError(
                "Apenas uma coluna foi detectada — o separador do arquivo provavelmente "
                "não pôde ser identificado automaticamente."
            )
    raise last_error


def _strip_outer_quotes(df: pd.DataFrame) -> pd.DataFrame:
    """Com separador multi-caractere o engine 'python' do pandas usa split por
    regex e NÃO interpreta as aspas do CSV — colunas e valores chegam com as
    aspas externas literais ('"titulo"'). Remove-as e desfaz o escape ('""')."""
    def _unquote(value):
        if isinstance(value, str) and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1].replace('""', '"')
        return value

    df = df.rename(columns={c: _unquote(str(c)) for c in df.columns})
    return df.map(_unquote)


def guess_column(columns, candidates) -> int | None:
    """Índice da primeira coluna cujo nome contém um dos termos candidatos
    (case-insensitive), na ordem de prioridade dos candidatos. None se nada
    casar — o chamador decide o default do selectbox."""
    lowered = [str(c).strip().lower() for c in columns]
    for cand in candidates:
        for i, name in enumerate(lowered):
            if cand in name:
                return i
    return None
