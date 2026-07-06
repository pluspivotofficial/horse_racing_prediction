// Shared formatting helpers.
export const money = (n) => (n < 0 ? "−" : "") + "¥" + Math.abs(Math.round(n)).toLocaleString();
