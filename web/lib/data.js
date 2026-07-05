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

// Backtest / headline stats computed from any race that already has results.
export function computeStats(data) {
  let scored = 0, winHit = 0, plcHit = 0, roi = 0, roiN = 0, bestVal = null;
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
      if (h.value != null && (!bestVal || h.value > bestVal.value))
        bestVal = { ...h, race: rp.race };
    }
  }
  return {
    n: data.races.length,
    scored, winHit, plcHit, bestVal,
    roi: roiN ? Math.round((roi / roiN) * 100) : null,
    winPct: scored ? Math.round((winHit / scored) * 100) : null,
    plcPct: scored ? Math.round((plcHit / scored) * 100) : null,
  };
}
