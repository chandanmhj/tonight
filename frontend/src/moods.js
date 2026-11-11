// Keys must match backend/app/moods.py. Each mood is the kind of film someone wants tonight.
// `color` floods the top of the page when chosen; `ink` is the text colour that reads on it
// (every pair is at least 4.5:1 contrast).
export const MOODS = [
  { key: "funny", color: "#F2B632", ink: "#172033" },
  { key: "emotional", color: "#3E5BA9", ink: "#FFFFFF" },
  { key: "thrilling", color: "#C93C35", ink: "#FFFFFF" },
  { key: "mind-bending", color: "#167474", ink: "#FFFFFF" },
  { key: "adventurous", color: "#2F7A40", ink: "#FFFFFF" },
  { key: "romantic", color: "#A8325F", ink: "#FFFFFF" },
];

// Movie length choices. min and max are minutes (400 = no upper limit).
export const RUNTIMES = [
  { key: "u90", label: "Under 90 min", min: 0, max: 90 },
  { key: "u120", label: "Under 2 hours", min: 0, max: 120 },
  { key: "m120_150", label: "2 to 2½ hours", min: 120, max: 150 },
  { key: "o150", label: "Over 2½ hours", min: 150, max: 400 },
  { key: "any", label: "Any length", min: 0, max: 400 },
];

export const NEUTRAL ={ color: "#172033", ink: "#FFFFFF" };

export const moodByKey = (key) => MOODS.find((m) => m.key === key) || NEUTRAL;
