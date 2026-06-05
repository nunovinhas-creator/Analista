# backtesting/strategies.py — Estratégias de aposta para o backtesting engine
# Cada estratégia é um callable que recebe contexto e devolve stake em unidades.
import math


# ── Base abstracta ─────────────────────────────────────────────────────────────

class Strategy:
    """Classe base para estratégias de aposta.

    __call__(predicted_prob, odds, bankroll, history) -> float
        predicted_prob: probabilidade prevista para o evento (0-1)
        odds:           odds decimais da aposta
        bankroll:       banca actual em unidades
        history:        lista de BetEvent anteriores (pode ser vazia)
        retorna:        stake em unidades (>= 0)
    """
    name = "base"

    def __call__(self, predicted_prob, odds, bankroll, history):
        raise NotImplementedError


# ── Flat Stake ─────────────────────────────────────────────────────────────────

class FlatStakeStrategy(Strategy):
    """Aposta sempre a mesma quantidade fixa, independentemente do edge."""

    name = "flat"

    def __init__(self, stake_units=1.0):
        self.stake_units = stake_units

    def __call__(self, predicted_prob, odds, bankroll, history):
        # Stake fixo em unidades — não depende da banca nem da probabilidade
        return self.stake_units


# ── Kelly ──────────────────────────────────────────────────────────────────────

class KellyStrategy(Strategy):
    """Fracção do Kelly criterion.

    Formula Kelly: f = (p*b - q) / b
        p = probabilidade estimada de ganhar
        q = 1 - p
        b = odds - 1 (retorno líquido por unidade apostada)
    Fracção aplicada: fraction * f * bankroll, com tecto em cap_pct % da banca.
    """

    name = "kelly"

    def __init__(self, fraction=1.0, cap_pct=3.0):
        self.fraction = fraction
        self.cap_pct  = cap_pct

    def __call__(self, predicted_prob, odds, bankroll, history):
        if odds <= 1.01 or predicted_prob <= 0.0 or predicted_prob >= 1.0:
            return 0.0
        b = odds - 1.0
        p = predicted_prob
        q = 1.0 - p
        f = (p * b - q) / b
        if f <= 0.0:
            return 0.0
        stake = self.fraction * f * bankroll
        cap   = self.cap_pct * bankroll / 100.0
        return max(0.0, min(stake, cap))


class ProportionalKellyStrategy(Strategy):
    """Kelly com probabilidade ajustada pelo IC de Wilson quando há histórico suficiente.

    Se history >= 10 picks, ajusta p para o limite inferior do IC de Wilson 95%
    como estimativa conservadora da probabilidade real.
    Isso dá um Kelly "shrunk" proporcional ao tamanho da amostra.
    """

    name = "proportional_kelly"

    def __init__(self, fraction=0.25, cap_pct=3.0):
        self.fraction = fraction
        self.cap_pct  = cap_pct

    def _wilson_lower(self, wins, n, z=1.96):
        """Limite inferior do IC Wilson 95%."""
        if n == 0:
            return 0.0
        p      = wins / n
        denom  = 1 + z ** 2 / n
        centre = (p + z ** 2 / (2 * n)) / denom
        margin = (z * (p * (1 - p) / n + z ** 2 / (4 * n ** 2)) ** 0.5) / denom
        return max(0.0, centre - margin)

    def __call__(self, predicted_prob, odds, bankroll, history):
        if odds <= 1.01 or predicted_prob <= 0.0 or predicted_prob >= 1.0 or bankroll <= 0.0:
            return 0.0

        # Ajustar probabilidade com Wilson se tiver histórico suficiente
        resolved = [e for e in (history or []) if e.hit is not None]
        n = len(resolved)
        if n >= 10:
            wins = sum(1 for e in resolved if e.hit)
            p    = self._wilson_lower(wins, n)
        else:
            p = predicted_prob

        b = odds - 1.0
        q = 1.0 - p
        f = (p * b - q) / b
        if f <= 0.0:
            return 0.0

        stake = self.fraction * f * bankroll
        cap   = self.cap_pct * bankroll / 100.0
        return max(0.0, min(stake, cap))


# ── Martingale ─────────────────────────────────────────────────────────────────

class MartingaleStrategy(Strategy):
    """Dobra a stake após cada derrota; reseta na vitória.

    AVISO: estratégia de comparação apenas — risco de ruína elevado.
    Tecto em max_factor * stake_base para limitar o drawdown máximo possível.
    """

    name = "martingale"

    def __init__(self, stake_base=1.0, max_factor=5):
        self.stake_base  = stake_base
        self.max_factor  = max_factor
        self._multiplier = 1

    def __call__(self, predicted_prob, odds, bankroll, history):
        # Determinar estado a partir do último evento no histórico
        if history:
            last = history[-1]
            if last.hit is False:
                self._multiplier = min(self._multiplier * 2, self.max_factor)
            else:
                self._multiplier = 1
        else:
            self._multiplier = 1

        stake = self.stake_base * self._multiplier
        # Nunca apostar mais do que a banca disponível
        return min(stake, bankroll)


