"""Lê o CSV e popula um banco SQLite."""
import sqlite3
from pathlib import Path
import pandas as pd

PASTA = Path(__file__).resolve().parent

COLUNAS = [
    "dispositivo", "data_hora", "nivel_bateria", "carregando",
    "app_em_uso", "brilho_tela", "uso_cpu", "tela_ligada",
]

# O script recria as tabelas do zero a cada execução.
ESQUEMA = """
DROP TABLE IF EXISTS registros_bateria;
DROP TABLE IF EXISTS apps;
DROP TABLE IF EXISTS dispositivos;

CREATE TABLE dispositivos (
    id_dispositivo  INTEGER PRIMARY KEY,
    nome            TEXT NOT NULL UNIQUE
);

CREATE TABLE apps (
    id_app  INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE
);

CREATE TABLE registros_bateria (
    id_registro     INTEGER PRIMARY KEY,
    id_dispositivo  INTEGER NOT NULL REFERENCES dispositivos(id_dispositivo),
    id_app          INTEGER NOT NULL REFERENCES apps(id_app),
    data_hora       TEXT    NOT NULL CHECK (datetime(data_hora) IS NOT NULL),
    nivel_bateria   REAL    NOT NULL CHECK (nivel_bateria BETWEEN 0 AND 100),
    carregando      INTEGER NOT NULL CHECK (carregando IN (0, 1)),
    tela_ligada     INTEGER NOT NULL CHECK (tela_ligada IN (0, 1)),
    brilho_tela     INTEGER NOT NULL CHECK (brilho_tela BETWEEN 0 AND 100),
    uso_cpu         REAL    NOT NULL CHECK (uso_cpu BETWEEN 0 AND 100),
    UNIQUE (id_dispositivo, data_hora)
);

CREATE INDEX idx_registros_dispositivo_data
    ON registros_bateria(id_dispositivo, data_hora);
CREATE INDEX idx_registros_app
    ON registros_bateria(id_app);
"""


def validar_tabela(tabela: pd.DataFrame) -> pd.DataFrame:
    """Confere o CSV antes de inserir e devolve a data já padronizada."""
    faltando = [c for c in COLUNAS if c not in tabela.columns]
    if faltando:
        raise ValueError(f"Colunas ausentes no CSV: {faltando}")

    if tabela[COLUNAS].isnull().any().any():
        raise ValueError("O CSV contém valores vazios.")

    if not tabela["nivel_bateria"].between(0, 100).all():
        raise ValueError("nivel_bateria deve estar entre 0 e 100.")
    if not tabela["carregando"].isin([0, 1]).all():
        raise ValueError("carregando deve ser 0 ou 1.")
    if not tabela["tela_ligada"].isin([0, 1]).all():
        raise ValueError("tela_ligada deve ser 0 ou 1.")
    if not tabela["brilho_tela"].between(0, 100).all():
        raise ValueError("brilho_tela deve estar entre 0 e 100.")
    if not tabela["uso_cpu"].between(0, 100).all():
        raise ValueError("uso_cpu deve estar entre 0 e 100.")

    tabela = tabela.copy()
    tabela["data_hora"] = pd.to_datetime(
        tabela["data_hora"], errors="raise"
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    duplicadas = tabela.duplicated(["dispositivo", "data_hora"]).sum()
    if duplicadas:
        raise ValueError(
            f"Existem {duplicadas} registros repetidos de dispositivo + data_hora."
        )

    return tabela


def principal(arquivo_csv=PASTA / "logs_bateria.csv",
              arquivo_banco=PASTA / "bateria.db"):
    if not Path(arquivo_csv).exists():
        raise SystemExit(f"CSV não encontrado: {arquivo_csv}")

    tabela = validar_tabela(pd.read_csv(arquivo_csv))

    conexao = sqlite3.connect(arquivo_banco)
    try:
        # O SQLite vem com foreign keys desligadas por padrão.
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.executescript(ESQUEMA)

        with conexao:
            conexao.executemany(
                "INSERT INTO dispositivos(nome) VALUES (?)",
                [(d,) for d in tabela["dispositivo"].unique()],
            )
            conexao.executemany(
                "INSERT INTO apps(nome) VALUES (?)",
                [(a,) for a in tabela["app_em_uso"].unique()],
            )

            ids_dispositivos = dict(
                conexao.execute("SELECT nome, id_dispositivo FROM dispositivos")
            )
            ids_apps = dict(conexao.execute("SELECT nome, id_app FROM apps"))

            registros = [
                (
                    ids_dispositivos[l.dispositivo],
                    ids_apps[l.app_em_uso],
                    l.data_hora,
                    l.nivel_bateria,
                    l.carregando,
                    l.tela_ligada,
                    l.brilho_tela,
                    l.uso_cpu,
                )
                for l in tabela.itertuples(index=False)
            ]
            conexao.executemany(
                """INSERT INTO registros_bateria
                   (id_dispositivo, id_app, data_hora, nivel_bateria,
                    carregando, tela_ligada, brilho_tela, uso_cpu)
                   VALUES (?,?,?,?,?,?,?,?)""",
                registros,
            )

        print(f"{len(registros)} registros inseridos em {arquivo_banco}")
    finally:
        conexao.close()


if __name__ == "__main__":
    principal()
