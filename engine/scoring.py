"""Blend factor scores into an ability rating and a probability distribution.

Pipeline:
  factors (0-100 each)  --weighted-->  ability (0-100)
  abilities            --softmax-->     win probabilities (sum to 1)
  win prob             --Harville-->     place (top-3) probabilities
  win prob x odds                        expected value / betting edge
"""
from __future__ import annotations

import math
from typing import Optional

from .models import Horse, Race, Entry, HorsePrediction
from .features import compute_factors, WEIGHTS


# marks handed to the top of the field (競馬新聞の印)
MARKS = ["◎", "◯", "▲", "△", "☆"]


def _ability(factors: dict) -> float:
    total_w = sum(WEIGHTS.get(k, 0) for k in factors)
    if total_w == 0:
        return 50.0
    return sum(f.score * WEIGHTS.get(k, 0) for k, f in factors.items()) / total_w


def _softmax(abilities: list[float], temp: float = 9.5) -> list[float]:
    """Lower temp -> sharper favourite; 9.5 tuned so top pick lands in a
    realistic 20-40% band rather than over-backing a single horse."""
    m = max(abilities)
    exps = [math.exp((a - m) / temp) for a in abilities]
    s = sum(exps)
    return [e / s for e in exps]


def _place_probs(win_probs: list[float]) -> list[float]:
    """Harville model: P(top3) approximated from win probabilities.

    P(finish 2nd | not 1st) etc. — computed pairwise and clamped to <=0.999.
    """
    n = len(win_probs)
    out = []
    for i in range(n):
        p1 = win_probs[i]
        # probability i is 2nd: sum over j!=i P(j win)*P(i win | j gone)
        p2 = sum(win_probs[j] * (p1 / (1 - win_probs[j])) for j in range(n) if j != i and win_probs[j] < 1)
        # probability i is 3rd (approx)
        p3 = 0.0
        for j in range(n):
            if j == i or win_probs[j] >= 1:
                continue
            for k in range(n):
                if k in (i, j) or win_probs[k] >= 1 or (1 - win_probs[j] - win_probs[k]) <= 0:
                    continue
                p3 += win_probs[j] * (win_probs[k] / (1 - win_probs[j])) * (p1 / (1 - win_probs[j] - win_probs[k]))
        out.append(min(0.999, p1 + p2 + p3))
    return out


def predict_race(race: Race, horses: dict[str, Horse]) -> list[HorsePrediction]:
    preds: list[HorsePrediction] = []
    entries = [e for e in race.entries if e.horse_id]

    factor_sets = {}
    abilities = []
    for e in entries:
        horse = horses.get(e.horse_id, Horse(horse_id=e.horse_id, name=e.horse_name))
        factors = compute_factors(horse, race, e)
        factor_sets[e.horse_id] = factors
        abilities.append(_ability(factors))

    win_probs = _softmax(abilities)
    place_probs = _place_probs(win_probs)

    for e, ability, wp, pp in zip(entries, abilities, win_probs, place_probs):
        factors = factor_sets[e.horse_id]
        # prefer live odds; fall back to final odds captured on the result page
        odds = e.odds if e.odds else race.result_odds.get(e.horse_id)
        pred = HorsePrediction(
            horse_id=e.horse_id,
            horse_no=e.horse_no,
            horse_name=e.horse_name,
            jockey=e.jockey,
            factors={k: round(f.score, 1) for k, f in factors.items()},
            ability=round(ability, 1),
            win_prob=round(wp, 4),
            place_prob=round(pp, 4),
            odds=odds,
            fair_odds=round(1 / wp, 1) if wp > 0 else None,
            value=round(wp * odds - 1, 3) if odds else None,
        )
        pred._factors_full = factors  # attach for commentary (non-serialised)
        preds.append(pred)

    preds.sort(key=lambda p: p.win_prob, reverse=True)
    for rank, p in enumerate(preds, 1):
        p.rank = rank
        p.confidence = MARKS[rank - 1] if rank <= len(MARKS) else ""
    return preds


def field_confidence(preds: list[HorsePrediction]) -> str:
    """Characterise the race: is the favourite dominant or is it wide open?"""
    if not preds:
        return "不明"
    top = preds[0].win_prob
    if top >= 0.42:
        return "本命サイド（信頼度高）"
    if top >= 0.28:
        return "中穴含み（軸は堅い）"
    return "波乱含み（混戦・妙味あり）"
