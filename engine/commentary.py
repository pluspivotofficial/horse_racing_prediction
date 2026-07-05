"""Multi-perspective commentary.

The user asked for "いろんな視点でコメント" — so instead of one flat verdict we
speak through five analyst personas, each of which reads the same numbers
through a different lens:

  📊 データ分析官   — cold factor scores, form, class
  🐎 展開ラボ        — running style, pace scenario, closing speed
  🤝 相性ウォッチャー — jockey / course / weather / going compatibility
  💰 オッズ妙味ハンター — market vs model, where the value is
  ⚠️ リスク番人       — the case against; what could go wrong

A persona only speaks when it actually has something to say, so the mix of
voices differs per horse — which reads far more like a real handicapping desk.
"""
from __future__ import annotations

from typing import Optional

from .models import HorsePrediction, Race
from .scoring import field_confidence


PERSONAS = {
    "data": ("📊", "データ分析官"),
    "pace": ("🐎", "展開ラボ"),
    "fit": ("🤝", "相性ウォッチャー"),
    "workout": ("🔬", "調教アナリスト"),
    "pedigree": ("🧬", "血統ラボ"),
    "value": ("💰", "妙味ハンター"),
    "risk": ("⚠️", "リスク番人"),
}


def _c(key: str, text: str) -> dict:
    icon, name = PERSONAS[key]
    return {"persona": key, "icon": icon, "name": name, "text": text}


def horse_comments(p: HorsePrediction) -> list[dict]:
    f = getattr(p, "_factors_full", {})
    out: list[dict] = []

    # 📊 data analyst — lead with the strongest and weakest factor
    if f:
        ranked = sorted(f.values(), key=lambda x: x.score, reverse=True)
        best, worst = ranked[0], ranked[-1]
        verdict = "本命級の総合力" if p.ability >= 60 else \
                  "上位拮抗の一角" if p.ability >= 53 else \
                  "抑え・ヒモ評価"
        out.append(_c("data",
            f"総合スコア{p.ability:.0f}／{verdict}。最大の強みは『{best.label}』（{best.note}）。"
            f"想定勝率{p.win_prob*100:.0f}%・複勝率{p.place_prob*100:.0f}%。"))
        if worst.score <= 47:
            out.append(_c("risk", f"不安要素は『{worst.label}』— {worst.note}。"))

    # 🐎 pace lab
    pace = f.get("pace_fit")
    if pace:
        out.append(_c("pace", pace.note + "。"))

    # 🔬 workout — speak when there's a real evaluation (positive or negative)
    wk = f.get("workout")
    if wk and wk.sample:
        if wk.score >= 60:
            out.append(_c("workout", f"{wk.note} 上昇気配で状態は good。"))
        elif wk.score <= 47:
            out.append(_c("risk", f"調教面がやや不安：{wk.note}。"))
        else:
            out.append(_c("workout", f"{wk.note}。"))

    # 🧬 pedigree — speak when it adds signal (unproven condition or strong blood)
    pg = f.get("pedigree")
    if pg and pg.sample and (pg.score >= 55 or pg.score <= 47 or "初" in pg.note or "替わり" in pg.note):
        out.append(_c("pedigree", pg.note + "。"))

    # 🤝 compatibility — surface the best-fitting condition factor with a real edge
    fit_keys = ["jockey_fit", "course_fit", "going_fit", "weather_fit", "distance_fit"]
    fits = [f[k] for k in fit_keys if k in f and f[k].sample >= 2]
    fits.sort(key=lambda x: x.score, reverse=True)
    if fits and fits[0].score >= 55:
        out.append(_c("fit", f"◎相性:{fits[0].note}。"))
    # also flag a notable *negative* fit
    neg = [x for x in fits if x.score <= 46]
    if neg:
        out.append(_c("risk", f"{neg[0].label}に懸念:{neg[0].note}。"))

    # 💰 value hunter
    if p.odds and p.value is not None:
        if p.value > 0.1:
            out.append(_c("value",
                f"オッズ{p.odds}倍は美味しい。モデル的中率換算の妥当オッズは{p.fair_odds}倍前後で、"
                f"期待値{(p.win_prob*p.odds):.2f}倍の“買い”。"))
        elif p.value < -0.25 and p.rank <= 3:
            out.append(_c("value",
                f"人気先行。オッズ{p.odds}倍は実力以上に売れており、妙味は薄い（妥当{p.fair_odds}倍）。"))
    return out


def pace_scenario(preds: list[HorsePrediction], race: Race) -> str:
    """Read the field's running styles to narrate the likely pace."""
    fronts = 0
    for p in preds:
        f = getattr(p, "_factors_full", {})
        pf = f.get("pace_fit")
        if pf and ("逃げ" in pf.note or "先行" in pf.note):
            fronts += 1
    n = len(preds)
    if n == 0:
        return ""
    ratio = fronts / n
    surf = "芝" if race.surface == "芝" else "ダート"
    if ratio >= 0.4:
        return (f"前に行きたい馬が{fronts}頭と多く、{surf}{race.distance}mは"
                f"ハイペース濃厚。差し・追込勢に展開が向く見込み。")
    if ratio <= 0.2:
        return (f"逃げ・先行タイプが{fronts}頭と手薄。スローペースからの"
                f"瞬発力勝負になりやすく、前残り・先行有利の展開。")
    return (f"先行勢{fronts}頭で平均ペース想定。大きな展開の偏りは小さく、"
            f"地力上位が力を出しやすい流れ。")


def race_comment(preds: list[HorsePrediction], race: Race) -> str:
    if not preds:
        return "出走データが揃っていません。"
    conf = field_confidence(preds)
    a, b = preds[0], preds[1] if len(preds) > 1 else preds[0]
    gap = a.win_prob - b.win_prob
    lead = (f"本命は◎{a.horse_no}{a.horse_name}（想定勝率{a.win_prob*100:.0f}%）。"
            if gap > 0.08 else
            f"◎{a.horse_no}{a.horse_name}と◯{b.horse_no}{b.horse_name}が拮抗（勝率{a.win_prob*100:.0f}% vs {b.win_prob*100:.0f}%）。")
    # find the biggest value pick
    values = [p for p in preds if p.value and p.value > 0.1]
    val = ""
    if values:
        v = max(values, key=lambda p: p.value)
        if v.rank > 1:
            val = f" 妙味なら{v.horse_no}{v.horse_name}（オッズ{v.odds}倍・期待値{(v.win_prob*v.odds):.2f}）。"
    return f"{lead} 全体は「{conf}」。{val}"
