#!/usr/bin/env python3
"""Generate weekend predictions and write the JSON the web app consumes.

Usage
-----
  # coming weekend (Mon-Fri workflow — predicts the upcoming Sat/Sun)
  python scripts/predict_weekend.py --today 2026-07-06

  # a specific weekend by explicit dates
  python scripts/predict_weekend.py --dates 20250628 20250629

  # limit races (feature races / smaller demo)
  python scripts/predict_weekend.py --dates 20250628 --grade-only --max 12

Output: data/output/weekend_<first-date>.json  (and latest.json)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.netkeiba.client import NetkeibaClient
from engine.pipeline import predict, weekend_race_ids, upcoming_weekend
from engine.settlement import simulate_weekend
from engine.models import dumps, VENUE_CODES


def parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", help="YYYY-MM-DD; predict the coming weekend from this date")
    ap.add_argument("--dates", nargs="+", help="explicit YYYYMMDD dates")
    ap.add_argument("--max", type=int, default=0, help="cap number of races (0 = all)")
    ap.add_argument("--min-race-no", type=int, default=0, help="only races with race_no >= N (feature races)")
    ap.add_argument("--grade-only", action="store_true", help="only OP/graded feature races")
    ap.add_argument("--offline", action="store_true", help="use cache only")
    ap.add_argument("--min-interval", type=float, default=0.8)
    args = ap.parse_args()

    if args.dates:
        dates = args.dates
    elif args.today:
        dates = upcoming_weekend(parse_date(args.today))
    else:
        ap.error("provide --today or --dates")

    client = NetkeibaClient(min_interval=args.min_interval, offline=args.offline)
    id_map = weekend_race_ids(client, dates)
    if not id_map:
        print(f"No races found for {dates} (entries may not be published yet).")
        # still write an empty-but-valid payload so the UI can show the state
    race_ids: list[str] = []
    for d in dates:
        for rid in id_map.get(d, []):
            if args.min_race_no and int(rid[10:12]) < args.min_race_no:
                continue
            race_ids.append(rid)

    races_out = []
    for i, rid in enumerate(race_ids, 1):
        try:
            rp = predict(client, rid)
        except Exception as e:  # never let one race kill the batch
            print(f"  [skip] {rid}: {e}")
            continue
        if args.grade_only and rp.race.grade not in ("GI", "GII", "GIII", "L", "OP"):
            continue
        d = rp.to_dict()
        # strip non-serialisable helper attribute if present
        races_out.append(d)
        mark = rp.horses[0].confidence if rp.horses else ""
        print(f"  [{i}/{len(race_ids)}] {rp.race.venue}{rp.race.race_no}R {rp.race.name} "
              f"→ {mark}{rp.horses[0].horse_name if rp.horses else '?'} ({len(rp.horses)}頭)")
        if args.max and len(races_out) >= args.max:
            break

    # earnings simulation: settle every recommendation against real dividends
    simulation = simulate_weekend(races_out, unit_yen=100, bankroll0=100_000)

    payload = {
        "generated_for": dates,
        "race_count": len(races_out),
        "venues": sorted({r["race"]["venue"] for r in races_out}),
        "simulation": simulation,
        "races": races_out,
    }
    if simulation.get("n_bets"):
        print(f"\n収支シミュレーション: {simulation['n_bets']}点 / 的中率{simulation['hit_rate']*100:.0f}% / "
              f"投資{simulation['staked']:,}円 → 回収{simulation['returned']:,}円 "
              f"(収支{simulation['profit']:+,}円・回収率{simulation['roi']*100:.0f}%)")
    out_dir = ROOT / "data" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = out_dir / f"weekend_{dates[0]}.json"
    fname.write_text(dumps(payload), encoding="utf-8")
    (out_dir / "latest.json").write_text(dumps(payload), encoding="utf-8")
    # also drop a copy where the web app reads it
    web_data = ROOT / "web" / "public" / "data"
    web_data.mkdir(parents=True, exist_ok=True)
    (web_data / "weekend.json").write_text(dumps(payload), encoding="utf-8")
    print(f"\nWrote {len(races_out)} races -> {fname}")


if __name__ == "__main__":
    main()
