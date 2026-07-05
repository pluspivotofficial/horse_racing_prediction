// Client-safe constants (no node: imports) — used by both server and client.
export const FACTOR_LABELS = {
  recent_form: "近走成績", class_fit: "クラス実績", distance_fit: "距離適性",
  course_fit: "コース適性", surface_fit: "馬場適性", going_fit: "馬場状態",
  weather_fit: "天候相性", jockey_fit: "騎手相性", pace_fit: "脚質決め手",
  draw_fit: "枠順", condition: "馬体調子",
};
export const FACTOR_ORDER = [
  "recent_form", "class_fit", "distance_fit", "course_fit", "jockey_fit",
  "pace_fit", "going_fit", "weather_fit", "surface_fit", "condition", "draw_fit",
];
