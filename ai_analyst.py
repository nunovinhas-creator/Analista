# ai_analyst.py — Análise estatística automática (100% gratuito, sem API externa)
import math
from datetime import datetime, timezone
from utils import kelly_quarter, MARKET_BASE_ODDS


def _binomial_pvalue(n, k, p=0.5):
    """P-valor unilateral: P(X >= k | n, p)."""
    if n == 0 or k == 0:
        return 1.0
    if n > 200:
        # Aproximação normal com correcção de continuidade (evita O(n) loop)
        mu    = n * p
        sigma = (n * p * (1 - p)) ** 0.5
        z     = (k - 0.5 - mu) / sigma if sigma > 0 else float("inf")
        return round(min(1.0, 0.5 * math.erfc(z / math.sqrt(2))), 4)
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


def _best_segment(mapping, min_count):
    """Retorna (label, stats) do segmento com maior win_rate com pelo menos min_count picks, ou (None, None)."""
    filtered = {k: v for k, v in mapping.items() if v.get("count", 0) >= min_count}
    if not filtered:
        return None, None
    return max(filtered.items(), key=lambda x: x[1]["win_rate"])


def _picks_to_significance(wr, n_current, base=0.5, z=1.645):
    """Quantos picks no total para atingir p<0.05 com o WR actual (aproximação normal)."""
    if wr <= base:
        return None, None
    n_needed = math.ceil((z * 0.5 / (wr - base)) ** 2)
    remaining = max(0, n_needed - n_current)
    return n_needed, remaining


