# data_quality/monitor.py — Monitor unificado de qualidade de dados
import json
import os
from datetime import datetime, timezone

_HERE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPORTS = os.path.join(_HERE, "docs")


def run_all_checks(over25_stats: dict, football_stats: dict) -> dict:
    """
    Executa todos os checks de qualidade de dados e devolve relatório unificado.
    Combina: label quality, drift detection, schema validation.
    """
    alerts  = []
    ts      = datetime.now(timezone.utc).isoformat()

    # ── 1. Label Quality ──────────────────────────────────────────────────────
    picks_quality = {}
    try:
        from data_quality.label_quality import quality_report
        raw_picks = over25_stats.get("all_picks_raw", [])
        if not raw_picks:
            # Reconstituir picks a partir de pending + resolved count
            picks_quality = {
                "n_total": over25_stats.get("total", 0),
                "n_resolved": over25_stats.get("resolved", 0),
                "n_suspected_errors": 0,
                "error_rate": 0.0,
            }
        else:
            picks_quality = quality_report(raw_picks)
        er = picks_quality.get("error_rate", 0.0)
        if er > 0.15:
            alerts.append(f"⚠️ Label quality: {er:.0%} de picks suspeitos ({picks_quality.get('n_suspected_errors',0)} registos)")
    except Exception as e:
        picks_quality = {"error": str(e)}
        alerts.append(f"⚠️ Label quality check falhou: {e}")

    # ── 2. Drift Detection ────────────────────────────────────────────────────
    drift_report = {}
    try:
        from data_quality.drift import run_drift_analysis
        drift_report = run_drift_analysis(over25_stats)
        if drift_report.get("drift", {}).get("drift_detected"):
            psi = drift_report.get("drift", {}).get("psi_score", 0)
            alerts.append(f"🔴 Drift detectado! PSI={psi:.3f} — distribuição de picks mudou significativamente")
        if drift_report.get("concept_drift", {}).get("drift_detected"):
            alerts.append("🔴 Concept drift: win rate divergiu do baseline (CUSUM positivo)")
    except Exception as e:
        drift_report = {"error": str(e)}
        alerts.append(f"⚠️ Drift check falhou: {e}")

    # ── 3. Schema Validation ─────────────────────────────────────────────────
    schema_validation = {"picks_valid": True, "history_valid": True,
                         "picks_errors": [], "history_errors": []}
    try:
        from data.schema.picks_schema   import validate_picks
        from data.schema.history_schema import validate_history

        raw_picks  = over25_stats.get("all_picks_raw", [])
        records    = football_stats.get("_raw_records", [])

        if raw_picks:
            vp, ep, _ = validate_picks(raw_picks)
            schema_validation["picks_valid"]  = vp
            schema_validation["picks_errors"] = ep[:5]
            if not vp:
                alerts.append(f"❌ Schema picks: {len(ep)} erros de validação")

        if records:
            vh, eh, _ = validate_history({"records": records})
            schema_validation["history_valid"]  = vh
            schema_validation["history_errors"] = eh[:5]
            if not vh:
                alerts.append(f"❌ Schema history: {len(eh)} erros de validação")

    except Exception as e:
        schema_validation["error"] = str(e)

    # ── 4. Alertas automáticos de métricas ───────────────────────────────────
    wr  = over25_stats.get("win_rate", 0)
    roi = over25_stats.get("roi", 0)
    n   = over25_stats.get("resolved", 0)
    dd  = over25_stats.get("max_drawdown", 0)
    clv = over25_stats.get("avg_clv")

    if n >= 10 and wr < 0.45:
        alerts.append(f"🔴 Win rate baixo: {wr:.1%} (abaixo do break-even de 52.6%)")
    if dd > 10:
        alerts.append(f"⚠️ Drawdown elevado: -{dd:.2f}u — considerar pausa")
    if clv is not None and clv < -2:
        alerts.append(f"⚠️ CLV negativo: {clv:+.2f}% — apostas feitas depois do mercado mover")
    if roi < -5 and n >= 20:
        alerts.append(f"🔴 ROI negativo persistente: {roi:+.2f}u com {n} picks")

    fb_o25 = football_stats.get("per_market", {}).get("o25", {})
    if fb_o25.get("picks", 0) >= 20 and fb_o25.get("win_rate", 0) < 0.50:
        alerts.append(f"⚠️ Football O2.5 WR abaixo do break-even: {fb_o25['win_rate']:.1%}")

    # ── 5. Health overall ────────────────────────────────────────────────────
    n_critical = sum(1 for a in alerts if a.startswith("🔴"))
    n_warn     = sum(1 for a in alerts if a.startswith("⚠️"))
    if n_critical > 0:
        overall_health = "critical"
    elif n_warn > 0:
        overall_health = "warning"
    else:
        overall_health = "healthy"

    return {
        "timestamp":         ts,
        "picks_quality":     picks_quality,
        "drift":             drift_report,
        "schema_validation": schema_validation,
        "alerts":            alerts,
        "n_alerts":          len(alerts),
        "overall_health":    overall_health,
    }


def format_monitor_report(monitor_dict: dict) -> str:
    """Formata relatório de monitorização em texto legível."""
    lines = [
        f"╔══ MONITOR DE QUALIDADE — {monitor_dict.get('timestamp','')[:16]} ══╗",
        f"  Estado: {monitor_dict.get('overall_health','?').upper()}",
        f"  Alertas: {monitor_dict.get('n_alerts', 0)}",
        "",
    ]

    alerts = monitor_dict.get("alerts", [])
    if alerts:
        lines.append("  ALERTAS:")
        for a in alerts:
            lines.append(f"    {a}")
        lines.append("")

    pq = monitor_dict.get("picks_quality", {})
    if pq and not pq.get("error"):
        lines.append(f"  Label Quality: {pq.get('n_total',0)} picks | {pq.get('error_rate',0):.1%} suspeitos")

    dr = monitor_dict.get("drift", {})
    if dr and not dr.get("error"):
        drift_inner = dr.get("drift", {})
        psi = drift_inner.get("psi_score", 0)
        lines.append(f"  Drift (PSI): {psi:.3f} — {drift_inner.get('summary','?')}")

    sv = monitor_dict.get("schema_validation", {})
    p_ok = "✅" if sv.get("picks_valid", True) else "❌"
    h_ok = "✅" if sv.get("history_valid", True) else "❌"
    lines.append(f"  Schema picks={p_ok}  history={h_ok}")
    lines.append("╚══════════════════════════════════════════════╝")
    return "\n".join(lines)


def save_monitor_report(monitor_dict: dict, path=None):
    """Guarda relatório JSON em docs/monitor_report.json."""
    path = path or os.path.join(_REPORTS, "monitor_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(monitor_dict, f, ensure_ascii=False, indent=2, default=str)
    print(f"[monitor] relatório guardado em {path}")
