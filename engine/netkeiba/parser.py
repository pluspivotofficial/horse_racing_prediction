"""HTML -> structured data.

All selectors here were verified against live netkeiba pages (2025-2026 layout).
Parsing is deliberately defensive: netkeiba mutates markup often and a free
account hides some columns (they render as ``**``), so every field is optional
and we degrade gracefully rather than crash a whole weekend's run.
"""
from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from ..models import (
    Race, Entry, Horse, PastRun, VENUE_CODES, VENUE_CODES_EN,
)

GRADE_RE = re.compile(r"\((G[I]{1,3}|Jpn[I]{1,3}|L|OP)\)")
DIST_RE = re.compile(r"(芝|ダ|障)\s*[右左直]?\s*(\d{3,4})")
BODY_RE = re.compile(r"(\d{3})\s*\(([-+]?\d+)\)")


def _text(el) -> str:
    return el.get_text(strip=True) if el else ""


def _first_idx(header: list[str], needles: list[str]) -> Optional[int]:
    for i, h in enumerate(header):
        if any(n in h for n in needles):
            return i
    return None


def _num(s: str) -> Optional[float]:
    s = (s or "").replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _int(s: str) -> Optional[int]:
    f = _num(s)
    return int(f) if f is not None else None


# --------------------------------------------------------------------------
# race list for a date
# --------------------------------------------------------------------------
def parse_race_list(html: str) -> list[str]:
    """Return ordered, de-duplicated race_ids present on a date's list page."""
    seen, out = set(), []
    for m in re.finditer(r"race_id=(\d{12})", html):
        rid = m.group(1)
        if rid not in seen:
            seen.add(rid)
            out.append(rid)
    return out


def race_id_meta(race_id: str) -> dict:
    """Decode the structured info baked into a race_id.

    Format: YYYY VV KK DD RR  (year, venue, kai, day, race-no)
    """
    return {
        "year": race_id[0:4],
        "venue_code": race_id[4:6],
        "venue": VENUE_CODES.get(race_id[4:6], "?"),
        "venue_en": VENUE_CODES_EN.get(race_id[4:6], "?"),
        "kai": int(race_id[6:8]),
        "day": int(race_id[8:10]),
        "race_no": int(race_id[10:12]),
    }


