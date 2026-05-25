# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é este projecto

**Analista** lê permanentemente os dados de dois repositórios externos e produz dashboards, análise científica diária e um relatório enviado por email às 21:30 Lisboa (20:30 UTC).

Repositórios fonte (somente leitura, via raw.githubusercontent.com):
- `nunovinhas-creator/over25-scanner` — scanner estático HTML com picks Over 2.5 e 1X2 sharp guardados em `data/picks.json` e `data/picks_1x2.json`
- `nunovinhas-creator/football-dashboard` — pipeline Python (Matemática Da Bola) com histórico em `docs/history.json` e `docs/trebles.json`

## Comandos principais

```bash
pip install -r requirements.txt

# Análise + dashboards (sem email)
python main.py analyze

# Análise + dashboards + IA + email
python main.py report
```

Variáveis de ambiente necessárias para `report`:
```
ANTHROPIC_API_KEY   # Claude API para análise científica
GMAIL_USER          # endereço Gmail que envia o email
GMAIL_APP_PASSWORD  # Google App Password (não a password normal)
```

## Arquitectura

```
main.py                    # orquestrador — parse modo, chama os módulos em sequência
fetcher.py                 # fetch JSON via raw.githubusercontent.com (requests, timeout=20s)
analyze_over25.py          # métricas sobre picks.json: WR, ROI, CLV, streak, por movimento/score/xG/liga
analyze_football.py        # métricas sobre history.json + trebles.json: por mercado, confiança, liga, trebles
dashboard_over25.py        # gera docs/over25_dashboard.html (Chart.js CDN, dark theme)
dashboard_football.py      # gera docs/football_dashboard.html (Chart.js CDN, dark theme)
ai_analyst.py              # chama claude-opus-4-7 para análise estatística + propostas
emailer.py                 # HTML email via Gmail SMTP_SSL porta 465
.github/workflows/analista.yml  # cron 07:00, 14:00, 20:30 UTC; commit+push docs/ automático
```

Fluxo de dados: `fetcher → analyze_* → gen_dashboard_* → ai_analyst → emailer`  
Sem base de dados — todo o estado vem dos repos externos; os dashboards são o único output persistido.

## CI/CD — GitHub Actions

Três cron jobs (todos no mesmo workflow `analista.yml`):
- **07:00 UTC** → `python main.py analyze`
- **14:00 UTC** → `python main.py analyze`
- **20:30 UTC** → `python main.py report` (inclui email)

O workflow deteta o modo automaticamente pela hora UTC; pode ser forçado via `workflow_dispatch` com input `mode=report`.

Após cada run faz `git add docs/ && git commit && git push` para actualizar os dashboards no GitHub Pages.

## GitHub Pages

Os dashboards ficam disponíveis em:
- `https://nunovinhas-creator.github.io/Analista/over25_dashboard.html`
- `https://nunovinhas-creator.github.io/Analista/football_dashboard.html`

Activar em: Settings → Pages → Source: `main` branch, pasta `/docs`.

## Secrets necessários no repositório

| Secret | Descrição |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `GMAIL_USER` | endereço Gmail de envio |
| `GMAIL_APP_PASSWORD` | App Password do Google (não a password da conta) |

## Convenções de código

- Estilo procedural, sem classes, igual aos repositórios fonte
- Nomes de funções/variáveis em inglês, comentários em português
- Sem type hints
- Error handling: `try/except` com `print(f"[WARN] ...")` — sem logging framework
- Datas sempre UTC via `datetime.now(timezone.utc)`
- Output em `docs/` (criado automaticamente se não existir)

## Estrutura dos dados fonte

### over25-scanner — picks.json
```json
{
  "data": "ISO datetime",
  "casa": "home team", "fora": "away team", "liga": "league",
  "odds_over": 1.85, "movimento": "SHORTENING|DRIFTING",
  "xg_total": 2.8, "btts_prob": 0.62, "score_sistema": 78,
  "result_over25": "WIN|LOSS|null", "clv": -0.05
}
```

### football-dashboard — history.json records[]
```json
{
  "date": "2026-05-22", "league": "Premier League",
  "home": "Arsenal", "away": "Chelsea",
  "prob_home": 0.52, "prob_draw": 0.24, "prob_away": 0.24,
  "prob_o25": 0.71, "prob_btts": 0.58,
  "xg_home": 1.8, "xg_away": 1.2,
  "confidence": "ALTA|MÉDIA|BAIXA",
  "pick_1x2": true, "hit_1x2": true,
  "pick_o25": true, "hit_o25": false,
  "pick_btts": false, "pick_xg": false
}
```
