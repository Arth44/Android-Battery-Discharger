# Android Battery Discharge Analyzer

> English version: [README.en.md](README.en.md)

Pipeline didático: dados sintéticos → SQLite → SQL analítico → relatórios em imagem.

O objetivo do projeto é praticar geração de dados, modelagem relacional, consultas com
`JOIN`/CTE/window functions e visualização com matplotlib.

## Requisitos

- Python 3.10+ (testado com 3.12)
- pandas, numpy e matplotlib (veja `requirements.txt`)

## Como rodar

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python gerar_dados.py            # gera logs_bateria.csv
python carregar_banco.py         # cria bateria.db
python analisar.py               # imprime resultados e gera os PNGs
```

O `carregar_banco.py` recria as tabelas do zero a cada execução. Ele é um
script de estudo, não um carregador incremental.

## Saída

A pasta `relatorios/` é criada automaticamente e recebe:

- `relatorio_<dispositivo>.png` — um por celular, com:
  - curva das **primeiras 48 h** (contadas a partir do primeiro registro do
    aparelho);
  - taxa média de descarga por hora do dia, considerando apenas períodos sem
    carregamento;
  - drenagem por app, considerando apenas períodos com a tela ligada.
- `relatorio_comparativo.png` — drenagem por app em cada celular (tela ligada)
  e ranking de descarga média por hora sem carregamento.

Os dispositivos são lidos da tabela `dispositivos`: se você adicionar um
celular novo ao banco, ele ganha um relatório automaticamente.

## Modelo de dados

`dispositivos` 1—N `registros_bateria` N—1 `apps`

A tabela `registros_bateria` tem:

- `UNIQUE (id_dispositivo, data_hora)`, para não duplicar amostras do mesmo
  aparelho no mesmo instante;
- `CHECK` de faixa para `nivel_bateria`, `brilho_tela` e `uso_cpu`;
- `CHECK` para `carregando` e `tela_ligada` aceitarem apenas 0 ou 1;
- validação de `data_hora` com `datetime(data_hora)`;
- foreign keys habilitadas com `PRAGMA foreign_keys = ON` no carregamento;
- índices em `(id_dispositivo, data_hora)` e `id_app`.

## O que as métricas significam

- **%/hora sem carregamento**: queda total de bateria dividida pelas horas
  reais entre as amostras, desconsiderando intervalos em que o aparelho estava
  carregando. As horas são calculadas com `julianday`, então o código não
  assume que toda amostra tem exatamente 5 minutos.
- **Drenagem por app (tela ligada)**: mesma ideia, mas usando apenas os
  intervalos em que `tela_ligada = 1`. Assim o `Launcher` com a tela desligada
  não é comparado com apps que o usuário realmente abriu.
- **Ranking de dispositivos**: é apenas demonstrativo. O gerador usa o mesmo
  modelo de consumo para todos os aparelhos; portanto, diferenças pequenas no
  ranking são ruído da simulação, não uma comparação real de hardware.

## Destaques técnicos

- Window function (`LAG ... OVER PARTITION BY`) para calcular a queda entre
  amostras e o tempo real decorrido.
- CTEs encadeadas filtrando períodos de carregamento.
- Consulta parametrizada (`:dispositivo`): a mesma query serve para um
  aparelho ou para todos.
- Relatórios automáticos por dispositivo, sem lista fixa de aparelhos.
- Validação simples do CSV antes de inserir no banco.

## Limitações / próximos passos

- Dados sintéticos: o modelo de consumo é simplificado e igual para todos os
  aparelhos. Para comparar hardware de verdade, seria preciso dar parâmetros
  diferentes a cada dispositivo (capacidade, eficiência, tela etc.).
- A carga é simulada de forma simples: começa quando a bateria fica abaixo de
  15% e vai até 100%.
- SQLite é suficiente para o escopo didático. Trocar por PostgreSQL só faz
  sentido se o projeto crescer; não é necessário para este estudo.
- A ingestão de `adb shell dumpsys batterystats` real fica como próximo passo.
  Nesse caso, vale usar o contador de carga em mAh e timestamps com fuso
  horário, porque a porcentagem tem pouca resolução.
- Os arquivos `logs_bateria.csv`, `bateria.db` e os PNGs são artefatos gerados;
  podem ser recriados pelos scripts.
