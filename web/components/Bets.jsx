"use client";

export default function Bets({ bets }) {
  return (
    <div className="betsec">
      <div className="section-t" style={{ margin: "0 0 10px" }}>💰 推奨馬券プラン</div>
      <div className="tickets">
        {bets && bets.length ? (
          bets.map((b, i) => {
            const ev = b.expected_value;
            const cls = ev >= 2 ? "hi" : ev >= 1.1 ? "mid" : "";
            return (
              <div className={`ticket t-${b.bet_type}`} key={i}>
                <div className="tt">
                  <span className="bt">{b.bet_type}</span>
                  <span className={`ev ${cls}`}>×{ev}</span>
                </div>
                <div className="sel">{b.selection}</div>
                <div className="meta">
                  <span>推奨 {b.stake_units}u</span>
                  <span>的中 {Math.round(b.hit_prob * 100)}%</span>
                </div>
                <div className="rat">{b.rationale}</div>
              </div>
            );
          })
        ) : (
          <div style={{ color: "var(--muted)" }}>条件を満たす推奨馬券がありません</div>
        )}
      </div>
    </div>
  );
}
