"""Offline unit tests for the prediction math (no network required).

Run:  python -m pytest engine/tests/ -q     (or: python engine/tests/test_engine.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.models import Race, Entry, Horse, PastRun
from engine.features import compute_factors, WEIGHTS
from engine.scoring import predict_race, _softmax, _place_probs
from engine.betting import recommend


def _horse(hid, strong=True):
    """Synthetic horse: `strong` ones win, weak ones trail."""
    h = Horse(horse_id=hid, name=hid)
    for i in range(6):
        h.history.append(PastRun(
            date=f"2025/{6-i:02d}/01", venue="東京", weather="晴",
            field_size=12, finish=(2 if strong else 10), jockey="武豊",
            surface="芝", distance=1600, going="良", last_3f=33.5 if strong else 35.8,
            passing="3-3" if strong else "10-10", popularity=2 if strong else 11,
        ))
    return h


def _race():
    r = Race(race_id="202505050811", name="テストS", venue="東京",
             surface="芝", distance=1600, going="良", weather="晴",
             grade="GIII", field_size=6, date="2025-06-01")
    for i in range(6):
        r.entries.append(Entry(horse_id=f"h{i}", horse_name=f"h{i}",
                               horse_no=i + 1, jockey="武豊", odds=2.0 + i * 3))
    return r


def test_weights_sum_reasonable():
    assert 0.95 <= sum(WEIGHTS.values()) <= 1.05


def test_softmax_normalises():
    p = _softmax([70, 60, 55, 50, 48, 45])
    assert abs(sum(p) - 1.0) < 1e-9
    assert p[0] > p[-1]  # higher ability -> higher prob


def test_place_probs_bounded():
    wp = _softmax([70, 60, 55, 50, 48, 45])
    pp = _place_probs(wp)
    assert all(0 <= x <= 1 for x in pp)
    assert all(pp[i] >= wp[i] - 1e-6 for i in range(len(wp)))  # place >= win


def test_factor_scores_in_range():
    h = _horse("h0", strong=True)
    r = _race()
    factors = compute_factors(h, r, r.entries[0])
    assert set(factors) == set(WEIGHTS)
    for f in factors.values():
        assert 0 <= f.score <= 100
        assert isinstance(f.note, str) and f.note


def test_strong_horse_ranks_first():
    r = _race()
    horses = {f"h{i}": _horse(f"h{i}", strong=(i == 0)) for i in range(6)}
    preds = predict_race(r, horses)
    # win_prob is rounded to 4dp for clean JSON, so allow small rounding drift
    assert abs(sum(p.win_prob for p in preds) - 1.0) < 1e-2
    assert preds[0].horse_id == "h0"          # the only strong horse leads
    assert preds[0].confidence == "◎"
    assert preds[0].win_prob > preds[1].win_prob


def test_betting_generates_recs():
    r = _race()
    horses = {f"h{i}": _horse(f"h{i}", strong=(i == 0)) for i in range(6)}
    preds = predict_race(r, horses)
    bets = recommend(r, preds)
    assert isinstance(bets, list)
    for b in bets:
        assert b.stake_units >= 0
        assert b.bet_type


def test_settlement_and_sim():
    from engine.settlement import settle_bet, simulate_weekend
    from engine.models import BetRecommendation
    payouts = {"単勝": [{"combo": [5], "yen": 800}],
               "ワイド": [{"combo": [5, 3], "yen": 600}],
               "三連複": [{"combo": [5, 3, 8], "yen": 4200}]}
    # hit
    b = BetRecommendation("単勝", "5", 1.0, 1.2, 0.3, "", pay_key="単勝", combos=[[5]])
    s = settle_bet(b, payouts, unit_yen=100)
    assert s["stake_yen"] == 100 and s["return_yen"] == 800 and s["hit"]
    # miss
    b2 = BetRecommendation("単勝", "7", 1.0, 1.0, 0.1, "", pay_key="単勝", combos=[[7]])
    assert settle_bet(b2, payouts, unit_yen=100)["return_yen"] == 0
    # formation: one of 2 combos hits -> per-combo staking
    bf = BetRecommendation("3連複F", "5,3-8,9", 2.0, 5.0, 0.2, "",
                           pay_key="三連複", combos=[[5, 3, 8], [5, 3, 9]])
    sf = settle_bet(bf, payouts, unit_yen=100)
    assert sf["stake_yen"] == 200 and sf["return_yen"] == round(4200 / 100 * 100) and sf["hit"]
    # weekend simulation over a serialised race
    race = {"race": {"venue": "東京", "race_no": 11, "name": "T",
                     "payouts": payouts},
            "bets": [{"bet_type": "単勝", "selection": "5", "stake_units": 1.0,
                      "pay_key": "単勝", "combos": [[5]]}]}
    out = simulate_weekend([race], unit_yen=100, bankroll0=10000)
    assert out["n_bets"] == 1 and out["profit"] == 700 and out["bankroll_end"] == 10700


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
