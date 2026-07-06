"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { money } from "@/lib/format";

/* 擬似体験ウォレット — persistent play-money betting.
   Balance and bet history live in localStorage; bets settle against the real
   dividends embedded in the race data. */

const Ctx = createContext(null);
export const useWallet = () => useContext(Ctx);

const KEY = "turf_wallet_v2";
const DEF = { balance: 100000, start: 100000, bets: [] };
const rid = () => "b" + Date.now() + Math.random().toString(36).slice(2, 6);

export function WalletProvider({ children }) {
  const [w, setW] = useState(DEF);
  const [slip, setSlip] = useState(null);     // {rp,h,type,amt}
  const [reveal, setReveal] = useState(null); // {phase,bets,stake,ret,settled,winName}
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState(false);
  const [coins, setCoins] = useState(0);

  useEffect(() => {
    try { const j = JSON.parse(localStorage.getItem(KEY)); if (j) setW(j); } catch {}
  }, []);
  const persist = (nw) => { setW(nw); try { localStorage.setItem(KEY, JSON.stringify(nw)); } catch {} };
  const flash = (m) => { setToast(m); clearTimeout(window._twt); window._twt = setTimeout(() => setToast(""), 2600); };

  const openSlip = (rp, h) => setSlip({ rp, h, type: "単勝", amt: 500 });

  const place = () => {
    const { rp, h, type, amt } = slip, r = rp.race;
    if (amt <= 0 || amt > w.balance) { flash("金額を確認してください"); return; }
    const bet = { id: rid(), raceId: r.race_id, raceName: `${r.venue}${r.race_no}R ${r.name || ""}`,
      payKey: type, label: `${type} ${h.horse_no} ${h.horse_name}`, combos: [[h.horse_no]],
      stake: amt, odds: h.odds || null, status: "pending", payout: 0 };
    persist({ ...w, balance: w.balance - amt, bets: [...w.bets, bet] });
    setSlip(null); flash(`${money(amt)}を「${type}・${h.horse_name}」に投票`);
  };

  const aiBuyAll = (rp) => {
    let bal = w.balance; const add = []; let cost = 0;
    (rp.bets || []).forEach((b) => {
      const stake = Math.round(b.stake_units * 100);
      if (stake <= 0 || stake > bal) return;
      bal -= stake; cost += stake;
      add.push({ id: rid(), raceId: rp.race.race_id, raceName: `${rp.race.venue}${rp.race.race_no}R ${rp.race.name || ""}`,
        payKey: b.pay_key, label: `${b.bet_type} ${b.selection}`, combos: b.combos || [], stake, odds: null, status: "pending", payout: 0 });
    });
    if (!add.length) { flash("購入できる推奨がありません"); return; }
    persist({ ...w, balance: bal, bets: [...w.bets, ...add] });
    flash(`AI推奨${add.length}点（${money(cost)}）を購入`);
  };

  const settle = (rp) => {
    const payouts = rp.race.payouts || {};
    const pend = w.bets.filter((b) => b.raceId === rp.race.race_id && b.status === "pending");
    if (!pend.length) { flash("このレースの馬券がありません"); return; }
    if (!Object.keys(rp.race.result || {}).length) { flash("発走前です（結果確定後に精算）"); return; }
    const settled = w.bets.map((b) => {
      if (b.raceId !== rp.race.race_id || b.status !== "pending") return b;
      const tbl = {}; (payouts[b.payKey] || []).forEach((row) => { tbl[[...row.combo].sort((x, y) => x - y).join("-")] = row.yen; });
      const combos = b.combos && b.combos.length ? b.combos : [[]];
      const per = b.stake / combos.length; let ret = 0;
      combos.forEach((c) => { const k = [...c].sort((x, y) => x - y).join("-"); if (tbl[k]) ret += (tbl[k] / 100) * per; });
      return { ...b, status: ret > 0 ? "won" : "lost", payout: Math.round(ret) };
    });
    const just = settled.filter((b) => pend.some((p) => p.id === b.id));
    const stake = pend.reduce((a, b) => a + b.stake, 0);
    const ret = just.reduce((a, b) => a + b.payout, 0);
    const winId = Object.keys(rp.race.result).find((h) => rp.race.result[h] === 1);
    const winName = (rp.horses.find((h) => h.horse_id === winId) || {}).horse_name || "";
    setReveal({ phase: "running", bets: just, stake, ret, settled, winName });
    setTimeout(() => setReveal((r) => (r ? { ...r, phase: "result" } : r)), 1350);
  };

  const claim = () => {
    if (!reveal) return;
    persist({ ...w, balance: w.balance + reveal.ret, bets: reveal.settled });
    if (reveal.ret > 0) { setCoins((c) => c + 1); setTimeout(() => setCoins((c) => Math.max(0, c - 1)), 3200); }
    setReveal(null);
  };

  const reset = () => { persist(DEF); setModal(false); flash("ウォレットをリセットしました"); };
  const betsFor = (raceId) => w.bets.filter((b) => b.raceId === raceId);

  return (
    <Ctx.Provider value={{ w, openSlip, aiBuyAll, settle, betsFor, setModal }}>
      {children}
      {slip && <BetSlip slip={slip} setSlip={setSlip} balance={w.balance} onPlace={place} />}
      {reveal && <Reveal reveal={reveal} onClaim={claim} />}
      {modal && <WalletModal w={w} onClose={() => setModal(false)} onReset={reset} />}
      {toast && <div className="toast on">{toast}</div>}
      {coins > 0 && <Coins />}
    </Ctx.Provider>
  );
}

