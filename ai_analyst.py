# ai_analyst.py — Análise estatística automática (100% gratuito, sem API externa)
import math
from datetime import datetime, timezone


def _binomial_pvalue(n, k, p=0.5):
    """P-valor unilateral: probabilidade de obter >= k wins em n tentativas com taxa base p."""
    if n == 0 or k == 0:
        return 1.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return round(min(1.0, total), 4)


def _sig(pval):
    if pval < 0.01:
        return "✅ altamente significativo (p<0.01)"
    elif pval < 0.05:
        return "✅ significativo (p<0.05)"
    elif pval < 0.10:
        return "⚠️ marginalmente significativo (p<0.10)"
    else:
        return f"❌ não significativo (p={pval:.2f}) — pode ser sorte"


def _kelly_quarter(win_rate, avg_odds=1.90):
    """¼ Kelly como percentagem da banca (mais conservador e seguro)."""
    if avg_odds <= 1.01 or win_rate <= 0:
        return 0.0
    b = avg_odds - 1
    f = (win_rate * b - (1 - win_rate)) / b
    return max(0.0, f / 4)


def generate_ai_report(over25_stats, football_stats):
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lines = [f"## Análise Científica — {now}", ""]

    # ── OVER 2.5 SCANNER ──────────────────────────────────────────────────────
    o   = over25_stats
    n   = o.get("resolved", 0)
    k   = o.get("wins", 0)
    wr  = o.get("win_rate", 0)
    roi = o.get("roi", 0)

    lines.append("### Over 2.5 Scanner")
    if n >= 10:
        pval = _binomial_pvalue(n, k, 0.5)
        kq   = _kelly_quarter(wr) * 100
        lines.append(f"- **Significância estatística:** {n} picks, {k} wins ({wr:.1%}) — {_sig(pval)}")
        lines.append(f"- **ROI:** {roi:+.2f}u ({'amostra sólida' if n >= 50 else 'amostra ainda pequena — mínimo 50 picks para conclusões robustas'})")
        lines.append(f"- **Kelly ¼:** {kq:.1f}% da banca por aposta {'— apostar' if kq > 0 else '— edge negativo, não apostar'}")

        # Melhor segmento por movimento
        by_mov = {k_: v for k_, v in o.get("by_movement", {}).items() if v["count"] >= 5}
        if by_mov:
            best = max(by_mov.items(), key=lambda x: x[1]["win_rate"])
            lines.append(f"- **Filtro recomendado:** odds em {best[0]} → WR={best[1]['win_rate']:.1%} ({best[1]['count']} picks), ROI={best[1]['roi']:+.2f}u")

        # Melhor intervalo de score
        by_score = {k_: v for k_, v in o.get("by_score", {}).items() if v["count"] >= 3}
        if by_score:
            best_s = max(by_score.items(), key=lambda x: x[1]["win_rate"])
            lines.append(f"- **Score ótimo:** {best_s[0]} → WR={best_s[1]['win_rate']:.1%} — usar como score_sistema mínimo")

        # Melhor intervalo de xG
        by_xg = {k_: v for k_, v in o.get("by_xg", {}).items() if v["count"] >= 3}
        if by_xg:
            best_x = max(by_xg.items(), key=lambda x: x[1]["win_rate"])
            lines.append(f"- **xG ótimo:** {best_x[0]} → WR={best_x[1]['win_rate']:.1%} — combinar com score_sistema mínimo")

        # Tendência 7 dias
        r7 = o.get("recent_7d", {})
        if r7.get("count", 0) >= 3:
            trend = "📈 a melhorar" if r7["win_rate"] > wr else "📉 a piorar"
            lines.append(f"- **Últimos 7d:** WR={r7['win_rate']:.1%} ({r7['count']} picks) — {trend} vs média global")
    else:
        lines.append(f"- ⚠️ Apenas {n} picks resolvidos — aguardar mínimo 10 para análise estatística")

    # 1X2 Sharp
    p12 = o.get("picks_1x2", {})
    if p12.get("resolved", 0) >= 5:
        pv  = _binomial_pvalue(p12["resolved"], p12.get("wins", 0), 0.50)
        kq2 = _kelly_quarter(p12.get("win_rate", 0), 2.20) * 100
        lines.append(f"- **1X2 Sharp:** {p12['resolved']} picks, WR={p12['win_rate']:.1%}, ROI={p12['roi']:+.2f}u — {_sig(pv)}, Kelly ¼={kq2:.1f}%")

    lines.append("")

    # ── MATEMÁTICA DA BOLA ────────────────────────────────────────────────────
    f    = football_stats
    pm   = f.get("per_market", {})
    tr   = f.get("trebles", {})
    conf = f.get("by_confidence", {})

    lines.append("### Matemática Da Bola")

    for label, key, base_odds in [("Over 2.5", "o25", 1.90), ("BTTS", "btts", 1.80), ("1X2", "1x2", 2.20), ("xG (range)", "xg", 1.85)]:
        ms   = pm.get(key, {})
        n_m  = ms.get("picks", 0)
        k_m  = ms.get("wins", 0)
        if n_m >= 5:
            pv  = _binomial_pvalue(n_m, k_m, 0.5)
            kq  = _kelly_quarter(ms.get("win_rate", 0), base_odds) * 100
            lines.append(f"- **{label}:** {n_m} picks, WR={ms['win_rate']:.1%}, ROI={ms['roi']:+.0f}u — {_sig(pv)}, Kelly ¼={kq:.1f}%")

    # Triplas
    n_tr = tr.get("total", 0)
    if n_tr >= 3:
        pv_tr = _binomial_pvalue(n_tr, tr.get("won", 0), 0.33)
        avg_o = tr.get("avg_odds", 0)
        lines.append(f"- **Triplas:** {n_tr} jogadas, WR={tr['win_rate']:.1%}, ROI={tr['roi']:+.1f}u, odds médias={avg_o:.2f}x — {_sig(pv_tr)}")

    # Calibração por confiança
    conf_lines = []
    for level in ["ALTA", "MÉDIA", "BAIXA"]:
        cs = conf.get(level, {})
        if cs.get("picks", 0) >= 3:
            icon = "✅" if cs["win_rate"] >= 0.60 else ("⚠️" if cs["win_rate"] >= 0.50 else "❌")
            conf_lines.append(f"{icon} {level}: WR={cs['win_rate']:.1%} ({cs['picks']} picks)")
    if conf_lines:
        lines.append("- **Calibração:** " + " | ".join(conf_lines))

    # Melhores ligas por O2.5
    best_lgs = [(lg, s) for lg, s in f.get("by_league", {}).items() if s.get("o25_picks", 0) >= 5 and s["o25_wr"] >= 0.70]
    if best_lgs:
        best_lgs.sort(key=lambda x: x[1]["o25_wr"], reverse=True)
        lines.append("- **Ligas com maior edge O2.5:** " + ", ".join(f"{lg} ({s['o25_wr']:.1%})" for lg, s in best_lgs[:4]))

    lines.append("")

    # ── RECOMENDAÇÕES DE APOSTA ───────────────────────────────────────────────
    lines.append("### Recomendações para Lucro Real")

    recs = []
    o25_pm  = pm.get("o25",  {})
    btts_pm = pm.get("btts", {})

    if o25_pm.get("win_rate", 0) >= 0.60 and o25_pm.get("picks", 0) >= 15:
        kq = _kelly_quarter(o25_pm["win_rate"], 1.90) * 100
        recs.append(f"1. **O2.5 Football** — mercado principal: apostar **{kq:.1f}% da banca** por pick (confiança ALTA/MÉDIA apenas)")
    if btts_pm.get("win_rate", 0) >= 0.60 and btts_pm.get("picks", 0) >= 10:
        kq = _kelly_quarter(btts_pm["win_rate"], 1.80) * 100
        recs.append(f"2. **BTTS** — mercado secundário: apostar **{kq:.1f}% da banca** por pick (confiança ALTA/MÉDIA apenas)")
    if n_tr >= 3 and tr.get("win_rate", 0) >= 0.40:
        recs.append("3. **Triplas** — 1 unidade fixa por tripla diária (sistema de selecção já validado)")
    if n >= 20 and wr >= 0.55:
        kq = _kelly_quarter(wr) * 100
        recs.append(f"4. **Over 2.5 Scanner** — apostar **{kq:.1f}% da banca** (score_sistema ≥ 60, movimento SHORTENING prioritário)")

    recs.append("- **Regra de ouro:** nunca exceder 3% da banca por aposta individual")
    recs.append("- **Revisão de thresholds:** a cada 100 picks resolvidos com base nos dados actualizados")
    recs.append("- **Stop-loss:** parar de apostar num mercado se ROI cair > 10 unidades abaixo do pico")

    lines.extend(recs if recs else ["- Dados insuficientes para recomendações específicas. Aguardar mais picks resolvidos."])

    return "\n".join(lines)
