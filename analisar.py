"""Queries SQL analíticas + relatórios de descarga por dispositivo."""
import sqlite3
from pathlib import Path
import re

import pandas as pd
from pandas.errors import DatabaseError
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PASTA = Path(__file__).resolve().parent
PASTA_RELATORIOS = PASTA / "relatorios"
ARQUIVO_BANCO = PASTA / "bateria.db"

# CTE base: queda de bateria entre amostras consecutivas (só descarga real).
# Também guardamos as horas reais entre as amostras, em vez de assumir
# que toda amostra tem exatamente 5 minutos.
# O parâmetro :dispositivo filtra um aparelho; None considera todos.
CONSULTA_BASE = """
WITH variacoes AS (
    SELECT
        r.id_dispositivo,
        r.id_app,
        r.data_hora,
        r.carregando,
        r.tela_ligada,
        r.uso_cpu,
        LAG(r.nivel_bateria) OVER (PARTITION BY r.id_dispositivo ORDER BY r.data_hora)
            - r.nivel_bateria AS queda_pct,
        LAG(r.carregando) OVER (PARTITION BY r.id_dispositivo ORDER BY r.data_hora)
            AS carregando_anterior,
        LAG(r.data_hora) OVER (PARTITION BY r.id_dispositivo ORDER BY r.data_hora)
            AS data_hora_anterior
    FROM registros_bateria r
),
descargas AS (
    SELECT *,
           (julianday(data_hora) - julianday(data_hora_anterior)) * 24.0 AS horas
    FROM variacoes
    WHERE queda_pct IS NOT NULL
      AND carregando = 0 AND carregando_anterior = 0
      AND queda_pct >= 0
      AND (:dispositivo IS NULL OR id_dispositivo =
           (SELECT id_dispositivo FROM dispositivos WHERE nome = :dispositivo))
)
"""

# Apenas app em primeiro plano com a tela ligada. Isso evita comparar
# "Launcher com tela desligada" com apps que o usuário realmente abriu.
CONSULTA_APPS = CONSULTA_BASE + """
SELECT a.nome AS app,
       ROUND(SUM(d.queda_pct), 1) AS queda_total_pct,
       ROUND(SUM(d.queda_pct) / SUM(d.horas), 2) AS pct_por_hora,
       ROUND(100.0 * SUM(d.queda_pct) /
             (SELECT SUM(queda_pct) FROM descargas WHERE tela_ligada = 1), 1)
           AS participacao_pct
FROM descargas d
JOIN apps a USING (id_app)
WHERE d.tela_ligada = 1
GROUP BY a.nome
ORDER BY pct_por_hora DESC;
"""

CONSULTA_HORAS = CONSULTA_BASE + """
SELECT CAST(strftime('%H', data_hora) AS INTEGER) AS hora,
       ROUND(SUM(queda_pct) / SUM(horas), 2) AS pct_por_hora
FROM descargas
GROUP BY hora
ORDER BY hora;
"""

CONSULTA_DISPOSITIVOS = CONSULTA_BASE + """
SELECT dv.nome AS dispositivo,
       ROUND(SUM(d.queda_pct) / SUM(d.horas), 2) AS pct_por_hora,
       ROUND(AVG(d.uso_cpu), 1) AS cpu_media
FROM descargas d
JOIN dispositivos dv USING (id_dispositivo)
GROUP BY dv.nome
ORDER BY pct_por_hora DESC;
"""

CONSULTA_APPS_POR_DISPOSITIVO = CONSULTA_BASE + """
SELECT dv.nome AS dispositivo, a.nome AS app,
       ROUND(SUM(d.queda_pct) / SUM(d.horas), 2) AS pct_por_hora
FROM descargas d
JOIN dispositivos dv USING (id_dispositivo)
JOIN apps a USING (id_app)
WHERE d.tela_ligada = 1
GROUP BY dv.nome, a.nome;
"""

# As primeiras 48 h são calculadas a partir do primeiro registro de cada
# aparelho; não dependemos mais de uma data fixa no código.
CONSULTA_CURVA = """
SELECT r.data_hora, r.nivel_bateria, r.carregando
FROM registros_bateria r
JOIN dispositivos d USING (id_dispositivo)
WHERE d.nome = :dispositivo
  AND r.data_hora <= (
      SELECT datetime(MIN(r2.data_hora), '+48 hours')
      FROM registros_bateria r2
      WHERE r2.id_dispositivo = d.id_dispositivo
  )
ORDER BY r.data_hora;
"""


def consultar(conexao, sql, dispositivo=None, **extras):
    return pd.read_sql(
        sql,
        conexao,
        params={"dispositivo": dispositivo},
        **extras,
    )


