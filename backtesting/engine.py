# backtesting/engine.py — Motor de backtesting determinístico orientado a eventos
# Processa histórico de picks e simula apostas com diferentes estratégias.
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

from backtesting.strategies import get_strategy, Strategy

# Odds base por mercado (alinhado com utils.MARKET_BASE_ODDS)
_MARKET_ODDS = {"o25": 1.90, "btts": 1.85, "1x2": 2.20}


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class BetEvent:
    """Representa uma aposta individual simulada."""
    date:           str
    home:           str
    away:           str
    league:         str
    market:         str
    odds:           float
    predicted_prob: float
    stake:          float
    hit:            object  # bool ou None
    profit:         object  # float ou None
    metadata:       dict = field(default_factory=dict)


@dataclass
class BankrollState:
    """Estado instantâneo da banca durante o backtesting."""
    balance:         float
    initial_balance: float
    peak:            float
    max_drawdown:    float
    n_bets:          int
    n_wins:          int
    n_losses:        int


@dataclass
class BacktestResult:
    """Resultado completo de um backtest com todas as métricas calculadas."""
    events:           list
    bankroll_history: list
    final_balance:    float
    roi:              float
    roi_pct:          float
    win_rate:         float
    max_drawdown:     float
    sharpe:           float
    n_bets:           int
    by_market:        dict
    by_league:        dict
    by_month:         dict
    by_confidence:    dict


# ── Motor principal ────────────────────────────────────────────────────────────

