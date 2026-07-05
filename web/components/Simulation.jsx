"use client";

const money = (n) => (n < 0 ? "−" : "") + "¥" + Math.abs(Math.round(n)).toLocaleString();

export default function Simulation({ sim }) {
  if (!sim || !sim.n_bets) return null;
  const up = sim.profit >= 0;
  const c = sim.equity_curve;
  const W = 820, H = 170, pad = 14;
  const ys = c.map((p) => p.bankroll).concat([sim.bankroll_start]);
  const mn = Math.min(...ys), mx = Math.max(...ys), span = (mx - mn) || 1;
  const X = (i) => pad + (i * (W - 2 * pad)) / (c.length - 1);
  const Y = (v) => H - pad - ((v - mn) / span) * (H - 2 * pad);
  const line = c.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.bankroll).toFixed(1)}`).join(" ");
  const area = `M${X(0).toFixed(1)},${(H - pad).toFixed(1)} ` +
    c.map((p, i) => `L${X(i).toFixed(1)},${Y(p.bankroll).toFixed(1)}`).join(" ") +
    ` L${X(c.length - 1).toFixed(1)},${(H - pad).toFixed(1)} Z`;
  const baseY = Y(sim.bankroll_start).toFixed(1);
  const endUp = c[c.length - 1].bankroll >= sim.bankroll_start;
  const stroke = endUp ? "var(--turf)" : "var(--coral)";

  const led = [...sim.ledger].sort((a, b) => b.profit - a.profit);
  const top2 = led.slice(0, 2).reduce((a, r) => a + r.profit, 0);
  const fuku = sim.by_type["複勝"], wide = sim.by_type["ワイド"];
  const steady = [["複勝", fuku], ["ワイド", wide]].filter(([, v]) => v)
    .map(([n, v]) => `${n}${Math.round(v.roi * 100)}%`).join("・");
  const head = `※ 対象${sim.ledger.length}レースを推奨どおり実際に購入した場合を、実際の払戻(配当)で精算した結果です`
    + `（1点=${sim.unit_yen}円・元手${money(sim.bankroll_start)}）。`;
  const body = sim.profit >= 0
    ? `ただし1週末のみで分散は大きく、利益${money(sim.profit)}のうち${money(top2)}は${led[0].race.split(" ")[0]}等・上位2レースの的中に依存します。`
      + (fuku ? `堅実志向なら複勝中心（回収率${Math.round(fuku.roi * 100)}%）が目安。` : "")
    : `今週は妙味狙いの単勝・3連複などが外れ収支は${money(sim.profit)}。一方で堅実な${steady || "複勝"}は健闘しており、券種の選び方次第で結果は大きく変わります。`;
  const note = head + body + `長期の安定した回収率評価には複数週の検証が必要です。馬券は自己責任で。`;

  const Stat = ({ k, v, cls }) => (
    <div className="simstat"><div className="k">{k}</div><div className={`v ${cls || ""}`}>{v}</div></div>
  );

  return (
    <section className="simcard">
      <div className="sh">
        <h3>💴 収支シミュレーション</h3>
        <span className="cap">推奨馬券を実配当で精算 ・ {sim.n_bets}点</span>
      </div>
      <div className="simstats">
        <Stat k="投資額" v={money(sim.staked)} />
        <Stat k="回収額" v={money(sim.returned)} cls="gold" />
        <Stat k="収支" v={(up ? "+" : "") + money(sim.profit).replace("¥", "")} cls={up ? "up" : "down"} />
        <Stat k="回収率" v={(sim.roi * 100).toFixed(0) + "%"} cls={up ? "up" : "down"} />
        <Stat k="的中率" v={(sim.hit_rate * 100).toFixed(0) + "%"} />
      </div>
      <svg className="equity" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="資金推移">
        <defs>
          <linearGradient id="eqg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={stroke} stopOpacity="0.20" />
            <stop offset="1" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1={pad} y1={baseY} x2={W - pad} y2={baseY} stroke="var(--line2)" strokeWidth="1" strokeDasharray="3 4" />
        <path d={area} fill="url(#eqg)" />
        <path d={line} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={X(c.length - 1).toFixed(1)} cy={Y(c[c.length - 1].bankroll).toFixed(1)} r="4" fill={stroke} />
      </svg>
      <div className="eqlabels">
        <span>元手 {money(sim.bankroll_start)}</span>
        <span>最大ドローダウン −{money(sim.max_drawdown)} ／ 最終 {money(sim.bankroll_end)}</span>
      </div>
      <div className="bytype">
        {Object.entries(sim.by_type).sort((a, b) => b[1].return - a[1].return).map(([name, v]) => {
          const roi = v.roi * 100, w = Math.max(3, Math.min(100, roi / 6));
          const col = roi >= 100 ? "var(--turf)" : roi >= 60 ? "var(--gold)" : "var(--coral)";
          return (
            <div className="btrow" key={name}>
              <div className="n"><span>{name.replace("フォーメーション", "F")}</span><span>的中{v.hits}/{v.bets}</span></div>
              <div className="bar"><i style={{ width: `${w}%`, background: col }} /></div>
              <div className="n"><span className="roi" style={{ color: col }}>回収率 {roi.toFixed(0)}%</span><span>{money(v.return)}</span></div>
            </div>
          );
        })}
      </div>
      <div className="simnote">{note}</div>
    </section>
  );
}