export function WalletChip() {
  const { w, setModal } = useWallet();
  const pl = w.balance - w.start;
  return (
    <div className="wallet-chip" onClick={() => setModal(true)} title="マイウォレット">
      <span className="coin">🪙</span>
      <span className="bal">{money(w.balance)}</span>
      <span className={`dl ${pl >= 0 ? "up" : "down"}`}>{pl >= 0 ? "+" : "−"}{money(Math.abs(pl))}</span>
    </div>
  );
}

export function BetButton({ rp, h }) {
  const { openSlip } = useWallet();
  return <button className="betbtn" onClick={(e) => { e.stopPropagation(); openSlip(rp, h); }}>賭ける</button>;
}

export function BetTray({ rp }) {
  const { w, aiBuyAll, settle, betsFor } = useWallet();
  const r = rp.race;
  const mine = betsFor(r.race_id);
  const pend = mine.filter((b) => b.status === "pending");
  const hasRes = Object.keys(r.result || {}).length > 0;
  const aiCost = (rp.bets || []).reduce((a, b) => a + Math.round(b.stake_units * 100), 0);
  return (
    <div className="tray">
      {mine.length ? mine.map((b) => {
        const st = b.status === "pending" ? "発走待ち" : b.status === "won" ? "払戻 " + money(b.payout) : "はずれ";
        const cls = b.status === "won" ? "won" : b.status === "lost" ? "lost" : "pend";
        return (
          <div className="mybet" key={b.id}>
            <span>{b.label}<span style={{ color: "var(--muted)" }}> ・ {money(b.stake)}</span></span>
            <span className={`r ${cls}`}>{st}</span>
          </div>
        );
      }) : (
        <div className="empty">まだ投票していません。各馬の<b style={{ color: "var(--gold)" }}>「賭ける」</b>ボタン、または下のAI推奨から購入できます。</div>
      )}
      <div className="acts">
        {rp.bets && rp.bets.length > 0 &&
          <button className="betbtn ai-buy" onClick={() => aiBuyAll(rp)}>🤖 AI推奨を全部買う（{money(aiCost)}）</button>}
        {pend.length > 0 && hasRes &&
          <button className="reveal-btn" onClick={() => settle(rp)}>▶ レースを見て精算する（{pend.length}点）</button>}
        {pend.length > 0 && !hasRes &&
          <span style={{ color: "var(--muted)", fontSize: 12 }}>発走前 — 結果確定後に精算できます</span>}
      </div>
    </div>
  );
}

function BetSlip({ slip, setSlip, balance, onPlace }) {
  const { h, rp, type, amt } = slip, r = rp.race;
  const over = amt > balance;
  const pot = type === "単勝" && h.odds
    ? <>的中で <b>{money(amt * h.odds)}</b>（×{h.odds.toFixed(1)}）</>
    : "的中で払戻（配当は結果で確定）";
  const chip = (v) => setSlip({ ...slip, amt: v === "clear" ? 0 : (amt || 0) + v });
  return (
    <>
      <div className="backdrop on" onClick={() => setSlip(null)} />
      <div className="betslip open">
        <button className="bs-close" onClick={() => setSlip(null)}>✕</button>
        <h4>{h.confidence || ""} {h.horse_name}</h4>
        <div className="sub">{r.venue}{r.race_no}R {r.name || ""} ・ {h.horse_no}番 ／ 残高 {money(balance)}</div>
        <div className="bs-toggle">
          <button className={type === "単勝" ? "on" : ""} onClick={() => setSlip({ ...slip, type: "単勝" })}>単勝（1着）</button>
          <button className={type === "複勝" ? "on" : ""} onClick={() => setSlip({ ...slip, type: "複勝" })}>複勝（3着内）</button>
        </div>
        <div className="bs-amt"><span className="lab">賭け金</span><span className="a">{money(amt)}</span></div>
        <div className="bs-chips">
          {[100, 500, 1000, 3000, 5000].map((v) => <button key={v} onClick={() => chip(v)}>+{v.toLocaleString()}</button>)}
          <button style={{ color: "var(--coral)" }} onClick={() => chip("clear")}>クリア</button>
        </div>
        <div className="bs-pot">{pot}</div>
        <button className="bs-go" disabled={amt <= 0 || over} onClick={onPlace}>
          {over ? "残高が足りません" : `${money(amt)}を賭ける`}
        </button>
      </div>
    </>
  );
}

