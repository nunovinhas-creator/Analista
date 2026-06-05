"""
Sistema de rating Elo para futebol.
"""

import math


class EloSystem:
    """
    Sistema de rating Elo adaptado para futebol.
    Inclui vantagem de jogar em casa e zona de empate.
    """

    def __init__(self, k=32, home_advantage=100, initial_rating=1500):
        """
        Params:
            k: factor K — sensibilidade de actualização do rating
            home_advantage: pontos de vantagem para a equipa da casa
            initial_rating: rating inicial para equipas novas
        """
        self.k = k
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self._ratings = {}
        self.rating_history = {}  # team -> list of (date, rating)

    def get_rating(self, team):
        """Retorna o rating actual da equipa (cria com rating inicial se não existir)."""
        if team not in self._ratings:
            self._ratings[team] = float(self.initial_rating)
        return self._ratings[team]

    def expected_score(self, home, away):
        """
        Probabilidade esperada de vitória da equipa da casa.
        Inclui vantagem de jogar em casa.

        Returns:
            float: probabilidade de vitória da casa (sem empate)
        """
        rating_home = self.get_rating(home) + self.home_advantage
        rating_away = self.get_rating(away)
        diff = rating_home - rating_away
        return 1.0 / (1.0 + math.pow(10, -diff / 400.0))

    def update(self, home, away, home_goals, away_goals):
        """
        Actualiza os ratings após um jogo.

        Params:
            home: nome da equipa da casa
            away: nome da equipa de fora
            home_goals: golos marcados pela casa
            away_goals: golos marcados por fora

        Returns:
            (new_home_rating, new_away_rating)
        """
        r_home = self.get_rating(home)
        r_away = self.get_rating(away)

        # Score real: 1 = vitória, 0.5 = empate, 0 = derrota
        if home_goals > away_goals:
            actual_home = 1.0
            actual_away = 0.0
        elif home_goals == away_goals:
            actual_home = 0.5
            actual_away = 0.5
        else:
            actual_home = 0.0
            actual_away = 1.0

        expected_home = self.expected_score(home, away)
        expected_away = 1.0 - expected_home

        new_home = r_home + self.k * (actual_home - expected_home)
        new_away = r_away + self.k * (actual_away - expected_away)

        self._ratings[home] = new_home
        self._ratings[away] = new_away

        return (new_home, new_away)

    def get_all_ratings(self):
        """
        Retorna todos os ratings ordenados de forma decrescente.

        Returns:
            dict: {team: rating} ordenado por rating desc
        """
        return dict(sorted(self._ratings.items(), key=lambda x: x[1], reverse=True))

    def win_probability(self, home, away):
        """
        Probabilidade de vitória, empate e derrota usando transformação logística
        com zona de empate.

        Usa o modelo de Elo com uma "zona de empate" baseada no rating diferencial.
        A probabilidade de empate é modelada como a massa na região onde a diferença
        esperada é pequena.

        Returns:
            dict com prob_home, prob_draw, prob_away
        """
        r_home = self.get_rating(home) + self.home_advantage
        r_away = self.get_rating(away)
        diff = r_home - r_away

        # Transformação logística standard
        # Baseado no modelo de Elo com 3 resultados de Hvattum & Arntzen
        # P(home) = 1/(1+10^(-diff/400))
        p_home_win = 1.0 / (1.0 + math.pow(10, -diff / 400.0))

        # Zona de empate: quando os ratings são próximos, a probabilidade de empate é maior
        # Usamos uma função baseada no valor absoluto da diferença de ratings
        # draw_factor reduz-se à medida que a diferença aumenta
        abs_diff_norm = abs(diff) / 400.0
        draw_base = 0.25  # base de empate no futebol (~25%)
        draw_factor = draw_base * math.exp(-0.5 * abs_diff_norm)
        draw_factor = max(0.05, min(draw_factor, 0.35))

        # Ajustar home e away para acomodar o empate
        # Distribuir o "espaço" de empate proporcionalmente
        remaining = 1.0 - draw_factor
        prob_home = p_home_win * remaining
        prob_away = (1.0 - p_home_win) * remaining
        prob_draw = draw_factor

        # Garantir que soma a 1
        total = prob_home + prob_draw + prob_away
        if total > 0:
            prob_home /= total
            prob_draw /= total
            prob_away /= total

        return {
            "prob_home": float(max(0.0, min(1.0, prob_home))),
            "prob_draw": float(max(0.0, min(1.0, prob_draw))),
            "prob_away": float(max(0.0, min(1.0, prob_away))),
        }

    def _record_history(self, team, date, rating):
        """Regista o histórico de rating de uma equipa."""
        if team not in self.rating_history:
            self.rating_history[team] = []
        self.rating_history[team].append((date, rating))

    def fit_from_history(self, records):
        """
        Processa o histórico de jogos em ordem cronológica para construir os ratings.
        Infere o resultado a partir dos campos hit_1x2 + hw/aw ou hw/aw directamente.

        Params:
            records: lista de dicts do history.json com campos:
                     date, home, away, hit_1x2, hw, dr, aw

        Returns:
            self (para chaining)
        """
        # Ordenar por data
        def parse_date(r):
            try:
                return r.get("date", "1900-01-01") or "1900-01-01"
            except Exception:
                return "1900-01-01"

        sorted_records = sorted(records, key=parse_date)

        for rec in sorted_records:
            home = rec.get("home", "")
            away = rec.get("away", "")
            date = rec.get("date", "")

            if not home or not away:
                continue

            # Inferir resultado
            # Estratégia 1: usar hit_1x2 com as probabilidades hw/aw
            # Se pick_1x2 está activo e hit_1x2 é True/False, podemos inferir
            # Estratégia 2: usar hw/aw como probabilidades e inferir resultado esperado
            result = self._infer_result(rec)

            if result is None:
                continue

            home_goals, away_goals = result

            # Actualizar ratings
            new_home, new_away = self.update(home, away, home_goals, away_goals)

            # Registar histórico
            self._record_history(home, date, new_home)
            self._record_history(away, date, new_away)

        return self

    def _infer_result(self, rec):
        """
        Infere o resultado do jogo a partir dos campos disponíveis.
        Retorna (home_goals, away_goals) de forma proxy ou None se não possível.
        """
        # Tentar inferir do hit_1x2 e das probabilidades hw/aw
        pick_1x2 = rec.get("pick_1x2", False)
        hit_1x2 = rec.get("hit_1x2", None)
        hw = rec.get("hw", 0) or 0  # prob home win 0-100
        dr = rec.get("dr", 0) or 0  # prob draw 0-100
        aw = rec.get("aw", 0) or 0  # prob away win 0-100

        # Caso 1: temos resultado directo através de pick + hit
        if pick_1x2 is True and hit_1x2 is not None:
            # Determinar qual era o pick (equipa favorita)
            if hw >= dr and hw >= aw:
                # Pick era casa
                if hit_1x2:
                    return (1, 0)  # casa ganhou
                else:
                    # Derrota ou empate — usar aw vs dr para desempatar
                    if aw > dr:
                        return (0, 1)
                    else:
                        return (0, 0)
            elif aw >= dr and aw >= hw:
                # Pick era fora
                if hit_1x2:
                    return (0, 1)  # fora ganhou
                else:
                    if hw > dr:
                        return (1, 0)
                    else:
                        return (0, 0)
            else:
                # Pick era empate
                if hit_1x2:
                    return (0, 0)
                else:
                    if hw > aw:
                        return (1, 0)
                    else:
                        return (0, 1)

        # Caso 2: sem pick, usar probabilidades para inferir resultado mais provável
        total = hw + dr + aw
        if total > 0:
            hw_n = hw / total
            dr_n = dr / total
            aw_n = aw / total

            # Usar resultado mais provável como proxy
            if hw_n >= dr_n and hw_n >= aw_n:
                return (1, 0)
            elif aw_n >= dr_n and aw_n >= hw_n:
                return (0, 1)
            else:
                return (0, 0)

        # Sem dados suficientes
        return None


def top_n(elo_system, n=20):
    """
    Retorna as top N equipas por rating Elo.

    Params:
        elo_system: instância de EloSystem
        n: número de equipas a retornar

    Returns:
        lista de (team, rating) ordenada de forma decrescente
    """
    all_ratings = elo_system.get_all_ratings()
    result = list(all_ratings.items())
    return result[:n]
