"""Gera um dataset sintético de logs de bateria Android."""
from pathlib import Path
import numpy as np
import pandas as pd

PASTA = Path(__file__).resolve().parent

gerador = np.random.default_rng(42)

# app -> (uso base de CPU %, consumo extra de bateria por amostra em %)
APLICATIVOS = {
    "YouTube":   (45, 0.060),
    "Instagram": (35, 0.045),
    "Chrome":    (25, 0.030),
    "WhatsApp":  (10, 0.012),
    "Maps":      (50, 0.070),
    "Spotify":   (15, 0.015),
    "Launcher":  (5,  0.005),
}
DISPOSITIVOS = ["Pixel_7", "Galaxy_S23", "Moto_G84", "Xiaomi_13", "Pixel_6a"]

DATA_INICIO = "2026-10-05"
INTERVALO_MIN = 5
DIAS = 7

# A bateria só começa a carregar quando fica abaixo deste nível.
LIMITE_CARGA = 15


def simular_dispositivo(nome_dispositivo: str) -> pd.DataFrame:
    instantes = pd.date_range(
        DATA_INICIO,
        periods=DIAS * 24 * 60 // INTERVALO_MIN,
        freq=f"{INTERVALO_MIN}min",
    )

    nivel_bateria = float(gerador.integers(60, 100))
    carregando = False
    linhas = []
    nomes_apps = list(APLICATIVOS)
    probabilidades = [.18, .18, .15, .15, .08, .10, .16]

    for instante in instantes:
        hora = instante.hour
        dormindo = hora < 7
        tela_ligada = (not dormindo) and gerador.random() < (
            0.55 if 8 <= hora <= 23 else 0.2
        )

        # A carga é um estado: começa quando a bateria está baixa e
        # termina quando chega a 100%.
        if not carregando and nivel_bateria < LIMITE_CARGA and gerador.random() < 0.5:
            carregando = True

        if tela_ligada:
            app_em_uso = gerador.choice(nomes_apps, p=probabilidades)
            cpu_base, consumo_app = APLICATIVOS[app_em_uso]
            uso_cpu = float(np.clip(gerador.normal(cpu_base, 8), 2, 100))
            brilho_tela = int(np.clip(gerador.normal(60, 20), 10, 100))
        else:
            app_em_uso, uso_cpu, brilho_tela = "Launcher", float(gerador.uniform(1, 6)), 0
            consumo_app = 0.004

        # O ruído é proporcional à descarga base. Assim evitamos quedas
        # negativas que viravam "queda zero" por causa do max(descarga, 0).
        descarga_base = 3.5 * (
            consumo_app + 0.0004 * brilho_tela + 0.0006 * uso_cpu
        )
        descarga = max(0.0, descarga_base * (1 + gerador.normal(0, 0.05)))

        if carregando:
            nivel_bateria = min(100.0, nivel_bateria + gerador.uniform(1.2, 2.2))
            carregando_agora = 1
            if nivel_bateria >= 100.0:
                carregando = False
        else:
            nivel_bateria = max(1.0, nivel_bateria - descarga)
            carregando_agora = 0

        linhas.append((
            nome_dispositivo,
            instante,
            round(nivel_bateria, 4),
            carregando_agora,
            app_em_uso,
            brilho_tela,
            round(uso_cpu, 1),
            int(tela_ligada),
        ))

    return pd.DataFrame(linhas, columns=[
        "dispositivo", "data_hora", "nivel_bateria", "carregando",
        "app_em_uso", "brilho_tela", "uso_cpu", "tela_ligada"])


if __name__ == "__main__":
    tabela = pd.concat(
        [simular_dispositivo(d) for d in DISPOSITIVOS],
        ignore_index=True,
    )
    tabela.to_csv(PASTA / "logs_bateria.csv", index=False)
    print(f"{len(tabela)} linhas geradas -> logs_bateria.csv")
