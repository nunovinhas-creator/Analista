# Analista — Sistema de Análise de Apostas de Futebol

Pipeline automatizado de análise de apostas desportivas que lê dados de dois repositórios externos, aplica modelos estatísticos e produz dashboards, relatórios de backtesting e análise diária enviada por email.

---

## Dashboards (GitHub Pages)

| Dashboard | URL |
|---|---|
| Over 2.5 Scanner | https://nunovinhas-creator.github.io/Analista/over25_dashboard.html |
| Matemática Da Bola | https://nunovinhas-creator.github.io/Analista/football_dashboard.html |
| Hoje e Amanhã | https://nunovinhas-creator.github.io/Analista/today_dashboard.html |
| Advanced Analytics | https://nunovinhas-creator.github.io/Analista/advanced_dashboard.html |
| Backtest Report | https://nunovinhas-creator.github.io/Analista/backtest_report.html |

---

## Arquitectura

```
fetcher
   └─→ validate (pandera schemas)
          └─→ analyze (over25 / football)
                 └─→ model (poisson / elo / kelly)
                        └─→ backtest (engine + strategies)
                               └─→ dashboard (Chart.js + Plotly)
                                      └─→ email (Gmail SMTP)
```

### Módulos

| Ficheiro / Pacote | Descrição |
|---|---|
| `main.py` | Orquestrador — parse modo (analyze/report), invoca módulos em sequência |
| `fetcher.py` | Fetch JSON via raw.githubusercontent.com (requests, timeout=20s) |
| `analyze_over25.py` | Métricas sobre picks.json: WR, ROI, CLV, streak, por movimento/score/xG/liga |
| `analyze_football.py` | Métricas sobre history.json + trebles.json: por mercado, confiança, liga |
| `analyze_today.py` | Análise de picks do dia e previsões para amanhã |
| `picks_tracker.py` | Rastreio de picks activos e histórico de resultados |
| `dashboard_over25.py` | Gera `docs/over25_dashboard.html` (Chart.js CDN, dark theme) |
| `dashboard_football.py` | Gera `docs/football_dashboard.html` (Chart.js CDN, dark theme) |
| `dashboard_today.py` | Gera `docs/today_dashboard.html` com picks do dia |
| `ai_analyst.py` | Análise estatística local (significância, Kelly, recomendações) |
| `emailer.py` | HTML email via Gmail SMTP_SSL porta 465 |
| `utils.py` | Utilitários partilhados (datas UTC, formatação) |
| `models/math/poisson.py` | Modelo de Poisson bivariado para previsão de golos |
| `models/math/skellam.py` | Distribuição Skellam para diferença de golos |
| `models/math/elo.py` | Sistema de rating Elo adaptado para futebol |
| `models/math/kelly.py` | Critério de Kelly para dimensionamento de apostas |
| `models/metrics/calibration.py` | Curvas de calibração e Brier Score |
| `models/metrics/edge.py` | Cálculo de edge sobre odds de mercado |
| `data/schema/picks_schema.py` | Schema Pandera para validação de picks.json |
| `data/schema/history_schema.py` | Schema Pandera para validação de history.json |
| `data_quality/monitor.py` | Monitorização de drift e label quality |
| `backtesting/engine.py` | Motor de backtesting com gestão de bankroll |
| `backtesting/strategies.py` | Estratégias: flat, Kelly, proporcional |
| `backtesting/report.py` | Geração de relatório HTML de backtesting |
| `dashboard/gen_advanced.py` | Dashboard avançado com Plotly (interactive) |
| `dashboard/plotly_charts.py` | Gráficos Plotly reutilizáveis |
| `pipeline/etl.py` | ETL pipeline para transformação de dados brutos |

---

## Instalação

```bash
pip install -r requirements.txt

# Análise + dashboards (sem email)
python main.py analyze

# Análise + dashboards + IA + email
python main.py report
```

### Variáveis de ambiente necessárias para `report`

```
GMAIL_USER          # endereço Gmail que envia o email
GMAIL_APP_PASSWORD  # Google App Password (não a password normal)
```

---

## Módulos Científicos

### `models/math/`

- **`poisson.py`** — Modelo de Poisson bivariado: estima taxa de golos de cada equipa e calcula probabilidades para todos os scorelines. Base para mercados Over/Under e Resultado.
- **`skellam.py`** — Distribuição Skellam (diferença de duas Poissons independentes): calcula probabilidades exactas de vitória/empate/derrota sem assumir independência perfeita.
- **`elo.py`** — Rating Elo com factores de actualização por margem de golos e importância do jogo. Produz probabilidades comparáveis às de mercado.
- **`kelly.py`** — Critério de Kelly completo e fraccionário (1/4 Kelly). Dimensiona apostas em função do edge e bankroll.