# ── Value ──────────────────────────────────────────────────────────────────────

class ValueStrategy(Strategy):
    """Aposta apenas quando o Expected Value é superior ao threshold mínimo.

    EV = predicted_prob * odds - 1
    Só aposta se EV > min_ev. Usa stake fixo quando existe valor positivo.
    """

    name = "value"

    def __init__(self, stake_units=1.0, min_ev=0.05):
        self.stake_units = stake_units
        self.min_ev      = min_ev

    def __call__(self, predicted_prob, odds, bankroll, history):
        if odds <= 1.01 or predicted_prob <= 0.0:
            return 0.0
        ev = predicted_prob * odds - 1.0
        if ev < self.min_ev:
            return 0.0
        return self.stake_units


# ── Confidence Weighted ────────────────────────────────────────────────────────

class ConfidenceWeightedStrategy(Strategy):
    """Multiplica o stake fixo pelo peso associado ao nível de confiança do pick.

    Requer metadata["conf"] no evento com valor "ALTA", "MÉDIA" ou "BAIXA".
    Pesos padrão: ALTA=1.5, MÉDIA=1.0, BAIXA=0.5.
    """

    name = "confidence"

    def __init__(self, stake_units=1.0, conf_weights=None):
        self.stake_units  = stake_units
        self.conf_weights = conf_weights or {"ALTA": 1.5, "MÉDIA": 1.0, "BAIXA": 0.5}

    def __call__(self, predicted_prob, odds, bankroll, history):
        # O conf vem em metadata do evento — não disponível aqui directamente.
        # O engine passa metadata via predicted_prob ao invocar; para acesso ao conf
        # o engine chama a estratégia com metadata["conf"] injectado via _call_with_meta.
        # Devolve stake_units * peso_padrão (MÉDIA) como fallback.
        return self.stake_units * self.conf_weights.get("MÉDIA", 1.0)

    def call_with_meta(self, predicted_prob, odds, bankroll, history, metadata):
        """Variante que recebe metadata explícito — invocada pelo engine."""
        conf   = (metadata or {}).get("conf", "MÉDIA")
        weight = self.conf_weights.get(conf, 1.0)
        return self.stake_units * weight


# ── Factory ────────────────────────────────────────────────────────────────────

_STRATEGY_MAP = {
    "flat":             lambda **kw: FlatStakeStrategy(stake_units=kw.get("stake_units", 1.0)),
    "kelly":            lambda **kw: KellyStrategy(fraction=1.0,  cap_pct=kw.get("cap_pct", 3.0)),
    "full_kelly":       lambda **kw: KellyStrategy(fraction=1.0,  cap_pct=kw.get("cap_pct", 3.0)),
    "half_kelly":       lambda **kw: KellyStrategy(fraction=0.5,  cap_pct=kw.get("cap_pct", 3.0)),
    "quarter_kelly":    lambda **kw: KellyStrategy(fraction=0.25, cap_pct=kw.get("cap_pct", 3.0)),
    "prop_kelly":       lambda **kw: ProportionalKellyStrategy(fraction=kw.get("fraction", 0.25), cap_pct=kw.get("cap_pct", 3.0)),
    "proportional_kelly": lambda **kw: ProportionalKellyStrategy(fraction=kw.get("fraction", 0.25), cap_pct=kw.get("cap_pct", 3.0)),
    "martingale":       lambda **kw: MartingaleStrategy(stake_base=kw.get("stake_base", 1.0), max_factor=kw.get("max_factor", 5)),
    "value":            lambda **kw: ValueStrategy(stake_units=kw.get("stake_units", 1.0), min_ev=kw.get("min_ev", 0.05)),
    "confidence":       lambda **kw: ConfidenceWeightedStrategy(stake_units=kw.get("stake_units", 1.0), conf_weights=kw.get("conf_weights")),
}


def get_strategy(name, **kwargs):
    """Factory: devolve instância de Strategy pelo nome.

    Nomes suportados: flat, kelly, full_kelly, half_kelly, quarter_kelly,
    prop_kelly, proportional_kelly, martingale, value, confidence.
    """
    key = (name or "flat").lower().strip()
    factory = _STRATEGY_MAP.get(key)
    if factory is None:
        raise ValueError(f"Estratégia desconhecida: '{name}'. Disponíveis: {list_strategies()}")
    return factory(**kwargs)


def list_strategies():
    """Devolve lista de todos os nomes de estratégias disponíveis."""
    return sorted(_STRATEGY_MAP.keys())