class BacktestEngine:
    """Motor de backtesting determinístico.

    Itera os registos por ordem cronológica, aplica a estratégia para calcular
    o stake, simula a aposta e rastreia o estado da banca ao longo do tempo.
    """

    def __init__(self, initial_bankroll=100.0, strategy=None):
        self.initial_bankroll = initial_bankroll
        # Aceita Strategy ou nome de string; fallback: flat stake 1u
        if strategy is None:
            self.strategy = get_strategy("flat")
        elif isinstance(strategy, str):
            self.strategy = get_strategy(strategy)
        else:
            self.strategy = strategy

    # ── Entrada via history.json ───────────────────────────────────────────────

    def run_on_history(self, history_records, market="o25",
                       pick_key="pick_o25", hit_key="hit_o25",
                       odds=None):
        """Corre o backtest sobre registos do history.json do football-dashboard.

        Filtra os registos com pick=True e resultado não-nulo, ordena por data
        e simula as apostas em sequência.

        Args:
            history_records: lista de dicts conforme schema do history.json
            market:          nome do mercado ("o25", "btts", "1x2")
            pick_key:        campo booleano de pick no registo (ex: "pick_o25")
            hit_key:         campo booleano de resultado (ex: "hit_o25")
            odds:            odds fixas; se None usa _MARKET_ODDS[market]

        Returns:
            BacktestResult
        """
        base_odds = odds if odds is not None else _MARKET_ODDS.get(market, 1.90)

        # Mapeamento mercado → campo de probabilidade prevista (escala 0-100)
        _prob_key_map = {
            "o25":  "po",
            "btts": "pb",
            "1x2":  "hw",  # probabilidade da casa como proxy 1X2
        }
        prob_key = _prob_key_map.get(market, "po")

        # Filtrar e ordenar registos válidos
        valid = []
        for r in history_records:
            if not r.get(pick_key):
                continue
            if r.get(hit_key) is None:
                continue
            valid.append(r)

        valid.sort(key=lambda r: r.get("date", ""))

        bankroll = self.initial_bankroll
        bankroll_history = [bankroll]
        events = []
        history_so_far = []

        for r in valid:
            # Converter probabilidade 0-100 → 0-1
            raw_prob = r.get(prob_key, 0)
            try:
                predicted_prob = float(raw_prob) / 100.0
            except (TypeError, ValueError):
                predicted_prob = 0.5

            # Clamp para evitar valores impossíveis
            predicted_prob = max(0.01, min(0.99, predicted_prob))

            metadata = {
                "conf":   r.get("conf", "MÉDIA"),
                "league": r.get("league", ""),
                "date":   r.get("date", ""),
            }

            # Calcular stake via estratégia (suporte para ConfidenceWeightedStrategy)
            strat = self.strategy
            if hasattr(strat, "call_with_meta"):
                stake = strat.call_with_meta(predicted_prob, base_odds, bankroll,
                                             history_so_far, metadata)
            else:
                stake = strat(predicted_prob, base_odds, bankroll, history_so_far)

            # Nunca apostar mais do que a banca disponível
            stake = max(0.0, min(float(stake), bankroll))

            hit = bool(r.get(hit_key))
            event = self._process_bet(BetEvent(
                date=str(r.get("date", "")),
                home=str(r.get("home", "")),
                away=str(r.get("away", "")),
                league=str(r.get("league", "")),
                market=market,
                odds=base_odds,
                predicted_prob=predicted_prob,
                stake=stake,
                hit=hit,
                profit=None,
                metadata=metadata,
            ), stake)

            bankroll += event.profit
            bankroll = max(0.0, bankroll)
            bankroll_history.append(bankroll)
            events.append(event)
            history_so_far.append(event)

        return self._compute_result(events, bankroll_history)

    # ── Entrada via picks.json (over25-scanner) ────────────────────────────────

    def run_on_picks(self, picks, market="o25"):
        """Corre o backtest sobre picks do over25-scanner.

        Usa o campo odds_over de cada pick como odds reais da aposta.
        Filtra apenas picks com resultado não-nulo ("WIN" ou "LOSS").

        Args:
            picks:  lista de dicts conforme schema do picks.json
            market: nome do mercado (usado para label; assume "o25")

        Returns:
            BacktestResult
        """
        def _safe_float(v, default=0.0):
            if v is None or v == "":
                return default
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        # Filtrar e ordenar por data
        valid = [p for p in picks if p.get("result_over25") in ("WIN", "LOSS")]
        valid.sort(key=lambda p: str(p.get("data", "")))

        bankroll = self.initial_bankroll
        bankroll_history = [bankroll]
        events = []
        history_so_far = []

        for p in valid:
            odds = _safe_float(p.get("odds_over"))
            if odds < 1.01:
                odds = _MARKET_ODDS["o25"]

            # xg_total como proxy de probabilidade prevista (cap a 5 golos esperados)
            xg = _safe_float(p.get("xg_total"), 0.0)
            # Probabilidade Over 2.5 via Poisson aproximado: 1 - P(X<=2) com λ=xg
            if xg > 0.1:
                lam = xg
                p_under = math.exp(-lam) * (1 + lam + lam**2 / 2)
                predicted_prob = max(0.01, min(0.99, 1.0 - p_under))
            else:
                # Fallback: score_sistema normalizado para 0-1
                score = _safe_float(p.get("score_sistema"), 60.0)
                predicted_prob = max(0.01, min(0.99, score / 100.0))

            metadata = {
                "conf":       "ALTA" if _safe_float(p.get("score_sistema"), 0) >= 70 else "MÉDIA",
                "league":     str(p.get("liga", "")),
                "date":       str(p.get("data", "")),
                "movimento":  str(p.get("movimento", "")),
                "score_sistema": _safe_float(p.get("score_sistema"), 0),
            }

            strat = self.strategy
            if hasattr(strat, "call_with_meta"):
                stake = strat.call_with_meta(predicted_prob, odds, bankroll,
                                             history_so_far, metadata)
            else:
                stake = strat(predicted_prob, odds, bankroll, history_so_far)

            stake = max(0.0, min(float(stake), bankroll))

            hit = (p.get("result_over25") == "WIN")
            event = self._process_bet(BetEvent(
                date=str(p.get("data", "")),
                home=str(p.get("casa", "")),
                away=str(p.get("fora", "")),
                league=str(p.get("liga", "")),
                market=market,
                odds=odds,
                predicted_prob=predicted_prob,
                stake=stake,
                hit=hit,
                profit=None,
                metadata=metadata,
            ), stake)

            bankroll += event.profit
            bankroll = max(0.0, bankroll)
            bankroll_history.append(bankroll)
            events.append(event)
            history_so_far.append(event)

        return self._compute_result(events, bankroll_history)

    # ── Processamento de aposta individual ────────────────────────────────────

    def _process_bet(self, event, stake):
        """Calcula profit e devolve BetEvent preenchido.

        WIN: profit = stake * (odds - 1)
        LOSS: profit = -stake
        hit=None: profit = 0 (aposta void)
        """
        if event.hit is None:
            profit = 0.0
        elif event.hit:
            profit = stake * (event.odds - 1.0)
        else:
            profit = -stake

        return BetEvent(
            date=event.date,
            home=event.home,
            away=event.away,
            league=event.league,
            market=event.market,
            odds=event.odds,
            predicted_prob=event.predicted_prob,
            stake=stake,
            hit=event.hit,
            profit=round(profit, 4),
            metadata=event.metadata,
        )

    # ── Cálculo de métricas de resultado ──────────────────────────────────────

    def _compute_result(self, events, bankroll_history):
        """Calcula todas as métricas de sumário a partir dos eventos e histórico de banca."""
        resolved = [e for e in events if e.hit is not None]
        n_bets   = len(resolved)
        n_wins   = sum(1 for e in resolved if e.hit)
        n_losses = n_bets - n_wins

        total_staked = sum(e.stake for e in resolved)
        total_profit = sum(e.profit for e in resolved if e.profit is not None)

        final_balance = bankroll_history[-1] if bankroll_history else self.initial_bankroll
        roi       = total_profit
        roi_pct   = (total_profit / total_staked * 100.0) if total_staked > 0 else 0.0
        win_rate  = (n_wins / n_bets) if n_bets > 0 else 0.0

        max_dd    = self._max_drawdown(bankroll_history)
        sharpe    = self._sharpe(bankroll_history)

        # Segmentação por mercado
        by_market = defaultdict(lambda: {"n": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
        for e in resolved:
            seg = by_market[e.market]
            seg["n"]      += 1
            seg["wins"]   += 1 if e.hit else 0
            seg["profit"] += e.profit
            seg["staked"] += e.stake
        by_market = {k: _enrich_segment(v) for k, v in by_market.items()}

        # Segmentação por liga (top 10 por volume)
        by_league_raw = defaultdict(lambda: {"n": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
        for e in resolved:
            seg = by_league_raw[e.league or "Desconhecida"]
            seg["n"]      += 1
            seg["wins"]   += 1 if e.hit else 0
            seg["profit"] += e.profit
            seg["staked"] += e.stake
        # Ordenar por volume e manter top 10
        sorted_leagues = sorted(by_league_raw.items(), key=lambda x: x[1]["n"], reverse=True)
        by_league = {k: _enrich_segment(v) for k, v in sorted_leagues[:10]}

        # Segmentação mensal
        by_month_raw = defaultdict(lambda: {"n": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
        for e in resolved:
            month = e.date[:7] if len(e.date) >= 7 else "????-??"  # "YYYY-MM"
            seg = by_month_raw[month]
            seg["n"]      += 1
            seg["wins"]   += 1 if e.hit else 0
            seg["profit"] += e.profit
            seg["staked"] += e.stake
        by_month = {k: _enrich_segment(v) for k, v in sorted(by_month_raw.items())}

        # Segmentação por confiança (usa metadata["conf"])
        by_conf_raw = defaultdict(lambda: {"n": 0, "wins": 0, "profit": 0.0, "staked": 0.0})
        for e in resolved:
            conf = (e.metadata or {}).get("conf", "MÉDIA")
            seg = by_conf_raw[conf]
            seg["n"]      += 1
            seg["wins"]   += 1 if e.hit else 0
            seg["profit"] += e.profit
            seg["staked"] += e.stake
        by_confidence = {k: _enrich_segment(v) for k, v in by_conf_raw.items()}

        return BacktestResult(
            events=events,
            bankroll_history=bankroll_history,
            final_balance=round(final_balance, 4),
            roi=round(roi, 4),
            roi_pct=round(roi_pct, 2),
            win_rate=round(win_rate, 4),
            max_drawdown=round(max_dd, 4),
            sharpe=round(sharpe, 4),
            n_bets=n_bets,
            by_market=by_market,
            by_league=by_league,
            by_month=by_month,
            by_confidence=by_confidence,
        )

    # ── Métricas auxiliares ────────────────────────────────────────────────────

    @staticmethod
    def _max_drawdown(bankroll_history):
        """Drawdown máximo: queda máxima relativa em unidades desde um pico."""
        if len(bankroll_history) < 2:
            return 0.0
        peak = bankroll_history[0]
        max_dd = 0.0
        for val in bankroll_history:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _sharpe(bankroll_history):
        """Sharpe ratio anualizado estimado a partir da série de banca.

        Usa retornos percentuais diários estimados (1 ponto por aposta como proxy).
        Se não houver variância suficiente, devolve 0.0.
        Assume ~250 apostas/ano como factor de anualização.
        """
        if len(bankroll_history) < 3:
            return 0.0

        # Calcular retornos consecutivos em percentagem
        returns = []
        for i in range(1, len(bankroll_history)):
            prev = bankroll_history[i - 1]
            curr = bankroll_history[i]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return 0.0

        n      = len(returns)
        mean_r = sum(returns) / n
        if n < 2:
            return 0.0

        variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
        std_r    = math.sqrt(variance) if variance > 0 else 0.0
        if std_r == 0.0:
            return 0.0

        # Anualizar assumindo ~250 apostas/ano como benchmark razoável
        annualized = mean_r * math.sqrt(250)
        std_annual = std_r * math.sqrt(250)
        return annualized / std_annual if std_annual > 0 else 0.0


# ── Funções auxiliares internas ────────────────────────────────────────────────

def _enrich_segment(seg):
    """Adiciona win_rate e roi_pct a um dict de segmento."""
    n       = seg["n"]
    wins    = seg["wins"]
    staked  = seg["staked"]
    profit  = seg["profit"]
    return {
        "n":        n,
        "wins":     wins,
        "losses":   n - wins,
        "win_rate": round(wins / n, 4) if n > 0 else 0.0,
        "profit":   round(profit, 4),
        "staked":   round(staked, 4),
        "roi_pct":  round(profit / staked * 100.0, 2) if staked > 0 else 0.0,
    }


# ── API de conveniência ────────────────────────────────────────────────────────

def run_backtest(history_records, strategy_name="flat", market="o25",
                 initial_bankroll=100.0, **strategy_kwargs):
    """Função de conveniência: cria engine, corre e devolve BacktestResult.

    Args:
        history_records: lista de registos do history.json
        strategy_name:   nome da estratégia ("flat", "kelly", "quarter_kelly", etc.)
        market:          mercado a testar ("o25", "btts", "1x2")
        initial_bankroll: banca inicial em unidades
        **strategy_kwargs: argumentos adicionais para a estratégia

    Returns:
        BacktestResult
    """
    # Mapeamento mercado → chaves de pick/hit
    _market_keys = {
        "o25":  ("pick_o25",  "hit_o25"),
        "btts": ("pick_btts", "hit_btts"),
        "1x2":  ("pick_1x2",  "hit_1x2"),
    }
    pick_key, hit_key = _market_keys.get(market, ("pick_o25", "hit_o25"))
    base_odds = _MARKET_ODDS.get(market, 1.90)

    strategy = get_strategy(strategy_name, **strategy_kwargs)
    engine   = BacktestEngine(initial_bankroll=initial_bankroll, strategy=strategy)
    return engine.run_on_history(
        history_records,
        market=market,
        pick_key=pick_key,
        hit_key=hit_key,
        odds=base_odds,
    )


def compare_strategies(history_records, market="o25", initial_bankroll=100.0):
    """Compara flat, half_kelly, quarter_kelly e full_kelly no mesmo histórico.

    Devolve dict mapeando strategy_name → BacktestResult.
    Permite comparação directa do impacto de cada estratégia de sizing.

    Args:
        history_records:  lista de registos do history.json
        market:           mercado a testar
        initial_bankroll: banca inicial em unidades (igual para todas as estratégias)

    Returns:
        dict[str, BacktestResult]
    """
    strategies_to_compare = ["flat", "half_kelly", "quarter_kelly", "full_kelly"]
    results = {}
    for name in strategies_to_compare:
        try:
            results[name] = run_backtest(
                history_records,
                strategy_name=name,
                market=market,
                initial_bankroll=initial_bankroll,
            )
        except Exception as exc:
            print(f"[WARN] compare_strategies: estratégia '{name}' falhou — {exc}")
    return results
