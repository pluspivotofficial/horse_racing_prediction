"""Polite, cached HTTP client for netkeiba.

Design goals
------------
* **Be a good citizen.**  One request at a time, a real delay between hits,
  a descriptive User-Agent, and an on-disk cache so we never fetch the same
  page twice.  Scraping is a privilege; we treat it like one.
* **Work offline.**  Once a page is cached, the whole pipeline runs with the
  network unplugged — which makes development, testing and the shipped demo
  fully reproducible.
* **Correct encoding.**  db.netkeiba.com serves EUC-JP; race.netkeiba.com
  serves UTF-8.  We detect and normalise to unicode.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional

import requests

DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
    "(+horse-racing-prediction research project)"
)


class NetkeibaClient:
    def __init__(
        self,
        cache_dir: Path | str = DEFAULT_CACHE,
        min_interval: float = 0.8,
        timeout: int = 20,
        offline: bool = False,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.timeout = timeout
        self.offline = offline
        self._last_fetch = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": UA})

    # -- cache helpers -------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key}.html"

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_fetch
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_fetch = time.time()

    # -- main entry ----------------------------------------------------------
    def get(self, url: str, encoding: Optional[str] = None, force: bool = False) -> str:
        """Return page HTML as unicode, using cache when possible."""
        cp = self._cache_path(url)
        if cp.exists() and not force:
            return cp.read_text(encoding="utf-8", errors="ignore")

        if self.offline:
            raise RuntimeError(f"offline mode and page not cached: {url}")

        self._throttle()
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        raw = resp.content

        text = None
        encodings = [encoding] if encoding else self._encoding_candidates(url)
        for enc in encodings:
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            text = raw.decode("utf-8", errors="ignore")

        cp.write_text(text, encoding="utf-8")
        return text

    @staticmethod
    def _encoding_candidates(url: str) -> list[str]:
        if "db.netkeiba.com" in url:
            return ["euc-jp", "utf-8"]
        return ["utf-8", "euc-jp"]

    # -- semantic endpoints --------------------------------------------------
    def race_list(self, kaisai_date: str, force: bool = False) -> str:
        """AJAX race-list for one calendar date (YYYYMMDD)."""
        url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={kaisai_date}"
        return self.get(url, encoding="utf-8", force=force)

    def calendar(self, year: int, month: int, force: bool = False) -> str:
        url = f"https://race.netkeiba.com/top/calendar.html?year={year}&month={month:02d}"
        return self.get(url, encoding="utf-8", force=force)

    def shutuba(self, race_id: str, force: bool = False) -> str:
        """Upcoming entries table (pre-race)."""
        url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
        return self.get(url, encoding="utf-8", force=force)

    def race_db(self, race_id: str, force: bool = False) -> str:
        """Post-race DB page: conditions, weather, going, full result."""
        url = f"https://db.netkeiba.com/race/{race_id}/"
        return self.get(url, encoding="euc-jp", force=force)

    def horse_history(self, horse_id: str, force: bool = False) -> str:
        """Full career past-performance table."""
        url = f"https://db.netkeiba.com/horse/result/{horse_id}/"
        return self.get(url, encoding="euc-jp", force=force)

    def horse_profile(self, horse_id: str, force: bool = False) -> str:
        url = f"https://db.netkeiba.com/horse/{horse_id}/"
        return self.get(url, encoding="euc-jp", force=force)

    def pedigree(self, horse_id: str, force: bool = False) -> str:
        """3-generation blood table."""
        url = f"https://db.netkeiba.com/horse/ped/{horse_id}/"
        return self.get(url, encoding="euc-jp", force=force)

    def sire(self, sire_id: str, force: bool = False) -> str:
        """Sire's progeny statistics page."""
        url = f"https://db.netkeiba.com/horse/sire/{sire_id}/"
        return self.get(url, encoding="euc-jp", force=force)

    def oikiri(self, race_id: str, force: bool = False) -> str:
        """Pre-race final-workout (追い切り) table for a race."""
        url = f"https://race.netkeiba.com/race/oikiri.html?race_id={race_id}"
        return self.get(url, encoding="utf-8", force=force)