### `models/metrics/`

- **`calibration.py`** — Curvas de calibração, ECE (Expected Calibration Error) e Brier Score. Avalia se as probabilidades do modelo são confiáveis.
- **`edge.py`** — Calcula edge sobre odds de mercado: `edge = p_model / p_implied - 1`. Filtra apostas com edge positivo.

### `data/schema/`

Schemas Pandera que definem tipos, intervalos e invariantes dos dados fonte. Garantem que mudanças nos repositórios externos não passam silenciosamente.

### `data_quality/`

- **`monitor.py`** — Detecção de drift estatístico (PSI, KS-test), label quality checks e alertas quando métricas saem dos intervalos históricos.

### `backtesting/`

- **`engine.py`** — Simula apostas históricas com gestão de bankroll realista; suporta múltiplas estratégias em paralelo.
- **`strategies.py`** — Estratégias incluídas: flat stake, Kelly, proporcional ao edge, threshold variável.
- **`report.py`** — Relatório HTML interactivo com equity curve, drawdown, métricas por liga/mês.

### `dashboard/`

- **`gen_advanced.py`** — Dashboard Plotly com gráficos interactivos: ROI por liga, calibração, equity curve, heatmaps de performance.
- **`plotly_charts.py`** — Componentes Plotly reutilizáveis partilhados pelos dashboards.

### `pipeline/`

- **`etl.py`** — ETL que normaliza os dados brutos dos dois repositórios fonte para um formato interno consistente.

---

## Validação de Dados

Os schemas Pandera em `data/schema/` definem:
- Tipos de coluna e intervalos válidos (ex: odds entre 1.01 e 50.0)
- Campos obrigatórios vs opcionais
- Invariantes de negócio (ex: `result_over25` só pode ser WIN, LOSS ou null)

Para correr validação manualmente:

```bash
python -c "
from fetcher import fetch_all_data
from data.schema.picks_schema import validate_picks
from data.schema.history_schema import validate_history
data = fetch_all_data()
valid, errors, n = validate_picks(data['over25_picks'])
print(f'Picks: {\"OK\" if valid else \"FAIL\"} — {n} registos, {len(errors)} erros')
"
```

Para correr os testes:

```bash
python -m pytest tests/ -v --tb=short
```

---

## Backtesting

O motor de backtesting simula apostas no histórico disponível em `football_history` e compara várias estratégias de staking:

```bash
python -c "
from fetcher import fetch_all_data
from backtesting.engine import compare_strategies
from backtesting.report import save_report
data = fetch_all_data()
records = data['football_history'].get('records', [])
results = compare_strategies(records, market='o25')
for name, r in results.items():
    print(f'{name}: ROI={r.roi:+.2f}u, WR={r.win_rate:.1%}, MaxDD={r.max_drawdown:.2f}u, n={r.n_bets}')
save_report(results)
"
```

Métricas reportadas: ROI (unidades), Win Rate, Max Drawdown, Sharpe Ratio, número de apostas, equity curve.

---

## CI/CD Workflows

| Workflow | Trigger | Acção |
|---|---|---|
| `analista.yml` | A cada 2h + 20:30 UTC | `python main.py analyze/report` + commit `docs/` |
| `data-quality.yml` | Diário 06:00 UTC | Checks qualidade + validação Pandera + pytest |
| `backtesting.yml` | Semanal segunda 08:00 UTC | Backtest completo + dashboard avançado |
| `tests.yml` | Push para main (`.py`, `requirements.txt`) + PR | `pytest tests/` |

Todos os workflows com `permissions: contents: write` fazem `git push` com retry (4 tentativas, backoff linear).

---

## Thresholds de Pick (calibrados)

| Mercado | Threshold mínimo | Condição adicional |
|---|---|---|
| Over 2.5 | Probabilidade ≥ 60% | — |
| BTTS | Probabilidade ≥ 60% | — |
| 1X2 | Probabilidade ≥ 55% | Confiança ALTA ou MÉDIA apenas |

---

## Secrets necessários no repositório

| Secret | Descrição |
|---|---|
| `GMAIL_USER` | Endereço Gmail de envio |
| `GMAIL_APP_PASSWORD` | App Password do Google (não a password da conta) |

Configurar em: **Settings → Secrets and variables → Actions → New repository secret**