# --------------------------------------------------------------------------
# upcoming entries (shutuba)
# --------------------------------------------------------------------------
def parse_shutuba(html: str, race_id: str) -> Race:
    soup = BeautifulSoup(html, "lxml")
    meta = race_id_meta(race_id)
    race = Race(
        race_id=race_id,
        venue=meta["venue"],
        venue_en=meta["venue_en"],
        race_no=meta["race_no"],
    )

    name_el = soup.select_one(".RaceName")
    if name_el:
        race.name = name_el.get_text(strip=True)
    title = soup.select_one("title")
    if title and not race.name:
        race.name = title.get_text(strip=True).split("|")[0].strip()

    data01 = _text(soup.select_one(".RaceData01"))
    _apply_conditions(race, data01)
    m = re.search(r"(\d{1,2}):(\d{2})", data01)
    if m:
        race.off_time = m.group(0)

    grade = GRADE_RE.search(race.name or "")
    if grade:
        race.grade = grade.group(1)

    for tr in soup.select("tr.HorseList"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        horse_a = tr.select_one('a[href*="/horse/"]')
        jockey_a = tr.select_one('a[href*="/jockey/"]')
        hid = re.search(r"/horse/(\d+)", horse_a["href"]).group(1) if horse_a else ""
        jid = re.search(r"/jockey/[a-z/]*(\d+)", jockey_a["href"]).group(1) if jockey_a else ""
        cells = [_text(td) for td in tds]
        odds, pop = _shutuba_odds_pop(cells)
        entry = Entry(
            horse_id=hid,
            horse_name=_text(horse_a) or _pick(cells, 3),
            draw=_int(_pick(cells, 0)),
            horse_no=_int(_pick(cells, 1)),
            sex_age=_find_sex_age(cells),
            weight_carried=_num(_find_weight_carried(cells)),
            jockey=_text(jockey_a),
            jockey_id=jid,
            trainer=_find_trainer(tr),
            odds=odds,
            popularity=pop,
        )
        bw = BODY_RE.search(" ".join(cells))
        if bw:
            entry.body_weight = int(bw.group(1))
            entry.body_weight_diff = int(bw.group(2))
        race.entries.append(entry)

    race.field_size = len(race.entries)
    return race


def _pick(cells: list[str], i: int) -> str:
    return cells[i] if 0 <= i < len(cells) else ""


def _find_sex_age(cells: list[str]) -> str:
    for c in cells:
        if re.fullmatch(r"[牡牝セせん]{1,2}\d{1,2}", c):
            return c
    return ""


def _find_weight_carried(cells: list[str]) -> str:
    for c in cells:
        if re.fullmatch(r"\d{2}\.\d", c):
            return c
    return ""


def _find_pop(cells: list[str]) -> str:
    # popularity is a small integer usually near the end
    for c in reversed(cells):
        if re.fullmatch(r"\d{1,2}", c):
            return c
    return ""


def _shutuba_odds_pop(cells: list[str]) -> tuple[Optional[float], Optional[int]]:
    """Odds and favourite-rank sit immediately after the body-weight cell,
    e.g. ... '468(-4)', '3.5', '2', ...  Anchor off body weight to avoid
    mistaking the 55.0 handicap weight for odds."""
    bw_i = next((i for i, c in enumerate(cells) if BODY_RE.search(c) or c in ("計不", "--")), None)
    tail = cells[bw_i + 1:] if bw_i is not None else cells
    odds = next((_num(c) for c in tail if re.fullmatch(r"\d{1,4}\.\d", c)), None)
    pop = None
    if odds is not None:
        after = tail[tail.index(f"{odds:g}") + 1:] if f"{odds:g}" in tail else tail
        pop = next((_int(c) for c in after if re.fullmatch(r"\d{1,2}", c)), None)
    return odds, pop


def _find_trainer(tr) -> str:
    a = tr.select_one('a[href*="/trainer/"]')
    return _text(a)


def _apply_conditions(race: Race, text: str) -> None:
    dm = DIST_RE.search(text)
    if dm:
        race.surface = dm.group(1)
        race.distance = int(dm.group(2))
    if "右" in text:
        race.direction = "右"
    elif "左" in text:
        race.direction = "左"
    elif "直線" in text or "直" in text:
        race.direction = "直"
    wm = re.search(r"天候\s*[:：]?\s*(\S)", text)
    if wm:
        race.weather = wm.group(1)
    gm = re.search(r"馬場\s*[:：]?\s*(\S)", text)
    if gm:
        race.going = gm.group(1)


# --------------------------------------------------------------------------
# post-race DB page (conditions + result)
# --------------------------------------------------------------------------
def parse_race_db(html: str, race_id: str) -> Race:
    soup = BeautifulSoup(html, "lxml")
    meta = race_id_meta(race_id)
    race = Race(
        race_id=race_id, venue=meta["venue"], venue_en=meta["venue_en"],
        race_no=meta["race_no"],
    )
    h1 = soup.select_one("diary_snap_cut h1, .data_intro h1, h1")
    if h1:
        race.name = h1.get_text(strip=True)
    if not race.name:
        title = soup.select_one("title")
        if title:
            race.name = title.get_text(strip=True).split("｜")[0].split("|")[0].strip()
    grade = GRADE_RE.search(race.name or "")
    if grade:
        race.grade = grade.group(1)

    # conditions live in a diary_snap span like "芝右1200m / 天候 : 晴 / 芝 : 良"
    span = ""
    for sp in soup.select("diary_snap_cut span, .data_intro span, p"):
        t = sp.get_text(" ", strip=True)
        if DIST_RE.search(t) and ("天候" in t or "馬場" in t or "良" in t):
            span = t
            break
    if not span:
        span = soup.get_text(" ", strip=True)
    dm = DIST_RE.search(span)
    if dm:
        race.surface, race.distance = dm.group(1), int(dm.group(2))
    if "右" in span[:200]:
        race.direction = "右"
    elif "左" in span[:200]:
        race.direction = "左"
    wm = re.search(r"天候\s*[:：]\s*(\S)", span)
    if wm:
        race.weather = wm.group(1)
    gm = re.search(r"(?:芝|ダート)\s*[:：]\s*(良|稍|重|不)", span)
    if gm:
        race.going = gm.group(1)
    dtm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", html)
    if dtm:
        race.date = f"{dtm.group(1)}-{int(dtm.group(2)):02d}-{int(dtm.group(3)):02d}"

    # result table -> finish / final-odds / popularity per horse, mapped by header
    table = soup.select_one("table.race_table_01")
    if table:
        rows = table.find_all("tr")
        header = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])] if rows else []
        i_fin = _first_idx(header, ["着順"])
        i_odds = _first_idx(header, ["単勝"])
        i_pop = _first_idx(header, ["人気"])
        for tr in rows[1:]:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            row = [_text(td) for td in tds]
            horse_a = tr.select_one('a[href*="/horse/"]')
            finish = _int(row[i_fin]) if i_fin is not None else _int(row[0])
            if horse_a and finish:
                hid = re.search(r"/horse/(\d+)", horse_a["href"]).group(1)
                race.result[hid] = finish
                if i_odds is not None and _num(row[i_odds]) is not None:
                    race.result_odds[hid] = _num(row[i_odds])
                if i_pop is not None and _int(row[i_pop]) is not None:
                    race.result_pop[hid] = _int(row[i_pop])
    race.field_size = len(race.result)
    return race


