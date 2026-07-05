"""Feature engineering — turn a horse's raw history into compatibility scores.

Every factor returns a :class:`Factor` with:
  * ``score``  0-100, where 50 is "neutral / unknown" and higher is better fit
  * ``note``   a short Japanese phrase used by the commentary layer
  * ``sample`` how many relevant past runs backed the score (for confidence)

The factors are intentionally interpretable rather than a black box, because
the product's whole promise is *explaining* why a horse is a bet — "いろんな
視点でコメントできるように".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable

from .models import Horse, Race, Entry, PastRun


@dataclass
class Factor:
    key: str
    label: str          # Japanese display label
    score: float        # 0-100
    note: str           # human-readable evidence
    sample: int = 0     # relevant runs behind it


# -- primitives --------------------------------------------------------------

def _norm_finish(run: PastRun) -> Optional[float]:
    """1.0 = won, 0.0 = came last.  None if unusable."""
    if run.finish is None or not run.field_size or run.field_size < 2:
        return None
    return 1.0 - (run.finish - 1) / (run.field_size - 1)


def _recency_weights(n: int, half_life: float = 4.0) -> list[float]:
    return [0.5 ** (i / half_life) for i in range(n)]


def _weighted_perf(runs: list[PastRun]) -> Optional[float]:
    """Recency-weighted average normalised finish -> 0-100."""
    pairs = [(_norm_finish(r), w) for r, w in zip(runs, _recency_weights(len(runs)))]
    pairs = [(v, w) for v, w in pairs if v is not None]
    if not pairs:
        return None
    num = sum(v * w for v, w in pairs)
    den = sum(w for _, w in pairs)
    return 100.0 * num / den


def _rate(runs: list[PastRun]) -> tuple[float, float]:
    """(win_rate, place_rate) over runs with a known finish."""
    fin = [r for r in runs if r.finish is not None]
    if not fin:
        return 0.0, 0.0
    wins = sum(1 for r in fin if r.finish == 1)
    plc = sum(1 for r in fin if r.finish <= 3)
    return wins / len(fin), plc / len(fin)


def _shrink(cond_score: Optional[float], base: float, sample: int, k: int = 3) -> float:
    """Pull a small-sample conditional score toward the horse's baseline.

    With few relevant runs we trust the specific signal less.
    """
    if cond_score is None:
        return base
    weight = sample / (sample + k)
    return cond_score * weight + base * (1 - weight)


# -- individual factors ------------------------------------------------------

def f_recent_form(horse: Horse, race: Race, entry: Entry) -> Factor:
    runs = horse.history[:6]
    perf = _weighted_perf(runs)
    if perf is None:
        return Factor("recent_form", "近走成績", 50, "実績データ不足", 0)
    wr, pr = _rate(runs)
    fins = [r.finish for r in runs[:5] if r.finish]
    trend = ""
    if len(fins) >= 3:
        recent, older = fins[:2], fins[2:]
        if sum(recent) / len(recent) + 1.5 < sum(older) / len(older):
            trend = "・上昇度○"
        elif sum(recent) / len(recent) > sum(older) / len(older) + 1.5:
            trend = "・やや下降"
    seq = "-".join(str(f) for f in fins[:5]) if fins else "?"
    note = f"近5走 {seq} 着（複勝率{pr*100:.0f}%){trend}"
    return Factor("recent_form", "近走成績", perf, note, len(runs))


def _base_perf(horse: Horse) -> float:
    return _weighted_perf(horse.history[:10]) or 50.0


def f_course_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    runs = [r for r in horse.history if r.venue and r.venue == race.venue]
    base = _base_perf(horse)
    perf = _weighted_perf(runs)
    score = _shrink(perf, base, len(runs))
    wr, pr = _rate(runs)
    if runs:
        note = f"{race.venue}競馬場 {len(runs)}戦 複勝率{pr*100:.0f}%・勝率{wr*100:.0f}%"
    else:
        note = f"{race.venue}競馬場は初出走（未知数）"
    return Factor("course_fit", "コース適性", score, note, len(runs))


def f_distance_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    if not race.distance:
        return Factor("distance_fit", "距離適性", 50, "距離不明", 0)
    band = 200
    runs = [r for r in horse.history if r.distance and abs(r.distance - race.distance) <= band]
    base = _base_perf(horse)
    perf = _weighted_perf(runs)
    score = _shrink(perf, base, len(runs))
    wr, pr = _rate(runs)
    if runs:
        note = f"{race.distance}m前後 {len(runs)}戦 複勝率{pr*100:.0f}%"
    else:
        note = f"{race.distance}m近辺は経験薄く距離適性は未知数"
    return Factor("distance_fit", "距離適性", score, note, len(runs))


def f_surface_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    if not race.surface:
        return Factor("surface_fit", "馬場適性", 50, "馬場種別不明", 0)
    runs = [r for r in horse.history if r.surface == race.surface]
    base = _base_perf(horse)
    perf = _weighted_perf(runs)
    score = _shrink(perf, base, len(runs))
    kind = "芝" if race.surface == "芝" else "ダート"
    wr, pr = _rate(runs)
    if runs:
        note = f"{kind} {len(runs)}戦 複勝率{pr*100:.0f}%"
    else:
        note = f"{kind}替わりで一変あるか"
    return Factor("surface_fit", "馬場適性", score, note, len(runs))


def f_going_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    if not race.going:
        return Factor("going_fit", "馬場状態", 50, "当日の馬場状態が未確定", 0)
    runs = [r for r in horse.history if r.going and r.going[0] == race.going[0]]
    base = _base_perf(horse)
    perf = _weighted_perf(runs)
    score = _shrink(perf, base, len(runs))
    label = {"良": "良馬場", "稍": "稍重", "重": "重馬場", "不": "不良"}.get(race.going[0], race.going)
    wr, pr = _rate(runs)
    if runs:
        note = f"{label} {len(runs)}戦 複勝率{pr*100:.0f}%"
    else:
        note = f"{label}は経験なし・対応力は未知数"
    return Factor("going_fit", "馬場状態", score, note, len(runs))


def f_weather_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    if not race.weather:
        return Factor("weather_fit", "天候相性", 50, "当日の天候が未確定", 0)
    wet = race.weather in ("雨", "小雨", "雪")
    if wet:
        runs = [r for r in horse.history if r.weather in ("雨", "小雨", "雪")]
        label = "道悪(雨)"
    else:
        runs = [r for r in horse.history if r.weather in ("晴", "曇")]
        label = "良好な天候"
    base = _base_perf(horse)
    perf = _weighted_perf(runs)
    score = _shrink(perf, base, len(runs))
    wr, pr = _rate(runs)
    if runs:
        note = f"{label}({race.weather})で {len(runs)}戦 複勝率{pr*100:.0f}%"
    else:
        note = f"{label}({race.weather})の実績乏しい"
    return Factor("weather_fit", "天候相性", score, note, len(runs))


def f_jockey_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    jk = entry.jockey or ""
    if not jk:
        return Factor("jockey_fit", "騎手相性", 50, "騎手未定", 0)
    with_jk = [r for r in horse.history if r.jockey and jk[:2] in r.jockey]
    base = _base_perf(horse)
    perf = _weighted_perf(with_jk)
    score = _shrink(perf, base, len(with_jk))
    wr, pr = _rate(with_jk)
    prev = horse.history[0].jockey if horse.history else ""
    change = prev and jk[:2] not in (prev or "")
    if with_jk:
        note = f"{jk}騎手とは {len(with_jk)}戦 複勝率{pr*100:.0f}%（手が合う）" if pr >= 0.4 else \
               f"{jk}騎手とは {len(with_jk)}戦 複勝率{pr*100:.0f}%"
    elif change:
        note = f"今回{jk}騎手へ乗り替わり（初コンビ）"
    else:
        note = f"{jk}騎手との初コンビ"
    return Factor("jockey_fit", "騎手相性", score, note, len(with_jk))


# grade ordering for class assessment
_GRADE_RANK = {"GI": 6, "GII": 5, "GIII": 4, "L": 3, "OP": 3, "": 2}


def f_class_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    today = _GRADE_RANK.get(race.grade, 2)
    # best finish at today's class-or-higher
    strong = [r for r in horse.history if _GRADE_RANK.get(r.grade, 2) >= today]
    perf = _weighted_perf(strong)
    base = _base_perf(horse)
    score = _shrink(perf, base, len(strong), k=2)
    if strong:
        best = min((r.finish for r in strong if r.finish), default=None)
        wr, pr = _rate(strong)
        lvl = race.grade or "同クラス"
        note = f"{lvl}級で {len(strong)}戦・最高{best}着（複勝率{pr*100:.0f}%）" if best else \
               f"{lvl}級で {len(strong)}戦の経験"
    else:
        note = "今回が実質格上挑戦・クラスの壁は課題"
        score = min(score, 48)
    return Factor("class_fit", "クラス実績", score, note, len(strong))


def _running_style(horse: Horse) -> tuple[str, float]:
    """Infer style from 通過 first-corner position ratio. Returns (label, front_bias)."""
    ratios = []
    for r in horse.history[:8]:
        if r.passing and r.field_size:
            try:
                first = int(r.passing.split("-")[0])
                ratios.append(first / r.field_size)
            except (ValueError, ZeroDivisionError):
                pass
    if not ratios:
        return "自在", 0.5
    avg = sum(ratios) / len(ratios)
    if avg <= 0.25:
        return "逃げ・先行", avg
    if avg <= 0.5:
        return "先行", avg
    if avg <= 0.72:
        return "差し", avg
    return "追込", avg


def f_pace_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    style, bias = _running_style(horse)
    # last-3F closing ability
    l3 = [r.last_3f for r in horse.history[:6] if r.last_3f and 30 <= r.last_3f <= 40]
    close = None
    if l3:
        best = min(l3)
        close = max(0.0, min(100.0, (36.0 - best) / (36.0 - 32.5) * 100))
    base = 50.0
    if close is not None:
        base = 45 + close * 0.35
    note = f"脚質は{style}"
    if l3:
        note += f"・上がり最速{min(l3):.1f}秒の決め手"
    return Factor("pace_fit", "脚質・決め手", base, note, len(l3))


def f_draw_fit(horse: Horse, race: Race, entry: Entry) -> Factor:
    # post-position bias matters most in sprints; mild elsewhere
    if not entry.draw or not race.field_size or not race.distance:
        return Factor("draw_fit", "枠順", 50, "枠順の影響は限定的", 0)
    pos = entry.draw / race.field_size
    score = 50.0
    note = f"{entry.draw}番枠"
    if race.distance <= 1400 and race.surface == "芝":
        # inner draws favoured in turf sprints
        score = 58 - pos * 16
        note += "（短距離・内枠有利の傾向）" if pos < 0.4 else "（外枠でロスは気になる）"
    else:
        score = 52 - abs(pos - 0.45) * 8
        note += "（枠の有利不利は小さい）"
    return Factor("draw_fit", "枠順", max(40, min(62, score)), note, 0)


_WK_SCORE = {"S": 70, "A": 65, "B": 55, "C": 46, "D": 40, "E": 36}
_WK_POS = ("上々", "絶好", "抜群", "良化", "上積", "躍動", "順調", "合格", "変身", "文句", "十分", "併せ先着")
_WK_NEG = ("平凡", "平行", "イマイチ", "物足", "一息", "案外", "重い", "消", "非力", "遅れ")


def f_workout(horse: Horse, race: Race, entry: Entry) -> Factor:
    """Final-workout (追い切り) evaluation letter + short note."""
    ev = (entry.workout_eval or "").upper()
    cm = entry.workout_comment or ""
    if not ev and not cm:
        return Factor("workout", "追い切り", 50, "追い切り情報は未公開（暫定評価）", 0)
    score = _WK_SCORE.get(ev, 52)
    if any(k in cm for k in _WK_POS):
        score += 3
    if any(k in cm for k in _WK_NEG):
        score -= 4
    score = max(38, min(72, score))
    parts = []
    if ev:
        parts.append(f"追い切り評価{ev}")
    if cm:
        parts.append(cm)
    tone = "動き良好" if score >= 60 else "標準" if score >= 48 else "見劣り"
    return Factor("workout", "追い切り", score, "・".join(parts) + f"（{tone}）", 1 if ev else 0)


def f_pedigree(horse: Horse, race: Race, entry: Entry) -> Factor:
    """Bloodline quality (sire progeny stats), weighted up when the horse is
    unproven at today's surface/distance — where pedigree matters most."""
    ped = horse.pedigree or {}
    ss = horse.sire_stats or {}
    if not ped.get("sire"):
        return Factor("pedigree", "血統", 50, "血統情報を取得できませんでした", 0)
    wr = ss.get("win_rate")
    graded = ss.get("graded_wins", 0)
    if wr is not None:
        quality = 46 + (wr - 0.05) * 350
        if graded >= 20:
            quality += 4
        elif graded >= 8:
            quality += 2
        quality = max(42, min(66, quality))
    else:
        quality = 50
    surf_runs = sum(1 for r in horse.history if r.surface == race.surface)
    dist_runs = sum(1 for r in horse.history
                    if r.distance and race.distance and abs(r.distance - race.distance) <= 200)
    unproven = surf_runs < 2 or dist_runs < 2
    score = quality if unproven else 50 + (quality - 50) * 0.4
    sire = ped.get("sire", "?")
    ds = ped.get("damsire", "")
    wr_txt = f"産駒勝率{wr*100:.0f}%" if wr is not None else "産駒成績不明"
    g_txt = f"・重賞{graded}勝" if graded else ""
    note = f"父{sire}（{wr_txt}{g_txt}）"
    if ds:
        note += f"×母父{ds}"
    if unproven:
        cond = "初" + ("芝" if race.surface == "芝" else "ダート") if surf_runs < 2 else "距離替わり"
        note += f"。{cond}だが血統的な後押しは" + ("あり" if score >= 54 else "限定的")
    return Factor("pedigree", "血統", score, note, 1 if wr is not None else 0)


