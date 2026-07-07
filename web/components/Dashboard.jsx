"use client";
import { useMemo, useState } from "react";
import { FACTOR_LABELS, FACTOR_ORDER } from "@/lib/factors";
import HorseRow from "./HorseRow";
import Bets from "./Bets";
import Simulation from "./Simulation";
import { WalletProvider, WalletChip, BetTray } from "./Wallet";

export default function Dashboard({ data, stats }) {
  const [venue, setVenue] = useState("ALL");
  const [raceIdx, setRaceIdx] = useState(0);
  const [dark, setDark] = useState(true);

  const races = data.races || [];
  const filtered = useMemo(
    () => races.filter((r) => venue === "ALL" || r.race.venue === venue),
    [races, venue]
  );
  const current = races[raceIdx];

  function pickVenue(v) {
    setVenue(v);
    const list = races.filter((r) => v === "ALL" || r.race.venue === v);
    setRaceIdx(list.length ? races.indexOf(list[0]) : 0);
  }

  const d = data.generated_for || [];
  const weekLabel = d.length ? `対象 ${d[0]}〜${d[d.length - 1]}` : "今週末を予想";

  return (
    <WalletProvider>
    <div data-theme={dark ? "" : "light"}>
      <div className="topbar">
        <div className="wrap">
          <div className="brand">
            <span className="logo">🐎</span>
            <span>TURF ORACLE<small>WEEKEND RACING AI</small></span>
          </div>
          <span className="spacer" />
          <span className="week-badge" dangerouslySetInnerHTML={{ __html: weekLabel.replace(/(\d{8}〜\d{8}|\d{4}.*)/, "<b>$1</b>") }} />
          <WalletChip />
          <button className="theme-btn" onClick={() => setDark((v) => !v)} title="テーマ切替">◐</button>
        </div>
      </div>

      <div className="wrap">
        <section className="hero">
          <h1>今週末の勝ち馬を、<span className="grad">データで撃ち抜く。</span></h1>
          <p>過去戦績・騎手相性・コース適性・馬場・天候まで、13のファクターをAIが多角的に分析。「なぜ買えるのか」を毎レース言語化してお届けします。</p>
          <StatGrid stats={stats} venues={data.venues} />
        </section>

        <Simulation sim={data.simulation} />

        <div className="filters">
          {["ALL", ...(data.venues || [])].map((v) => (
            <div key={v} className={`chip ${venue === v ? "on" : ""}`} onClick={() => pickVenue(v)}>
              {v === "ALL" ? "すべての開催" : v + "競馬場"}
            </div>
          ))}
        </div>

        <div className="section-t">レースを選ぶ</div>
        <div className="racebar">
          {filtered.map((rp) => {
            const i = races.indexOf(rp);
            const r = rp.race, top = rp.horses[0], res = r.result || {};
            let hit = "🕒";
            if (Object.keys(res).length && top) {
              const f = res[top.horse_id];
              hit = f === 1 ? "🎯" : f && f <= 3 ? "✅" : "—";
            }
            const grade = r.grade && r.grade !== "OP"
              ? <span className="gtag">{r.grade}</span>
              : r.grade === "OP" ? <span className="gtag" style={{ background: "var(--slate)" }}>OP</span> : null;
            return (
              <div key={i} className={`racecard ${raceIdx === i ? "on" : ""}`} onClick={() => setRaceIdx(i)}>
                {grade || (hit && <span className="hitdot">{hit}</span>)}
                <div className="vn">{r.venue} {r.race_no}R</div>
                <div className="nm">{r.name || "—"}</div>
                <div className="cd">{r.surface}{r.distance}m {r.off_time}</div>
                <div className="pick">{top ? `${top.confidence} ${top.horse_name.slice(0, 8)}` : ""}</div>
              </div>
            );
          })}
        </div>

        {current && <RacePanel rp={current} />}

        <div className="foot">
          データ提供: netkeiba (実データ) ・ 予想はAIによる参考情報です。馬券は自己責任で。<br />
          <b>月〜金でその週末の出走レースを分析</b>し、確定オッズ・馬場・天候で自動更新されます。
        </div>
      </div>
    </div>
    </WalletProvider>
  );
}