# --------------------------------------------------------------------------
# horse career history
# --------------------------------------------------------------------------
def parse_horse_history(html: str, horse_id: str, limit: int = 30) -> Horse:
    soup = BeautifulSoup(html, "lxml")
    horse = Horse(horse_id=horse_id)
    table = soup.select_one("table.db_h_race_results")
    if table is None:
        return horse
    rows = table.find_all("tr")
    if not rows:
        return horse
    header = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    idx = _header_index(header)

    for tr in rows[1:]:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        cells = [td.get_text(" ", strip=True).replace("\xa0", " ") for td in tds]

        def col(key: str) -> str:
            i = idx.get(key)
            return cells[i] if i is not None and i < len(cells) else ""

        run = PastRun()
        run.date = col("date").replace("-", "/")
        run.venue = re.sub(r"[\d]", "", col("venue"))
        run.weather = col("weather")
        run.race_name = col("race")
        g = GRADE_RE.search(run.race_name)
        run.grade = g.group(1) if g else ""
        run.field_size = _int(col("field"))
        run.draw = _int(col("draw"))
        run.horse_no = _int(col("horse_no"))
        run.odds = _num(col("odds"))
        run.popularity = _int(col("pop"))
        run.finish = _int(col("finish"))
        run.jockey = col("jockey")
        run.weight_carried = _num(col("weight_carried"))
        dm = DIST_RE.search(col("distance"))
        if dm:
            run.surface, run.distance = dm.group(1), int(dm.group(2))
        run.going = col("going")
        run.time_index = _int(col("time_index"))
        run.passing = col("passing")
        run.last_3f = _num(col("last3f"))
        bw = BODY_RE.search(col("body_weight"))
        if bw:
            run.body_weight = int(bw.group(1))
        run.margin = _num(col("margin"))
        run.prize = _num(col("prize"))
        horse.history.append(run)
        if len(horse.history) >= limit:
            break

    # aggregate line from profile if present
    prof = soup.get_text(" ", strip=True)
    cm = re.search(r"(\d+戦\d+勝)", prof)
    if cm:
        horse.career = cm.group(1)
    return horse


# --------------------------------------------------------------------------
# pedigree (blood table)
# --------------------------------------------------------------------------
def parse_pedigree(html: str) -> dict:
    """Extract sire / dam / damsire from the 3-generation blood table.

    Layout (verified): the two full-height cells (rowspan == max) are sire then
    dam; the first male cell after the dam is the damsire (母父).
    """
    soup = BeautifulSoup(html, "lxml")
    bt = soup.select_one("table.blood_table")
    if not bt:
        return {}
    cells = []
    for td in bt.select("td"):
        a = td.select_one('a[href*="/horse/"]')
        if not a:
            continue
        name = a.get_text(strip=True)
        if name in ("血統", "産駒", ""):
            continue
        hid = re.search(r"/horse/(\w+)/", a["href"])
        cells.append({
            "name": re.split(r"[A-Za-z(]", name)[0] or name,  # strip romaji suffix
            "id": hid.group(1) if hid else "",
            "rowspan": int(td.get("rowspan", 1)),
            "male": "b_ml" in (td.get("class") or []),
        })
    if not cells:
        return {}
    top = max(c["rowspan"] for c in cells)
    fulls = [c for c in cells if c["rowspan"] == top]
    sire = fulls[0] if fulls else cells[0]
    dam = fulls[1] if len(fulls) > 1 else {}
    damsire = {}
    if dam:
        di = cells.index(dam)
        for c in cells[di + 1:]:
            if c["male"]:
                damsire = c
                break
    return {
        "sire": sire.get("name", ""), "sire_id": sire.get("id", ""),
        "dam": dam.get("name", ""),
        "damsire": damsire.get("name", ""), "damsire_id": damsire.get("id", ""),
    }


