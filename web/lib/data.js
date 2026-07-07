import fs from "node:fs";
import path from "node:path";

// (factor label/order constants live in ./factors.js so client components can
//  import them without pulling node:fs into the browser bundle)

// Server-side load of the prediction payload produced by the Python engine
// (scripts/predict_weekend.py writes web/public/data/weekend.json).
export function loadWeekend() {
  const p = path.join(process.cwd(), "public", "data", "weekend.json");
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8"));
  } catch {
    return { generated_for: [], venues: [], race_count: 0, races: [] };
  }
}

const GRANK = { GI: 6, GII: 5, GIII: 4, L: 3, OP: 3, "": 0 };

// Headline stats. When a race has results we show hit-rates; for an upcoming
// (pre-race) weekend we surface the marquee race and the strongest pick.
export function computeStats(data) {
  let scored = 0, winHit = 0, plcHit = 0, roi = 0, roiN = 0, bestVal = null, marquee = null, topPick = null;
  for (const rp of data.races) {
    const res = rp.race.result || {};
    const has = Object.keys(res).length > 0;
    const top = rp.horses[0];
    if (has && top) {
      scored++;
      const f = res[top.horse_id];
      if (f === 1) winHit++;
      if (f && f <= 3) plcHit++;
      if (top.odds) { roiN++; roi += f === 1 ? top.odds : 0; }
    }
    for (const h of rp.horses) {
      if (h.value != null && (!bestVal || h.value > bestVal.value)) bestVal = { ...h, race: rp.race };
    }
    const g = GRANK[rp.race.grade] || 0, mg = marquee ? (GRANK[marquee.race.grade] || 0) : -1;
    if (!marquee || g > mg || (g === mg && (rp.race.field_size || 0) > (marquee.race.field_size || 0))) marquee = rp;
    if (top && (!topPick || top.win_prob > topPick.win_prob)) topPick = { ...top, race: rp.race };
  }
  return {
    n: data.races.length,
    scored, winHit, plcHit, bestVal, marquee, topPick,
    roi: roiN ? Math.round((roi / roiN) * 100) : null,
    winPct: scored ? Math.round((winHit / scored) * 100) : null,
    plcPct: scored ? Math.round((plcHit / scored) * 100) : null,
  };
}
