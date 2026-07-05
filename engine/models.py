"""Core data models for the horse-racing prediction engine.

These dataclasses are the single source of truth for the shape of data that
flows through the pipeline:  scrape -> parse -> feature engineering ->
scoring -> betting -> commentary -> JSON for the web app.

Everything is plain stdlib so the models can be imported anywhere without
pulling in heavy dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


# --- Reference data ---------------------------------------------------------

# netkeiba venue codes (embedded in every race_id: positions 5-6).
VENUE_CODES: dict[str, str] = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
VENUE_CODES_EN: dict[str, str] = {
    "01": "Sapporo", "02": "Hakodate", "03": "Fukushima", "04": "Niigata",
    "05": "Tokyo", "06": "Nakayama", "07": "Chukyo", "08": "Kyoto",
    "09": "Hanshin", "10": "Kokura",
}


# --- Past-performance line (one historical start for a horse) ---------------

@dataclass
class PastRun:
    date: str = ""                 # YYYY/MM/DD
    venue: str = ""                # 函館, 東京 ...
    weather: str = ""              # 晴 曇 雨 小雨 雪 ...
    race_name: str = ""
    grade: str = ""                # GI / GII / GIII / OP / L / '' ...
    field_size: Optional[int] = None
    draw: Optional[int] = None     # 枠番
    horse_no: Optional[int] = None # 馬番
    odds: Optional[float] = None
    popularity: Optional[int] = None   # 人気 (favouritism rank)
    finish: Optional[int] = None       # 着順 (None if DNF/scratched)
    jockey: str = ""
    weight_carried: Optional[float] = None  # 斤量 (kg)
    surface: str = ""              # 芝 / ダ
    distance: Optional[int] = None # metres
    going: str = ""                # 良 稍 重 不 (track condition)
    time_index: Optional[int] = None    # netkeiba speed figure (タイム指数)
    passing: str = ""              # 通過 (running positions, e.g. "7-8")
    last_3f: Optional[float] = None     # 上がり 3F seconds
    body_weight: Optional[int] = None   # 馬体重 (kg)
    margin: Optional[float] = None      # 着差
    prize: Optional[float] = None       # 賞金 (万円)

    @property
    def is_win(self) -> bool:
        return self.finish == 1

    @property
    def is_placed(self) -> bool:  # top-3 (複勝圏)
        return self.finish is not None and self.finish <= 3


# --- A horse and its dossier ------------------------------------------------

@dataclass
class Horse:
    horse_id: str
    name: str = ""
    sex: str = ""                  # 牡 牝 セ
    age: Optional[int] = None
    career: str = ""               # e.g. "33戦6勝"
    record: str = ""               # e.g. "6-11-6-10" (1st-2nd-3rd-out)
    history: list[PastRun] = field(default_factory=list)
    # ancestry: {sire, sire_id, dam, damsire, damsire_id}
    pedigree: dict = field(default_factory=dict)
    # sire progeny aggregates: {starts, wins, win_rate, graded_wins}
    sire_stats: dict = field(default_factory=dict)


# --- An entry = a horse declared to run in a specific upcoming race ---------

@dataclass
class Entry:
    horse_id: str
    horse_name: str
    draw: Optional[int] = None
    horse_no: Optional[int] = None
    sex_age: str = ""
    weight_carried: Optional[float] = None
    jockey: str = ""
    jockey_id: str = ""
    trainer: str = ""
    body_weight: Optional[int] = None
    body_weight_diff: Optional[int] = None
    odds: Optional[float] = None
    popularity: Optional[int] = None
    # final-workout (追い切り) signal from the oikiri page
    workout_eval: str = ""         # S / A / B / C / D evaluation letter
    workout_comment: str = ""      # 短評 (e.g. 気配上々)


# --- The race being predicted ----------------------------------------------

@dataclass
class Race:
    race_id: str
    name: str = ""
    date: str = ""                 # YYYY-MM-DD
    venue: str = ""
    venue_en: str = ""
    race_no: Optional[int] = None
    surface: str = ""              # 芝 / ダ
    distance: Optional[int] = None
    direction: str = ""            # 右 / 左 / 直
    grade: str = ""
    going: str = ""                # actual/forecast track condition
    weather: str = ""              # actual/forecast weather
    field_size: Optional[int] = None
    entries: list[Entry] = field(default_factory=list)
    off_time: str = ""             # HH:MM
    # populated post-race for back-testing
    result: dict[str, int] = field(default_factory=dict)      # horse_id -> finish
    result_odds: dict[str, float] = field(default_factory=dict)  # horse_id -> final win odds
    result_pop: dict[str, int] = field(default_factory=dict)   # horse_id -> final favourite rank


# --- Prediction output for a single horse ----------------------------------

@dataclass
class HorsePrediction:
    horse_id: str
    horse_no: Optional[int]
    horse_name: str
    jockey: str
    # component scores (0-100, higher = better fit)
    factors: dict[str, float] = field(default_factory=dict)
    ability: float = 0.0           # blended raw score
    win_prob: float = 0.0          # normalised across field
    place_prob: float = 0.0
    odds: Optional[float] = None
    fair_odds: Optional[float] = None
    value: Optional[float] = None  # EV edge = win_prob*odds - 1
    rank: int = 0                  # model's predicted finishing rank
    confidence: str = ""           # ◎ ◯ ▲ △ ☆ or ''
    comments: list[dict] = field(default_factory=list)  # multi-perspective


@dataclass
class BetRecommendation:
    bet_type: str                  # 単勝 / 複勝 / 馬連 / ワイド / 3連複 ...
    selection: str                 # human readable ("5 → 3,8")
    stake_units: float             # suggested stake in units
    expected_value: float          # EV multiple (1.0 = break-even)
    hit_prob: float
    rationale: str


@dataclass
class RacePrediction:
    race: Race
    horses: list[HorsePrediction] = field(default_factory=list)
    bets: list[BetRecommendation] = field(default_factory=list)
    race_comment: str = ""
    pace_scenario: str = ""
    confidence_level: str = ""     # 本命サイド / 波乱含み / 大波乱
    data_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def dumps(obj) -> str:
    """JSON with dataclass support and Japanese kept readable."""
    def default(o):
        try:
            return asdict(o)
        except TypeError:
            return str(o)
    return json.dumps(obj, default=default, ensure_ascii=False, indent=2)
