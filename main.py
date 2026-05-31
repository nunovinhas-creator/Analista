# main.py — Orquestrador principal do Analista
# Uso: python main.py [analyze|report]
#   analyze — fetch + análise + dashboards (sem email)
#   report  — fetch + análise + dashboards + IA + email
import sys
from datetime import datetime, timezone

from fetcher           import fetch_all_data
from analyze_over25    import analyze_over25
from analyze_football  import analyze_football
from analyze_today     import analyze_today
from dashboard_over25  import gen_dashboard_over25
from dashboard_football import gen_dashboard_football
from dashboard_today   import gen_dashboard_today
from ai_analyst        import generate_ai_report
from emailer           import send_daily_report


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    now  = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[analista] {now} — modo={mode}")

    data = fetch_all_data()

    over25_stats   = analyze_over25(data["over25_picks"], data["over25_picks_1x2"])
    football_stats = analyze_football(data["football_history"], data["football_trebles"])

    try:
        today_stats = analyze_today(data["football_history"], data["football_dashboard_html"])
    except Exception as e:
        print(f"[ERROR] Falha em analyze_today: {e}")
        today_stats = {
            "today": "", "tomorrow": "", "total_games": 0,
            "total_picks": 0, "strong_picks": 0, "games": [],
            "tracker": {"total_resolved": 0, "total_pending": 0},
        }

    gen_dashboard_over25(over25_stats)
    gen_dashboard_football(football_stats)
    gen_dashboard_today(today_stats)

    print(f"[analista] over25: {over25_stats['resolved']} picks resolvidos, WR={over25_stats['win_rate']:.1%}, ROI={over25_stats['roi']:+.2f}u")
    print(f"[analista] football: {football_stats['total']} registos, O25 WR={football_stats['per_market'].get('o25',{}).get('win_rate',0):.1%}")
    print(f"[analista] hoje: {today_stats['total_games']} jogos, {today_stats['strong_picks']} picks fortes")

    if mode == "report":
        try:
            ai_report = generate_ai_report(over25_stats, football_stats)
        except Exception as e:
            print(f"[ERROR] Falha na análise científica: {e}")
            ai_report = ""
        try:
            send_daily_report(over25_stats, football_stats, ai_report, today_stats)
        except Exception as e:
            print(f"[ERROR] Falha no envio do email: {e}")


if __name__ == "__main__":
    main()