function Reveal({ reveal, onClaim }) {
  const { phase, bets, stake, ret, winName } = reveal;
  const win = ret > 0, net = ret - stake;
  return (
    <div className="reveal on">
      {phase === "running" ? (
        <div className="card"><div className="run">🐎</div>
          <div style={{ color: "var(--ink2)", letterSpacing: ".24em", marginTop: 14, fontSize: 13 }}>レース中…</div></div>
      ) : (
        <div className="card">
          <div style={{ fontSize: 44 }}>{win ? "🎉" : "🥕"}</div>
          <div style={{ fontSize: 12, color: "var(--muted)", letterSpacing: ".16em", margin: "10px 0 2px" }}>1着 {winName}</div>
          <div className={`amt ${win ? "win" : "lose"}`}>{win ? "+" : ""}{money(ret)}</div>
          <div style={{ fontSize: 13, color: "var(--ink2)", marginTop: 8 }}>
            投資 {money(stake)} → 払戻 {money(ret)}（収支 {net >= 0 ? "+" : "−"}{money(Math.abs(net))}）
          </div>
          <div className="detail">
            {bets.map((b) => (
              <div key={b.id}>{b.status === "won" ? "✅" : "✗"} {b.label} … <b style={{ color: b.status === "won" ? "var(--turf)" : "var(--muted)" }}>{b.payout ? money(b.payout) : "0"}</b></div>
            ))}
          </div>
          <div><button className="rvgo" onClick={onClaim}>受け取る（残高に反映）</button></div>
        </div>
      )}
    </div>
  );
}

function WalletModal({ w, onClose, onReset }) {
  const pl = w.balance - w.start;
  const hist = [...w.bets].reverse().slice(0, 40);
  return (
    <div className="wmodal on" onClick={(e) => { if (e.target.classList.contains("wmodal")) onClose(); }}>
      <div className="wmbox">
        <h4>🪙 マイウォレット</h4>
        <div className="big">{money(w.balance)}</div>
        <div className={`pl ${pl >= 0 ? "up" : "down"}`}>通算収支 {pl >= 0 ? "+" : "−"}{money(Math.abs(pl))} ／ 元手 {money(w.start)}</div>
        <div className="hist">
          <div style={{ fontSize: 11, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 8 }}>投票履歴</div>
          {hist.length ? hist.map((b) => {
            const col = b.status === "won" ? "var(--turf)" : b.status === "lost" ? "var(--muted)" : "var(--gold-dim)";
            const st = b.status === "pending" ? "—" : b.status === "won" ? "+" + money(b.payout) : "0";
            return (
              <div className="hrow" key={b.id}>
                <span>{b.raceName}<br /><span style={{ color: "var(--muted)" }}>{b.label} ・ {money(b.stake)}</span></span>
                <span className="v" style={{ color: col }}>{st}</span>
              </div>
            );
          }) : <div style={{ color: "var(--muted)", fontSize: 13 }}>まだ履歴がありません</div>}
        </div>
        <div className="wmbtns">
          <button onClick={onClose}>閉じる</button>
          <button className="reset" onClick={() => { if (confirm("残高と履歴をリセットして¥100,000に戻しますか？")) onReset(); }}>残高をリセット</button>
        </div>
      </div>
    </div>
  );
}

function Coins() {
  const coins = Array.from({ length: 16 }, (_, i) => i);
  return coins.map((i) => (
    <div key={i} className="coinfx" style={{ left: `${(i * 6.1) % 100}vw`, animationDuration: `${1.6 + (i % 5) * 0.3}s` }}>🪙</div>
  ));
}