def f_condition(horse: Horse, race: Race, entry: Entry) -> Factor:
    """Body-weight trend + days-since-last-run (rotation)."""
    notes = []
    score = 50.0
    if entry.body_weight_diff is not None:
        d = entry.body_weight_diff
        if -6 <= d <= 8:
            score += 4
            notes.append(f"馬体重{d:+d}kgと good")
        elif d < -6:
            score -= 4
            notes.append(f"馬体重{d:+d}kgで大きく減・要注意")
        else:
            notes.append(f"馬体重{d:+d}kgで増加")
    # rotation from date gap
    if len(horse.history) >= 1 and horse.history[0].date and race.date:
        try:
            from datetime import date
            y, m, d0 = horse.history[0].date.split("/")
            last = date(int(y), int(m), int(d0))
            ry, rm, rd = race.date.split("-")
            gap = (date(int(ry), int(rm), int(rd)) - last).days
            if 14 <= gap <= 60:
                score += 3
                notes.append(f"中{gap}日の好ローテ")
            elif gap > 120:
                score -= 3
                notes.append(f"{gap}日ぶりの休み明け")
            elif gap < 14:
                notes.append(f"中{gap}日の詰めた使い")
        except (ValueError, TypeError):
            pass
    if not notes:
        notes.append("状態面は平均的")
    return Factor("condition", "馬体・調子", max(40, min(60, score)), "・".join(notes), 0)


# -- registry & weights ------------------------------------------------------

FACTORS: list[Callable[[Horse, Race, Entry], Factor]] = [
    f_recent_form, f_class_fit, f_distance_fit, f_course_fit, f_surface_fit,
    f_going_fit, f_weather_fit, f_jockey_fit, f_pace_fit, f_workout, f_pedigree,
    f_draw_fit, f_condition,
]

# weights sum ~1.0 — form + class dominate; workout/pedigree/相性 refine
WEIGHTS: dict[str, float] = {
    "recent_form": 0.20,
    "class_fit": 0.14,
    "distance_fit": 0.10,
    "course_fit": 0.08,
    "surface_fit": 0.05,
    "going_fit": 0.06,
    "weather_fit": 0.04,
    "jockey_fit": 0.08,
    "pace_fit": 0.06,
    "workout": 0.07,
    "pedigree": 0.05,
    "draw_fit": 0.03,
    "condition": 0.04,
}


def compute_factors(horse: Horse, race: Race, entry: Entry) -> dict[str, Factor]:
    return {f.__name__.replace("f_", ""): f(horse, race, entry) for f in FACTORS}
