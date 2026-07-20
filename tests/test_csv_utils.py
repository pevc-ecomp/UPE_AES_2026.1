import io

import pandas as pd
import pytest

from csv_utils import CSV_EXPORT_SEP, guess_column, read_uploaded_csv, to_delimited_csv


# ── to_delimited_csv ──────────────────────────────────────────────────────────

def test_to_delimited_csv_usa_separador_duplo_e_aspas():
    df = pd.DataFrame({"titulo": ["Artigo A"], "justificativa": ["contém, vírgula; e ponto-e-vírgula"]})
    text = to_delimited_csv(df).decode("utf-8")
    lines = text.split("\r\n")
    assert lines[0] == '"titulo";;"justificativa"'
    assert lines[1] == '"Artigo A";;"contém, vírgula; e ponto-e-vírgula"'


def test_to_delimited_csv_escapa_aspas_duplas():
    df = pd.DataFrame({"c": ['ele disse "oi"']})
    text = to_delimited_csv(df).decode("utf-8")
    assert '"ele disse ""oi"""' in text


def test_to_delimited_csv_nan_vira_vazio():
    df = pd.DataFrame({"a": [None], "b": [float("nan")]})
    text = to_delimited_csv(df).decode("utf-8")
    assert text.split("\r\n")[1] == '"";;""'


# ── read_uploaded_csv ─────────────────────────────────────────────────────────

def _upload(content: str, encoding: str = "utf-8") -> io.BytesIO:
    return io.BytesIO(content.encode(encoding))


def test_read_uploaded_csv_virgula():
    df = read_uploaded_csv(_upload("a,b\n1,2\n"))
    assert list(df.columns) == ["a", "b"]
    assert len(df) == 1


def test_read_uploaded_csv_ponto_e_virgula():
    df = read_uploaded_csv(_upload("a;b\ntexto, com vírgula;2\n"))
    assert list(df.columns) == ["a", "b"]
    assert df.iloc[0]["a"] == "texto, com vírgula"


def test_read_uploaded_csv_reimporta_export_proprio():
    original = pd.DataFrame({"titulo": ["A, B"], "score": ["90"]})
    df = read_uploaded_csv(io.BytesIO(to_delimited_csv(original)))
    assert list(df.columns) == ["titulo", "score"]
    assert df.iloc[0]["titulo"] == "A, B"


def test_read_uploaded_csv_latin1():
    df = read_uploaded_csv(_upload("título;ano\nAvaliação;2024\n", encoding="latin-1"))
    assert len(df.columns) == 2
    assert len(df) == 1


def test_read_uploaded_csv_uma_coluna_gera_erro():
    with pytest.raises(Exception):
        read_uploaded_csv(_upload("apenas_uma_coluna\nvalor\n"))


# ── guess_column ──────────────────────────────────────────────────────────────

def test_guess_column_prioridade_dos_candidatos():
    cols = ["Ano", "Article Title", "Abstract"]
    assert guess_column(cols, ("title", "título")) == 1
    assert guess_column(cols, ("abstract", "resumo")) == 2
    assert guess_column(cols, ("year", "ano")) == 0


def test_guess_column_sem_correspondencia():
    assert guess_column(["a", "b"], ("title",)) is None
