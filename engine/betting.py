"""Bet recommendation engine.

Given the field's win/place probabilities and market odds, decide *what to
actually bet*.  Two philosophies are combined:

1. **Value / +EV** — back horses whose model probability implies a higher
   payout than the market is offering (win_prob x odds > 1).  This is where
   long-term profit comes from.
2. **Hit-rate anchoring** — most users also want tickets that *cash*, so we
   pair the value angle with structured place / quinella / wide tickets
   anchored on the model's top pick.

Stakes use a fractional-Kelly sizing so confident +EV spots get more, in
units (1 unit = the user's base stake), never raw yen.
"""
from __future__ import annotations

from itertools import combinations
from typing import Optional

from .models import HorsePrediction, BetRecommendation, Race


def _kelly(prob: float, odds: float, fraction: float = 0.25, cap: float = 3.0) -> float:
    """Fractional Kelly stake in units. b = odds-1."""
    b = odds - 1
    if b <= 0:
        return 0.0
    edge = prob * odds - 1
    if edge <= 0:
        return 0.0
    k = edge / b
    return round(min(cap, max(0.0, k * fraction * 10)), 2)  # x10 -> readable units


def recommend(race: Race, preds: list[HorsePrediction]) -> list[BetRecommendation]:
    bets: list[BetRecommendation] = []
    if len(preds) < 2:
        return bets
    by_no = {p.horse_no: p for p in preds}
    anchor = preds[0]

    # --- 1. Value win bets (単勝): only +EV horses ---------------------------
    for p in preds[:6]:
        if p.odds and p.value is not None and p.value > 0.08:
            stake = _kelly(p.win_prob, p.odds)
            if stake >= 0.2:
                bets.append(BetRecommendation(
                    bet_type="単勝",
                    selection=f"{p.horse_no} {p.horse_name}",
                    stake_units=stake,
                    expected_value=round(p.win_prob * p.odds, 2),
                    hit_prob=round(p.win_prob, 3),
                    rationale=(f"想定勝率{p.win_prob*100:.0f}%に対しオッズ{p.odds}倍は過小評価。"
                               f"期待値{p.win_prob*p.odds:.2f}倍の妙味"),
                ))

    # --- 2. Place safety on the anchor (複勝) --------------------------------
    if anchor.odds and anchor.place_prob >= 0.5:
        bets.append(BetRecommendation(
            bet_type="複勝",
            selection=f"{anchor.horse_no} {anchor.horse_name}",
            stake_units=round(min(2.0, anchor.place_prob * 2.5), 2),
            expected_value=round(anchor.place_prob * max(1.1, (anchor.odds or 3) * 0.28), 2),
            hit_prob=round(anchor.place_prob, 3),
            rationale=f"複勝率{anchor.place_prob*100:.0f}%の堅軸。的中重視の安全枠",
        ))

    # --- 3. Wide (ワイド): anchor x next two, high hit rate ------------------
    partners = preds[1:4]
    for q in partners:
        joint = anchor.place_prob * q.place_prob * 0.62  # both top-3 approx
        if joint >= 0.12:
            bets.append(BetRecommendation(
                bet_type="ワイド",
                selection=f"{anchor.horse_no} - {q.horse_no}",
                stake_units=round(min(1.5, joint * 4), 2),
                expected_value=round(joint * 6.5, 2),  # typical wide payout scale
                hit_prob=round(joint, 3),
                rationale=f"軸{anchor.horse_name}から相手{q.horse_name}。両者馬券圏内の可能性が高い手堅い組合せ",
            ))

    # --- 4. Quinella (馬連): anchor x value partners -------------------------
    for q in partners[:2]:
        joint = anchor.win_prob * q.win_prob * 2.0
        if joint >= 0.06:
            bets.append(BetRecommendation(
                bet_type="馬連",
                selection=f"{anchor.horse_no} - {q.horse_no}",
                stake_units=round(min(1.5, joint * 8), 2),
                expected_value=round(joint * 14, 2),
                hit_prob=round(joint, 3),
                rationale=f"1・2着を{anchor.horse_name}と{q.horse_name}で。中心視の2頭で組む本線",
            ))

    # --- 5. Trifecta formation (3連複) for value when race is open ----------
    top = preds[:5]
    if len(top) >= 4 and preds[0].win_prob < 0.4:
        legs = [p.horse_no for p in top[:2]]
        others = [p.horse_no for p in top[2:5]]
        combo = len(list(combinations(others, 2))) + len(legs) * len(others)
        hit = sum(p.place_prob for p in top[:5]) / 8
        bets.append(BetRecommendation(
            bet_type="3連複フォーメーション",
            selection=f"軸 {legs[0]},{legs[1]} - 相手 {','.join(map(str, others))}",
            stake_units=round(min(3.0, combo * 0.15), 2),
            expected_value=round(hit * 22, 2),
            hit_prob=round(hit, 3),
            rationale="混戦想定。上位拮抗のため点数を絞った3連複フォーメーションで高配当を狙う",
        ))

    # rank bets: value first, then hit-rate
    bets.sort(key=lambda b: b.expected_value, reverse=True)
    return bets[:6]
