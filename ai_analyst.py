# ai_analyst.py — Análise científica via Claude API (Anthropic)
import json
import os

import anthropic

MODEL = "claude-opus-4-7"


def _summarise(stats: dict, max_records: int = 5) -> dict:
    """Remove séries longas do dict para reduzir tokens enviados ao Claude."""
    s = dict(stats)
    for key in ("cumulative_roi", "cum_o25_series", "cum_btts_series", "cum_treble_series", "daily"):
        s.pop(key, None)
    # Limita by_league a top 5
    if "by_league" in s:
        s["by_league"] = dict(list(s["by_league"].items())[:5])
    return s


def generate_ai_report(over25_stats: dict, football_stats: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[WARN] ANTHROPIC_API_KEY não definida — análise IA omitida")
        return ""

    client = anthropic.Anthropic(api_key=api_key)

    context = json.dumps({
        "over25_scanner": _summarise(over25_stats),
        "football_dashboard": _summarise(football_stats),
    }, ensure_ascii=False, default=str)

    prompt = f"""És um data scientist especialista em mercados de apostas desportivas, modelação preditiva e análise estatística de football.

Abaixo estão as estatísticas detalhadas de dois sistemas de previsão de futebol.

```json
{context}
```

Faz uma análise completa e científica em Português, cobrindo obrigatoriamente estes 5 blocos:

## 1. Avaliação Estatística
- A win rate atual é estatisticamente significativa acima do acaso? (binomial test, IC 95%)
- O ROI é sustentável com este tamanho de amostra?
- Há evidência de skill real vs sorte?

## 2. Análise de Padrões
- Quais segmentos/filtros mostram edge consistente?
- Há sinais de degradação de performance ou adaptação do mercado?
- Calibração: as probabilidades estimadas correspondem aos resultados reais?

## 3. Propostas de Melhoria Técnica
- Melhorias no pipeline de dados e fiabilidade da API
- Features adicionais que melhorariam o poder preditivo
- Otimização de thresholds com base nos dados atuais

## 4. Segurança e Robustez
- Vulnerabilidades na arquitetura atual
- Recomendações para gestão de API keys e resiliência a falhas

## 5. Estratégia de Apostas para Lucro Real
- Dimensionamento de apostas (Kelly criterion — cálculo específico com os dados fornecidos)
- Quais mercados e segmentos focar para lucro real e sustentável
- Gestão de banca recomendada
- Estratégia de risco ajustado com ROI esperado anualizado

Sê específico com números e raciocínio estatístico. Evita generalidades. Cada proposta deve ter uma justificação baseada nos dados."""

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text
        print(f"[ai] análise gerada ({len(text)} caracteres)")
        return text
    except Exception as e:
        print(f"[WARN] Claude API erro: {e}")
        return f"Análise IA indisponível: {e}"
