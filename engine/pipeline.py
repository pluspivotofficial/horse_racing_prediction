"""Orchestration: race_id / weekend -> full RacePrediction objects.

Also owns *data-gap reporting*.  The user explicitly asked to be told when
something is missing ("なにか足らないものがあったら教えてね"), so every race
carries a ``data_warnings`` list describing exactly what we could not obtain
and how much it dents confidence.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from .models import Race, Horse, RacePrediction
from .netkeiba.client import NetkeibaClient
from .netkeiba import parser as P
from .scoring import predict_race, field_confidence
from .betting import recommend
from .commentary import horse_comments, race_comment, pace_scenario


def _merge_result_page(race: Race, dbrace: Race) -> None:
    """Overlay actual conditions/results from the DB page onto the entry race."""
    race.weather = race.weather or dbrace.weather
    race.going = race.going or dbrace.going
    race.date = race.date or dbrace.date
    race.direction = race.direction or dbrace.direction
    if not race.name and dbrace.name:
        race.name = dbrace.name
    if not race.grade and dbrace.grade:
        race.grade = dbrace.grade
    race.result = dbrace.result
    race.result_odds = dbrace.result_odds
    race.result_pop = dbrace.result_pop


def load_race(client: NetkeibaClient, race_id: str, want_result: bool = True) -> tuple[Race, dict[str, Horse], list[str]]:
    warnings: list[str] = []
    race = P.parse_shutuba(client.shutuba(race_id), race_id)

    if not race.entries:
        warnings.append("出馬表が未確定（枠順・出走馬が未発表）。確定後に精度が上がります。")

    # actual conditions + results (present only once a race has run)
    if want_result:
        try:
            db_html = client.race_db(race_id)
            dbrace = P.parse_race_db(db_html, race_id)
            if dbrace.entries or dbrace.result or dbrace.name:
                _merge_result_page(race, dbrace)
            race.payouts = P.parse_payouts(db_html)
        except Exception:
            pass

    if not race.weather:
        warnings.append("当日の天候が未確定のため、天候相性は暫定評価です。")
    if not race.going:
        warnings.append("当日の馬場状態が未確定のため、道悪適性は暫定評価です。")
    if not any(e.odds for e in race.entries) and not race.result_odds:
        warnings.append("オッズ未発売のため、期待値（妙味）の算出は暫定です。")

    # workout (追い切り) table for the whole race — one fetch
    workouts: dict[str, dict] = {}
    try:
        workouts = P.parse_oikiri(client.oikiri(race_id))
    except Exception:
        pass
    for e in race.entries:
        w = workouts.get(e.horse_id)
        if w:
            e.workout_eval = w.get("eval", "")
            e.workout_comment = w.get("comment", "")
    if not workouts:
        warnings.append("追い切り情報が未公開（暫定評価）。木〜金の更新で反映されます。")

    horses: dict[str, Horse] = {}
    thin = 0
    _sire_cache: dict[str, dict] = {}
    for e in race.entries:
        if not e.horse_id:
            continue
        try:
            h = P.parse_horse_history(client.horse_history(e.horse_id), e.horse_id)
        except Exception:
            h = Horse(horse_id=e.horse_id, name=e.horse_name)
        h.name = h.name or e.horse_name
        # pedigree + sire progeny stats (③ 血統)
        try:
            h.pedigree = P.parse_pedigree(client.pedigree(e.horse_id))
            sid = h.pedigree.get("sire_id")
            if sid:
                if sid not in _sire_cache:
                    _sire_cache[sid] = P.parse_sire_stats(client.sire(sid))
                h.sire_stats = _sire_cache[sid]
        except Exception:
            pass
        horses[e.horse_id] = h
        if len(h.history) < 3:
            thin += 1
    if thin:
        warnings.append(f"{thin}頭が実績データ3走未満（新馬・若駒等）で評価は参考値です。")

    return race, horses, warnings


def predict(client: NetkeibaClient, race_id: str, want_result: bool = True) -> RacePrediction:
    race, horses, warnings = load_race(client, race_id, want_result=want_result)
    preds = predict_race(race, horses)
    for p in preds:
        p.comments = horse_comments(p)
    bets = recommend(race, preds)
    rp = RacePrediction(
        race=race,
        horses=preds,
        bets=bets,
        race_comment=race_comment(preds, race),
        pace_scenario=pace_scenario(preds, race),
        confidence_level=field_confidence(preds),
        data_warnings=warnings,
    )
    return rp


# --- weekend helpers --------------------------------------------------------

def upcoming_weekend(today: Optional[date] = None) -> list[str]:
    """Return the [Saturday, Sunday] dates (YYYYMMDD) of the coming weekend."""
    if today is None:
        raise ValueError("pass today explicitly (Date.now is unavailable in some runtimes)")
    # Saturday = weekday 5
    days_to_sat = (5 - today.weekday()) % 7
    sat = today + timedelta(days=days_to_sat)
    sun = sat + timedelta(days=1)
    return [sat.strftime("%Y%m%d"), sun.strftime("%Y%m%d")]


def weekend_race_ids(client: NetkeibaClient, dates: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for d in dates:
        try:
            ids = P.parse_race_list(client.race_list(d))
        except Exception:
            ids = []
        if ids:
            out[d] = ids
    return out
