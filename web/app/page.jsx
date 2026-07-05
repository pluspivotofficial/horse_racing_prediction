import { loadWeekend, computeStats } from "@/lib/data";
import Dashboard from "@/components/Dashboard";

// Server component: read the engine's JSON at request time and hand it to the
// interactive dashboard.  Regenerate the JSON with:
//   python scripts/predict_weekend.py --today YYYY-MM-DD
export default function Page() {
  const data = loadWeekend();
  const stats = computeStats(data);
  return <Dashboard data={data} stats={stats} />;
}