def gerar_relatorio(conexao, nome_dispositivo: str) -> None:
    tabela_apps = consultar(conexao, CONSULTA_APPS, nome_dispositivo)
    tabela_horas = consultar(conexao, CONSULTA_HORAS, nome_dispositivo)
    curva = consultar(
        conexao, CONSULTA_CURVA, nome_dispositivo, parse_dates=["data_hora"]
    )

    if curva.empty or tabela_apps.empty:
        print(f"Sem dados suficientes para {nome_dispositivo}; relatório ignorado.")
        return

    print(f"\n== {nome_dispositivo}: drenagem por app (tela ligada) ==\n"
          f"{tabela_apps.to_string(index=False)}")

    figura, eixos = plt.subplots(3, 1, figsize=(11, 11))
    try:
        eixos[0].plot(
            curva["data_hora"], curva["nivel_bateria"],
            lw=1.4, color="#1a73e8",
        )
        eixos[0].fill_between(
            curva["data_hora"], 0, 100,
            where=curva["carregando"] == 1,
            color="#34a853", alpha=.2, label="Carregando",
        )
        eixos[0].set(
            title=f"Curva de descarga — {nome_dispositivo} (48 h)",
            ylabel="Bateria (%)",
        )
        eixos[0].legend()
        eixos[0].grid(alpha=.3)

        eixos[1].bar(
            tabela_horas["hora"], tabela_horas["pct_por_hora"],
            color="#ea4335",
        )
        eixos[1].set(
            title="Taxa média de descarga por hora do dia (sem carregamento)",
            xlabel="Hora",
            ylabel="% / hora",
        )
        eixos[1].grid(alpha=.3, axis="y")

        eixos[2].barh(
            tabela_apps["app"][::-1], tabela_apps["pct_por_hora"][::-1],
            color="#fbbc04",
        )
        eixos[2].set(
            title="Drenagem por app (tela ligada)",
            xlabel="% / hora com tela ligada",
        )

        plt.tight_layout()
        nome_arquivo = re.sub(r"[^A-Za-z0-9_.-]", "_", nome_dispositivo)
        caminho = PASTA_RELATORIOS / f"relatorio_{nome_arquivo}.png"
        plt.savefig(caminho, dpi=130, bbox_inches="tight")
        print(f"   -> {caminho.name}")
    finally:
        plt.close(figura)


def gerar_comparativo(conexao) -> None:
    ranking = consultar(conexao, CONSULTA_DISPOSITIVOS)
    por_app = consultar(conexao, CONSULTA_APPS_POR_DISPOSITIVO)

    if ranking.empty or por_app.empty:
        print("\nSem dados para gerar o comparativo.")
        return

    print(f"\n== Ranking de dispositivos ==\n{ranking.to_string(index=False)}")

    matriz = por_app.pivot(
        index="app", columns="dispositivo", values="pct_por_hora"
    )
    matriz = matriz.loc[
        matriz.mean(axis=1).sort_values(ascending=False).index
    ]

    figura, eixos = plt.subplots(2, 1, figsize=(12, 10))
    try:
        matriz.plot.bar(ax=eixos[0], width=.8, rot=0)
        eixos[0].set(
            title="Drenagem por app em cada dispositivo (tela ligada)",
            xlabel="",
            ylabel="% / hora com tela ligada",
        )
        eixos[0].grid(alpha=.3, axis="y")
        eixos[0].legend(title="Dispositivo", ncol=5)

        eixos[1].barh(
            ranking["dispositivo"][::-1], ranking["pct_por_hora"][::-1],
            color="#1a73e8",
        )
        eixos[1].set(
            title="Ranking: descarga média por dispositivo",
            xlabel="% / hora sem carregamento",
        )
        eixos[1].grid(alpha=.3, axis="x")

        plt.tight_layout()
        plt.savefig(
            PASTA_RELATORIOS / "relatorio_comparativo.png",
            dpi=130,
            bbox_inches="tight",
        )
    finally:
        plt.close(figura)


def main() -> None:
    if not ARQUIVO_BANCO.exists():
        raise SystemExit(
            f"Banco não encontrado: {ARQUIVO_BANCO}\n"
            "Rode primeiro: python carregar_banco.py"
        )

    PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(ARQUIVO_BANCO)
    try:
        nomes = [
            linha[0]
            for linha in conexao.execute(
                "SELECT nome FROM dispositivos ORDER BY nome"
            )
        ]
        if not nomes:
            raise SystemExit("Nenhum dispositivo encontrado no banco.")

        for nome in nomes:
            gerar_relatorio(conexao, nome)
        gerar_comparativo(conexao)
        print(f"\nRelatórios salvos em {PASTA_RELATORIOS}")
    except (sqlite3.Error, DatabaseError) as erro:
        raise SystemExit(f"Erro ao consultar o banco: {erro}") from erro
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