def _flatten_sire_header(table) -> list[str]:
    """Expand the grouped 2-row sire header into one flat label list.

    Grouped columns (重賞/特別/平場/芝/ダート) carry colspan=2 and split into
    出走/勝利 in the sub-row, e.g. '芝出走','芝勝利'.
    """
    rows = table.select("tr")
    if not rows:
        return []
    flat = []
    for th in rows[0].find_all(["th", "td"]):
        label = th.get_text(strip=True)
        span = int(th.get("colspan", 1))
        if span == 1:
            flat.append(label)
        else:
            flat.extend([label + "出走", label + "勝利"])
    return flat


def parse_sire_stats(html: str) -> dict:
    """Progeny aggregates from the sire page's cumulative (累計) row, including
    surface (芝/ダート) splits, Earnings Index, and average winning distance —
    the raw material for *condition-specific* pedigree aptitude."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.race_table_01")
    if not table:
        return {}
    flat = _flatten_sire_header(table)
    def idx(label):
        return flat.index(label) if label in flat else None
    for tr in table.select("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or cells[0] not in ("累計", "通算"):
            continue

        def at(label):
            i = idx(label)
            return cells[i] if i is not None and i < len(cells) else ""

        starts = _num(at("出走回数")) or _num(cells[4] if len(cells) > 4 else "")
        wins = _num(at("勝利回数")) or _num(cells[5] if len(cells) > 5 else "")
        if not starts or wins is None or starts <= 0:
            return {}
        out = {"starts": int(starts), "wins": int(wins),
               "win_rate": round(wins / starts, 4),
               "graded_wins": int(_num(at("重賞勝利")) or 0)}
        ts, tw = _num(at("芝出走")), _num(at("芝勝利"))
        ds, dw = _num(at("ダート出走")), _num(at("ダート勝利"))
        if ts and tw is not None:
            out["turf_starts"], out["turf_wins"] = int(ts), int(tw)
            out["turf_win_rate"] = round(tw / ts, 4) if ts else None
        if ds and dw is not None:
            out["dirt_starts"], out["dirt_wins"] = int(ds), int(dw)
            out["dirt_win_rate"] = round(dw / ds, 4) if ds else None
        ei = _num(at("EI"))
        if ei is not None:
            out["ei"] = ei
        adt = _num(at("平均距離(芝)"))
        add = _num(at("平均距離(ダ)"))
        if adt:
            out["avg_dist_turf"] = int(adt)
        if add:
            out["avg_dist_dirt"] = int(add)
        return out
    return {}


# --------------------------------------------------------------------------
# workout (追い切り / oikiri)
# --------------------------------------------------------------------------
def parse_oikiri(html: str) -> dict:
    """horse_id -> {eval, comment}. Evaluation letter (S/A/B/C/D) + short note."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, dict] = {}
    for tr in soup.select("tr.HorseList"):
        a = tr.select_one('a[href*="/horse/"]')
        if not a:
            continue
        hid = re.search(r"/horse/(\d+)", a["href"])
        if not hid:
            continue
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        ev = next((c for c in reversed(cells) if re.fullmatch(r"[SABCDE]", c)), "")
        comment = ""
        for c in cells:
            if c and not re.fullmatch(r"[SABCDE]", c) and re.search(r"[ぁ-んァ-ヶ一-龠]", c) \
               and "◎" not in c and len(c) <= 12 and "前走" not in c:
                # first short JP phrase that isn't the horse name row
                if c != (a.get_text(strip=True)):
                    comment = c
                    break
        out[hid.group(1)] = {"eval": ev, "comment": comment}
    return out


def _header_index(header: list[str]) -> dict:
    """Map our canonical keys to column positions by keyword matching."""
    keys = {
        "date": ["日付"], "venue": ["開催"], "weather": ["天気"],
        "race": ["レース名"], "field": ["頭数"], "draw": ["枠番"],
        "horse_no": ["馬番"], "odds": ["オッズ"], "pop": ["人気"],
        "finish": ["着順"], "jockey": ["騎手"], "weight_carried": ["斤量"],
        "distance": ["距離"], "going": ["馬場"], "time_index": ["ﾀｲﾑ指数", "タイム指数"],
        "passing": ["通過"], "last3f": ["上り", "上がり"], "body_weight": ["馬体重"],
        "margin": ["着差"], "prize": ["賞金"],
    }
    out: dict[str, int] = {}
    for i, h in enumerate(header):
        for key, needles in keys.items():
            if key in out:
                continue
            # 上り (final-3F seconds) must not match 上がり指数 (a speed index column)
            if key == "last3f" and "指数" in h:
                continue
            if key == "time_index" and h.strip() not in ("ﾀｲﾑ指数", "タイム指数") and "指数" not in h:
                continue
            if any(n in h for n in needles):
                out[key] = i
    return out