def generate_ai_report(over25_stats, football_stats):
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    lines = [f"## Análise Científica — {now}", ""]

    o25 = over25_stats
    n   = o25.get("resolved", 0)
    k   = o25.get("wins", 0)
    wr  = o25.get("win_rate", 0)
    roi = o25.get("roi", 0)
    clv = o25.get("avg_clv")
    max_dd = o25.get("max_drawdown", 0)

    # ── ALERTA CLV ─────────────────────────────────────────────────────────────
    if clv is not None:
        if clv < -2:
            lines.append("### ⚠️ Alerta CLV")
            lines.append(f"- **CLV Médio: {clv:+.2f}%** — as apostas estão a ser feitas DEPOIS do mercado mover.")
            lines.append("- As odds de fecho estão sistematicamente mais baixas do que as odds de entrada.")
            lines.append("- Acção recomendada: apostar mais cedo após publicação do pick (idealmente 24-48h antes).")
            lines.append("")
        elif clv >= 2:
            lines.append("### ✅ CLV Positivo")
            lines.append(f"- **CLV Médio: {clv:+.2f}%** — as apostas estão a ser feitas antes do mercado mover. Excelente sinal de edge real.")
            lines.append("")

    # ── OVER 2.5 SCANNER ──────────────────────────────────────────────────────
    lines.append("### Over 2.5 Scanner")

    if n >= 10:
        pval = _binomial_pvalue(n, k, 0.5)
        kq   = kelly_quarter(wr, MARKET_BASE_ODDS["o25"])
        ci_l = o25.get("ci_low", 0)
        ci_h = o25.get("ci_high", 1)
        lines.append(f"- **Significância:** {n} picks, {k} wins, WR={wr:.1%} [IC 95%: {ci_l:.0%}–{ci_h:.0%}] — {_sig(pval)}")
        lines.append(f"- **ROI:** {roi:+.2f}u · Max Drawdown: {max_dd:.2f}u · {'amostra sólida' if n >= 50 else 'aguardar 50+ picks para conclusões robustas'}")
        lines.append(f"- **Kelly ¼:** {kq:.1f}% da banca {'— apostar' if kq > 0 else '— edge negativo, não apostar'}")
        if clv is not None and clv < 0:
            lines.append(f"- **Ajuste CLV:** Kelly reduzido 50% → {kq*0.5:.1f}% da banca (CLV negativo)")

        # Deriva do modelo (rolling WR)
        rolling = o25.get("rolling_wr_series", [])
        if len(rolling) >= 5:
            current_rwr = rolling[-1]
            drift = current_rwr - wr
            if abs(drift) > 0.05:
                direction = "📈 a melhorar" if drift > 0 else "📉 a deteriorar"
                lines.append(f"- **Deriva do modelo:** WR últimos {min(20, n)} picks = {current_rwr:.1%} vs global {wr:.1%} → {direction}")

        # Melhor segmento (movimento)
        lbl, seg = _best_segment(o25.get("by_movement", {}), 5)
        if lbl:
            lines.append(f"- **Filtro recomendado:** movimento {lbl} → WR={seg['win_rate']:.1%} ({seg['count']} picks), ROI={seg['roi']:+.2f}u")

        # Melhor score
        lbl, seg = _best_segment(o25.get("by_score", {}), 3)
        if lbl:
            lines.append(f"- **Score óptimo:** {lbl} → WR={seg['win_rate']:.1%} — usar como score_sistema mínimo")

        # Melhor xG
        lbl, seg = _best_segment(o25.get("by_xg", {}), 3)
        if lbl:
            lines.append(f"- **xG óptimo:** {lbl} → WR={seg['win_rate']:.1%}")

        # Melhor banda de odds
        lbl, seg = _best_segment(o25.get("by_odds", {}), 3)
        if lbl:
            lines.append(f"- **Odds óptimas:** {lbl} → WR={seg['win_rate']:.1%} ({seg['count']} picks)")

        # Tendência 7 dias
        r7 = o25.get("recent_7d", {})
        if r7.get("count", 0) >= 3:
            trend = "📈 a melhorar" if r7["win_rate"] > wr else "📉 a piorar"
            lines.append(f"- **Últimos 7d:** WR={r7['win_rate']:.1%} ({r7['count']} picks) — {trend} vs média global")

        # Picks até significância
        n_need, n_rem = _picks_to_significance(wr, n)
        if n_need and n_rem > 0:
            lines.append(f"- **Até significância estatística (p<0.05):** {n_rem} picks adicionais (total {n_need} com WR actual de {wr:.1%})")

    else:
        lines.append(f"- ⚠️ Apenas {n} picks resolvidos — aguardar mínimo 10 para análise estatística")
        if n > 0:
            n_need, n_rem = _picks_to_significance(wr, n) if wr > 0.5 else (None, None)
            if n_need and n_rem > 0:
                lines.append(f"- Com WR actual de {wr:.1%}, precisas de {n_rem} picks adicionais para atingir p<0.05")

    # 1X2 Sharp
    p12 = o25.get("picks_1x2", {})
    if p12.get("resolved", 0) >= 5:
        pv   = _binomial_pvalue(p12["resolved"], p12.get("wins", 0), 0.50)
        kq2  = kelly_quarter(p12.get("win_rate", 0), MARKET_BASE_ODDS["1x2"])
        ci_l = p12.get("ci_low", 0)
        ci_h = p12.get("ci_high", 1)
        lines.append(f"- **1X2 Sharp:** {p12['resolved']} picks, WR={p12['win_rate']:.1%} [IC: {ci_l:.0%}–{ci_h:.0%}], ROI={p12['roi']:+.2f}u — {_sig(pv)}, Kelly ¼={kq2:.1f}%")

    lines.append("")

    # ── PICKS PENDENTES — STAKES ───────────────────────────────────────────────
    pending = o25.get("pending_with_kelly", [])
    if pending:
        lines.append("### Picks Pendentes — Stakes Recomendados")
        for p in pending:
            odds_str = f"{p['odds']:.2f}x" if p['odds'] else "—"
            if p["kelly_ok"]:
                clv_note = f" ⚠️ {p['kelly_note']}" if p.get("kelly_note") else ""
                score_str = f"{p['score']:.0f}" if p['score'] is not None else "—"
                xg_str    = f"{p['xg']:.1f}"    if p['xg']    is not None else "—"
                lines.append(f"- **{p['casa']} vs {p['fora']}** · Odds {odds_str} · Score {score_str} · xG {xg_str} · {p['movimento']} → **Kelly ¼: {p['kelly_pct']:.1f}% da banca**{clv_note}")
            else:
                lines.append(f"- {p['casa']} vs {p['fora']} · Odds {odds_str} → sem recomendação ({p.get('kelly_note', 'amostra insuficiente')})")
        lines.append("")

    # ── MATEMÁTICA DA BOLA ────────────────────────────────────────────────────
    fb         = football_stats
    per_market = fb.get("per_market", {})
    trebles    = fb.get("trebles", {})
    conf       = fb.get("by_confidence", {})
    bs         = fb.get("brier_scores", {})

    lines.append("### Matemática Da Bola")

    for label, key, base_odds in [("Over 2.5", "o25", MARKET_BASE_ODDS["o25"]), ("BTTS", "btts", MARKET_BASE_ODDS["btts"]), ("1X2", "1x2", MARKET_BASE_ODDS["1x2"]), ("xG (range)", "xg", 1.85)]:
        ms  = per_market.get(key, {})
        n_m = ms.get("picks", 0)
        k_m = ms.get("wins", 0)
        if n_m >= 5:
            pv   = _binomial_pvalue(n_m, k_m, 0.5)
            kq   = kelly_quarter(ms.get("win_rate", 0), base_odds)
            ci_l = ms.get("ci_low", 0)
            ci_h = ms.get("ci_high", 1)
            rel  = "" if ms.get("reliable") else " ⚠️n<20"
            lines.append(f"- **{label}:** {n_m} picks, WR={ms['win_rate']:.1%} [IC: {ci_l:.0%}–{ci_h:.0%}]{rel}, ROI={ms['roi']:+.0f}u — {_sig(pv)}, Kelly ¼={kq:.1f}%")

    # Brier Scores
    bs_o25  = bs.get("o25")
    bs_btts = bs.get("btts")
    if bs_o25 is not None:
        interp_o25  = "excelente" if bs_o25 < 0.15 else ("bom" if bs_o25 < 0.20 else ("aceitável" if bs_o25 < 0.25 else "fraco"))
        interp_btts = ("excelente" if bs_btts < 0.15 else ("bom" if bs_btts < 0.20 else ("aceitável" if bs_btts < 0.25 else "fraco"))) if bs_btts is not None else "N/D"
        bs_btts_str = f"{bs_btts:.4f}" if bs_btts is not None else "N/D"
        lines.append(f"- **Calibração (Brier Score):** O2.5={bs_o25:.4f} ({interp_o25}) · BTTS={bs_btts_str} ({interp_btts}) — quanto menor melhor (0=perfeito)")

    # Triplas
    n_tr = trebles.get("total", 0)
    if n_tr >= 3:
        pv_tr  = _binomial_pvalue(n_tr, trebles.get("won", 0), 0.33)
        avg_o  = trebles.get("avg_odds", 0)
        ci_l   = trebles.get("ci_low", 0)
        ci_h   = trebles.get("ci_high", 1)
        lines.append(f"- **Triplas:** {n_tr} jogadas, WR={trebles['win_rate']:.1%} [IC: {ci_l:.0%}–{ci_h:.0%}], ROI={trebles['roi']:+.1f}u, odds médias={avg_o:.2f}x — {_sig(pv_tr)}")

    # Calibração por confiança
    conf_lines = []
    for level in ["ALTA", "MÉDIA", "BAIXA"]:
        cs = conf.get(level, {})
        if cs.get("picks", 0) >= 3:
            rel  = "" if cs.get("reliable") else " ⚠️"
            icon = "✅" if cs["win_rate"] >= 0.60 else ("⚠️" if cs["win_rate"] >= 0.50 else "❌")
            conf_lines.append(f"{icon} {level}: WR={cs['win_rate']:.1%} ({cs['picks']} picks){rel}")
    if conf_lines:
        lines.append("- **Calibração confiança:** " + " | ".join(conf_lines))

    # Melhores ligas por O2.5
    best_lgs = [(lg, s) for lg, s in fb.get("by_league", {}).items() if s.get("o25_picks", 0) >= 5 and s["o25_wr"] >= 0.70]
    if best_lgs:
        best_lgs.sort(key=lambda x: x[1]["o25_wr"], reverse=True)
        lines.append("- **Ligas com maior edge O2.5:** " + ", ".join(f"{lg} ({s['o25_wr']:.1%})" for lg, s in best_lgs[:4]))

    lines.append("")

    # ── RECOMENDAÇÕES DE APOSTA ───────────────────────────────────────────────
    lines.append("### Recomendações para Lucro Real")

    recs = []
    o25_pm  = per_market.get("o25",  {})
    btts_pm = per_market.get("btts", {})

    if o25_pm.get("win_rate", 0) >= 0.60 and o25_pm.get("picks", 0) >= 15:
        kq = kelly_quarter(o25_pm["win_rate"], MARKET_BASE_ODDS["o25"])
        recs.append(f"1. **O2.5 Football** — mercado principal: apostar **{kq:.1f}% da banca** por pick (confiança ALTA/MÉDIA apenas)")
    if btts_pm.get("win_rate", 0) >= 0.60 and btts_pm.get("picks", 0) >= 10:
        kq = kelly_quarter(btts_pm["win_rate"], MARKET_BASE_ODDS["btts"])
        recs.append(f"2. **BTTS** — mercado secundário: apostar **{kq:.1f}% da banca** por pick (confiança ALTA/MÉDIA apenas)")
    if n_tr >= 3 and trebles.get("win_rate", 0) >= 0.40:
        recs.append("3. **Triplas** — 1 unidade fixa por tripla diária (sistema de selecção validado)")
    if n >= 20 and wr >= 0.55:
        kq = kelly_quarter(wr, MARKET_BASE_ODDS["o25"])
        kq_adj = round(kq * 0.5, 1) if (clv is not None and clv < 0) else kq
        recs.append(f"4. **Over 2.5 Scanner** — apostar **{kq_adj:.1f}% da banca**{' (ajustado por CLV negativo)' if kq_adj < kq else ''}")

    recs.append("- **Regra de ouro:** nunca exceder 3% da banca por aposta individual")
    recs.append("- **Stop-loss:** pausar um mercado se ROI cair > 10u abaixo do pico (drawdown de gestão de risco)")
    recs.append("- **Revisão de thresholds:** a cada 100 picks resolvidos com base nos dados actualizados")

    lines.extend(recs if recs else ["- Dados insuficientes para recomendações específicas. Aguardar mais picks resolvidos."])

    return "\n".join(lines)
