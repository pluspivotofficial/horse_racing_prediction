import "./globals.css";

export const metadata = {
  title: "TURF ORACLE — 週末競馬AI予想",
  description:
    "過去戦績・騎手相性・コース/馬場/天候適性を多角分析し、週末JRAの勝ち馬と推奨馬券をAIが提案するプラットフォーム。",
};

export const viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