function StatGrid({ stats, venues }) {
  const cards = [];
  cards.push([stats.scored ? "分析レース数" : "予想レース数", stats.n, (venues || []).join(" / "), "turf"]);
  if (stats.scored) {
    cards.push(["◎の複勝的中率", stats.plcPct + "%", `本命が3着内 ${stats.plcHit}/${stats.scored}R`, "gold"]);
    cards.push(["◎の単勝的中率", stats.winPct + "%", `本命が勝利 ${stats.winHit}/${stats.scored}R`, "sky"]);
  } else {
    if (stats.marquee) {
      const m = stats.marquee.race;
      cards.push(["今週の注目", (m.name || "").slice(0, 7), `${m.venue}${m.race_no}R ${m.grade || ""} ${m.surface || ""}${m.distance || ""}m`, "gold"]);
    }
    if (stats.topPick) {
      cards.push(["最有力の本命", stats.topPick.horse_name.slice(0, 7), `${stats.topPick.race.venue}${stats.topPick.race.race_no}R・勝率${Math.round(stats.topPick.win_prob * 100)}%`, "sky"]);
    }
  }
  if (stats.bestVal && stats.bestVal.value > 0) {
    const b = stats.bestVal;
    cards.push(["今週の妙味No.1", b.horse_name.slice(0, 7),
      `${b.race.venue}${b.race.race_no}R・EV${(b.win_prob * b.odds).toFixed(2)}`, "gold"]);
  } else {
    cards.push([stats.scored ? "推奨馬券" : "ファクター数", stats.scored ? "自動生成" : "13", stats.scored ? "単複〜3連複まで" : "多角的にスコアリング", "turf"]);
  }
  return (
    <div className="statgrid">
      {cards.slice(0, 4).map((c, i) => (
        <div key={i} className={`stat ${c[3]}`}>
          <div className="k">{c[0]}</div><div className="v">{c[1]}</div><div className="s">{c[2]}</div>
        </div>
      ))}
    </div>
  );
}

function RacePanel({ rp }) {
  const r = rp.race;
  const conds = [
    r.surface && <span key="s" className="pill turf">{r.surface}{r.distance}m{r.direction}</span>,
    r.weather && <span key="w" className="pill sky">天候 {r.weather}</span>,
    r.going && <span key="g" className="pill">馬場 {r.going}</span>,
    r.grade && <span key="gr" className="pill gold">{r.grade}</span>,
    r.off_time && <span key="t" className="pill">発走 {r.off_time}</span>,
  ].filter(Boolean);

  return (
    <div className="panel">
      <div className="rhead">
        <h2>{r.venue} {r.race_no}R {r.name}</h2>
        <div className="cond">{conds}</div>
      </div>
      <div className="banner">
        <div className="b verdict">
          <div className="lab">AI総合ジャッジ ・ {rp.confidence_level}</div>{rp.race_comment}
        </div>
        <div className="b pace">
          <div className="lab">🐎 展開ラボ ・ ペース想定</div>{rp.pace_scenario || "展開分析データ不足"}
        </div>
      </div>

      <div className="section-t" style={{ margin: "18px 0 8px" }}>予想オーダー（クリックで根拠を展開）</div>
      {rp.horses.map((h, i) => (
        <HorseRow key={h.horse_id} h={h} race={r} rp={rp} idx={i} defaultOpen={i === 0}
          factorLabels={FACTOR_LABELS} factorOrder={FACTOR_ORDER} />
      ))}

      <div className="section-t" style={{ margin: "22px 0 10px" }}>🎫 あなたの馬券（擬似体験）</div>
      <BetTray rp={rp} />

      <Bets bets={rp.bets} />

      {rp.data_warnings && rp.data_warnings.length > 0 && (
        <div className="warns">
          <div className="h">⚠ データの注意点（足りないもの）</div>
          <ul>{rp.data_warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}

      <div className="legend">
        <span><span className="dot" style={{ background: "var(--gold)" }} />◎本命</span>
        <span><span className="dot" style={{ background: "var(--turf)" }} />◯対抗</span>
        <span><span className="dot" style={{ background: "var(--sky)" }} />▲単穴</span>
        <span><span className="dot" style={{ background: "var(--violet)" }} />☆連下</span>
        <span>🎯=◎的中(勝) ✅=◎3着内</span>
      </div>
    </div>
  );
}
