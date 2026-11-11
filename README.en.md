# Android Battery Discharge Analyzer

> Versão em português: [README.md](README.md)

Educational pipeline: synthetic data → SQLite → analytical SQL → image reports.

The goal of the project is to practice data generation, relational modeling, queries with
`JOIN`/CTE/window functions, and visualization with matplotlib.

## Requirements

- Python 3.10+ (tested with 3.12)
- pandas, numpy, and matplotlib (see `requirements.txt`)

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python gerar_dados.py            # generates logs_bateria.csv
python carregar_banco.py         # creates bateria.db
python analisar.py               # prints results and generates the PNGs
```

`carregar_banco.py` recreates the tables from scratch on every run. It is a
study script, not an incremental loader.

## Output

The `relatorios/` folder is created automatically and receives:

- `relatorio_<device>.png` — one per phone, with:
  - the **first 48 h** curve (counted from the device's first record);
  - the average discharge rate per hour of day, considering only periods
    without charging;
  - discharge by app, considering only periods with the screen on.
- `relatorio_comparativo.png` — discharge by app on each phone (screen on)
  and the ranking of average discharge per hour without charging.

Devices are read from the `dispositivos` table: if you add a new phone to the
database, it gets a report automatically.

## Data model

`dispositivos` 1—N `registros_bateria` N—1 `apps`

The `registros_bateria` table has:

- `UNIQUE (id_dispositivo, data_hora)`, to avoid duplicate samples from the
  same device at the same instant;
- `CHECK` constraints on the ranges of `nivel_bateria`, `brilho_tela`, and
  `uso_cpu`;
- `CHECK` constraints so `carregando` and `tela_ligada` accept only 0 or 1;
- `data_hora` validated with `datetime(data_hora)`;
- foreign keys enabled with `PRAGMA foreign_keys = ON` during loading;
- indexes on `(id_dispositivo, data_hora)` and `id_app`.

## What the metrics mean

- **%/hour without charging**: total battery drop divided by the real hours
  between samples, ignoring intervals when the device was charging. Hours are
  computed with `julianday`, so the code does not assume every sample is
  exactly 5 minutes apart.
- **Discharge by app (screen on)**: same idea, but using only intervals where
  `tela_ligada = 1`. This way the `Launcher` with the screen off is not
  compared to apps the user actually opened.
- **Device ranking**: purely demonstrative. The generator uses the same
  consumption model for all devices, so small differences in the ranking are
  simulation noise, not a real hardware comparison.

## Technical highlights

- Window function (`LAG ... OVER PARTITION BY`) to compute the drop between
  samples and the real elapsed time.
- Chained CTEs filtering out charging periods.
- Parameterized query (`:dispositivo`): the same query works for one device or
  for all of them.
- Automatic reports per device, with no hardcoded device list.
- Simple CSV validation before inserting into the database.

## Limitations / next steps

- Synthetic data: the consumption model is simplified and identical for every
  device. To compare real hardware, each device would need different
  parameters (capacity, efficiency, screen, etc.).
- Charging is simulated simply: it starts when the battery drops below 15%
  and goes up to 100%.
- SQLite is enough for the educational scope. Switching to PostgreSQL only
  makes sense if the project grows; it is not needed for this study.
- Ingesting real data from `adb shell dumpsys batterystats` is the next step.
  In that case, use the charge counter in mAh and timestamps with a time zone,
  because percentage has low resolution.
- The files `logs_bateria.csv`, `bateria.db`, and the PNGs are generated
  artifacts; they can be recreated by the scripts.
