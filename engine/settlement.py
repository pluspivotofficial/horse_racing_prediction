"""Settlement & bankroll simulation.

Answers the question "what if I had actually bet the AI's recommendations?"
Using the **real dividends** (払戻) scraped from each race, we settle every
recommended ticket and roll a bankroll forward across the weekend — producing
an equity curve, ROI, hit-rate, and drawdown that are grounded in what the
tote actually paid.

Conventions
-----------
* 1 unit = ``unit_yen`` (default 100 yen).
* netkeiba dividends are per 100 yen, so a ticket returns
  ``yen_dividend / 100 * stake_yen`` when it hits.
* For 複勝 / ワイド (multiple winning combos), a combo "hits" iff it appears in
  the payout table — which already encodes the real top-2/top-3 rule, so
  settlement is rule-correct without special-casing field size.
"""
from __future__ import annotations

from typing import Optional


def _payout_lookup(payouts: dict, pay_key: str) -> dict:
    """{tuple(sorted combo): yen} for a bet category."""
    out = {}
    for row in payouts.get(pay_key, []):
        out[tuple(sorted(row["combo"]))] = row["yen"]
    return out


def settle_bet(bet, payouts: dict, unit_yen: int = 100) -> dict:
    """Settle one recommended ticket against the real dividends."""
    stake_yen = round(bet.stake_units * unit_yen)
    combos = bet.combos or []
    n = len(combos) or 1
    per_combo = stake_yen / n
    table = _payout_lookup(payouts, bet.pay_key)
    ret = 0.0
    hit = False
    for combo in combos:
        yen = table.get(tuple(sorted(combo)))
        if yen:
            ret += yen / 100.0 * per_combo
            hit = True
    return {
        "bet_type": bet.bet_type,
        "selection": bet.selection,
        "stake_yen": stake_yen,
        "return_yen": round(ret),
        "profit_yen": round(ret - stake_yen),
        "hit": hit,
    }


def simulate_weekend(races: list, unit_yen: int = 100, bankroll0: int = 100_000) -> dict:
    """Walk the weekend race-by-race, betting every recommendation.

    ``races`` are RacePrediction-like dicts (already serialised) OR objects
    exposing ``.race`` and ``.bets``.  Returns a summary + equity curve.
    """
    bankroll = bankroll0
    peak = bankroll0
    max_dd = 0.0
    staked = returned = 0.0
    n_bets = n_hits = 0
    curve = [{"label": "開始", "bankroll": round(bankroll0)}]
    per_type: dict[str, dict] = {}
    ledger = []
    best = None

    for rp in races:
        race = _get(rp, "race")
        bets = _get(rp, "bets") or []
        payouts = _get(race, "payouts") or {}
        if not payouts:
            continue  # race not yet run -> can't settle
        race_stake = race_return = 0.0
        race_bets = []
        for bet in bets:
            b = _as_bet(bet)
            s = settle_bet(b, payouts, unit_yen)
            staked += s["stake_yen"]; returned += s["return_yen"]
            race_stake += s["stake_yen"]; race_return += s["return_yen"]
            n_bets += 1; n_hits += 1 if s["hit"] else 0
            pt = per_type.setdefault(s["bet_type"], {"stake": 0, "return": 0, "bets": 0, "hits": 0})
            pt["stake"] += s["stake_yen"]; pt["return"] += s["return_yen"]
            pt["bets"] += 1; pt["hits"] += 1 if s["hit"] else 0
            if best is None or s["profit_yen"] > best["profit_yen"]:
                best = {**s, "race": f"{_get(race,'venue')}{_get(race,'race_no')}R"}
            race_bets.append(s)
        bankroll += race_return - race_stake
        peak = max(peak, bankroll)
        max_dd = max(max_dd, peak - bankroll)
        curve.append({
            "label": f"{_get(race,'venue')}{_get(race,'race_no')}R",
            "bankroll": round(bankroll),
        })
        ledger.append({
            "race": f"{_get(race,'venue')}{_get(race,'race_no')}R {_get(race,'name')}",
            "stake": round(race_stake), "return": round(race_return),
            "profit": round(race_return - race_stake), "bankroll": round(bankroll),
            "bets": race_bets,
        })

    roi = (returned / staked) if staked else 0.0
    for pt in per_type.values():
        pt["roi"] = round(pt["return"] / pt["stake"], 3) if pt["stake"] else 0.0
        pt["hit_rate"] = round(pt["hits"] / pt["bets"], 3) if pt["bets"] else 0.0
    return {
        "unit_yen": unit_yen,
        "bankroll_start": bankroll0,
        "bankroll_end": round(bankroll),
        "staked": round(staked),
        "returned": round(returned),
        "profit": round(returned - staked),
        "roi": round(roi, 3),
        "n_bets": n_bets,
        "n_hits": n_hits,
        "hit_rate": round(n_hits / n_bets, 3) if n_bets else 0.0,
        "max_drawdown": round(max_dd),
        "best_ticket": best,
        "by_type": per_type,
        "equity_curve": curve,
        "ledger": ledger,
    }


# -- helpers to accept both dicts and dataclasses -----------------------------
def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


class _BetView:
    """Adapts a serialised bet dict to the attribute shape settle_bet expects."""
    def __init__(self, d):
        self.bet_type = d.get("bet_type", "")
        self.selection = d.get("selection", "")
        self.stake_units = d.get("stake_units", 0)
        self.pay_key = d.get("pay_key", "")
        self.combos = d.get("combos", [])


def _as_bet(bet):
    return _BetView(bet) if isinstance(bet, dict) else bet
