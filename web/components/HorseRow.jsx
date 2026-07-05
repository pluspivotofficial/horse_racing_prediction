"use client";
import { useState } from "react";

const MARK_CLASS = ["m0", "m1", "m2", "m3", "m4"];

function wakuClass(no, field) {
  if (!no || !field) return "";
  const w = Math.min(8, Math.ceil(no / (Math.ceil(field / 8) || 1)));
  return "w" + w;
}
function factorColor(v) {
  if (v >= 60) return "var(--turf)";
  if (v >= 52) return "var(--turf-dim)";
  if (v >= 46) return "var(--slate)";
  return "var(--coral)";
}

export default function HorseRow({ h, race, idx, defaultOpen, factorLabels, factorOrder }) {
  const [open, setOpen] = useState(defaultOpen);
  const res = race.result || {};
  const fin = res[h.horse_id];
  const mk = MARK_CLASS[idx] || "mx";
  const val = h.value;
  const vtag = h.odds
    ? val > 0.05
      ? <span className="valtag pos">妙味 +{(val * 100).toFixed(0)}%</span>
      : <span className="valtag neg">妙味 {(val * 100).toFixed(0)}%</span>
    : null;

  return (
    <div className={`horse ${fin === 1 ? "win" : ""} ${open ? "open" : ""}`}>
      <div className="hmain" onClick={() => setOpen((v) => !v)}>
        <div className={`mark ${mk}`}>{h.confidence || idx + 1}</div>
        <div className={`num ${wakuClass(h.horse_no, race.field_size)}`}>{h.horse_no || "-"}</div>
        <div className="hinfo">
          <div className="nm">
            {h.horse_name}
            {fin && <span className={`fin ${fin <= 3 ? "top" : ""}`}>実{fin}着</span>}
          </div>
          <div className="jk">鞍上 <b>{h.jockey || "—"}</b> ・ 能力指数 {h.ability}</div>
          <div className="abil"><i style={{ width: `${Math.min(100, Math.max(3, (h.ability - 40) * 2.2))}%` }} /></div>
        </div>
        <div className="odds-col">
          <div className="winp">
            <div className="p">{Math.round(h.win_prob * 100)}<span style={{ fontSize: 12 }}>%</span></div>
            <div className="l">勝率</div>
          </div>
          <div className="odds">
            <div className="p">{h.odds ? h.odds.toFixed(1) : "—"}</div>
            <div className="l">単勝</div>
          </div>
          {vtag}
        </div>
      </div>

      <div className="hdetail">
        <div className="factorgrid">
          {factorOrder.filter((k) => k in h.factors).map((k) => {
            const v = h.factors[k];
            return (
              <div className="frow" key={k}>
                <span className="fl">{factorLabels[k]}</span>
                <span className="ft"><i style={{ width: `${Math.max(4, Math.min(100, v))}%`, background: factorColor(v) }} /></span>
                <span className="fv">{Math.round(v)}</span>
              </div>
            );
          })}
        </div>
        {h.comments && h.comments.length > 0 && (
          <div className="comments">
            {h.comments.map((c, i) => (
              <div className={`cmt ${c.persona}`} key={i}>
                <div className="ic">{c.icon}</div>
                <div className="bd">
                  <div className="nm">{c.name}</div>
                  <div className="tx">{c.text}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
