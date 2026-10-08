export type Kind = "faith" | "interview" | "body";

export interface PlanItem {
  id: number;
  track: string;
  kind: Kind;
  title: string;
  detail: string;
  minutes: number;
  counts_for_streak: boolean;
  done: boolean;
  done_at: string | null;
  skipped: boolean;
  bonus: boolean;
  status?: "done" | "scheduled" | "no_room" | "skipped";
  start?: string | null;
  end?: string | null;
  scheduled_minutes?: number | null;
  optional?: boolean;
}

export interface BusyTime {
  id: number | null;
  start: string;
  end: string;
  label: string;
  source: "work" | "you" | "calendar";
  free?: boolean;
}

export interface DayInfo {
  light: boolean;
  auto_light: boolean;
  energy: "low" | "ok" | "high" | null;
  busy: BusyTime[];
  calendar_errors: string[];
  ends_at: string | null;
}

export interface InterviewInfo {
  id: number;
  company: string;
  role: string;
  on: string;
  days_left: number;
  notes: string;
}

export type DayStatus = "done" | "missed" | "today" | "future";

export interface Streak {
  current: number;
  today_complete: boolean;
  cycle_number: number;
  cycle_day: number;
  cycle_length: number;
  cycle: { date: string; status: DayStatus }[];
}

export type PrayerName = "fajr" | "sunrise" | "dhuhr" | "asr" | "maghrib" | "isha";

export interface Prayers {
  method: string;
  asr_method: string;
  times: { name: PrayerName; at: string }[];
  next: { name: PrayerName; at: string };
  tomorrow_fajr: string;
}

export interface Today {
  date: string;
  now: string;
  timezone: string | null;
  plan: PlanItem[];
  streak: Streak;
  prayers: Prayers | null;
  needs_setup: boolean;
  day: DayInfo;
  interviews: InterviewInfo[];
  resolves_due: { id: number; title: string }[];
}

export type HeatStatus = "before" | "done" | "missed" | "today" | "future";

export interface WeekDay {
  date: string;
  weekday: "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";
  status: HeatStatus;
  blocks: { title: string; detail: string; kind: Kind; minutes: number; done: boolean }[];
}

export interface Week {
  week_of: string;
  today: string;
  days: WeekDay[];
}

export interface Habit {
  track: string;
  name: string;
  kind: Kind;
  reps: number;
  this_week: number;
  per_week: number;
  target: number;
}

export interface Progress {
  started_on: string;
  today: string;
  current: number;
  best: number;
  days_done: number;
  days_since_start: number;
  weeks: { date: string; status: HeatStatus }[][];
  habits: Habit[];
}

export type ThemeMode = "auto" | "light" | "dark" | "system";
export type TextSize = "normal" | "large" | "larger";

export interface Settings {
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
  calc_method: string;
  asr_method: string;
  started_on: string | null;
  has_location: boolean;
  theme: ThemeMode;
  text_size: TextSize;
  reduced_motion: boolean;
  work_start: string;
  work_end: string;
  work_days: string;
  office_days: string;
  commute_minutes: number;
  prayer_buffer_minutes: number;
  study_cutoff_after_isha: number;
  calendar_urls: string;
  phone_access: boolean;
  phone_key: string | null;
  windows_lockscreen: boolean;
  notifications: boolean;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Myelin returned ${res.status} for ${path}`);
  }
  return res.json() as Promise<T>;
}

export interface FocusSession {
  id: number;
  label: string;
  plan_item_id: number | null;
  started_at: string;
  ends_at: string;
  planned_minutes: number;
  ended_at: string | null;
  completed: boolean;
  minutes?: number;
}

export interface FocusState {
  active: FocusSession | null;
  today_minutes: number;
  sessions: (FocusSession & { minutes: number })[];
}

export interface Note {
  id: number;
  text: string;
  created_at: string;
  done: boolean;
  done_at: string | null;
}

export type Outcome = "solved" | "hint" | "stuck";
export type Track = "python" | "sql";
export type Difficulty = "easy" | "medium" | "hard";

export interface Problem {
  id: number;
  title: string;
  url: string;
  track: Track;
  difficulty: Difficulty;
  pattern: string;
  created_on: string;
  stage: number;
  due_on: string | null;
  is_due: boolean;
  mastered: boolean;
  attempts: number;
  last_outcome: Outcome | null;
  last_minutes: number | null;
}

export interface PatternStat {
  track: Track;
  pattern: string;
  problems: number;
  attempts: number;
  solve_rate: number | null;
  avg_minutes: number | null;
}

export interface Problems {
  problems: Problem[];
  due: Problem[];
  stats: {
    patterns: PatternStat[];
    next: Record<Track, { pattern: string; why: string } | null>;
  };
  pattern_names: Record<Track, string[]>;
  ladder_days: number[];
}

export interface ProblemIn {
  title?: string;
  url?: string;
  track: Track;
  difficulty: Difficulty;
  pattern: string;
  outcome: Outcome;
  minutes: number;
  note?: string;
}

export interface SqlTable {
  name: string;
  columns: { name: string; type: string }[];
  rows: number;
}

export interface SqlDatabase {
  id: string;
  description: string;
  tables: SqlTable[];
}

export interface SqlQuestion {
  id: string;
  db: string;
  title: string;
  difficulty: Difficulty;
  pattern: string;
  prompt: string;
  ordered: boolean;
  solved: boolean;
}

export interface SqlResult {
  columns: string[];
  rows: (string | number | null)[][];
  truncated: boolean;
  ms: number;
}

export interface AppInfo {
  version: string;
  desktop: boolean;
  windows: boolean;
  autostart: boolean | null;
  hotkey: string | null;
}

export interface LockScreenStatus {
  windows: { available: boolean; enabled: boolean; last_set: string | null; error: string | null };
  phone: { enabled: boolean; url: string | null; listening_on_network: boolean };
}

export const api = {
  today: () => call<Today>("/api/today"),
  week: () => call<Week>("/api/week"),
  progress: () => call<Progress>("/api/progress"),
  toggle: (id: number) => call<PlanItem>(`/api/plan/${id}/toggle`, { method: "POST" }),
  focus: () => call<FocusState>("/api/focus"),
  startFocus: (body: { plan_item_id?: number; label?: string; minutes: number }) =>
    call<FocusSession>("/api/focus/start", { method: "POST", body: JSON.stringify(body) }),
  stopFocus: (mark_done = false) =>
    call<FocusSession>("/api/focus/stop", { method: "POST", body: JSON.stringify({ mark_done }) }),
  notes: () => call<{ open: Note[]; cleared: Note[] }>("/api/notes"),
  addNote: (text: string) => call<Note>("/api/notes", { method: "POST", body: JSON.stringify({ text }) }),
  editNote: (id: number, patch: { done?: boolean; text?: string }) =>
    call<Note>(`/api/notes/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteNote: (id: number) => call<{ ok: boolean }>(`/api/notes/${id}`, { method: "DELETE" }),
  problems: () => call<Problems>("/api/problems"),
  logProblem: (body: ProblemIn) =>
    call<Problem & { was_new: boolean }>("/api/problems", { method: "POST", body: JSON.stringify(body) }),
  attempt: (id: number, outcome: Outcome, minutes = 0) =>
    call<Problem>(`/api/problems/${id}/attempts`, { method: "POST", body: JSON.stringify({ outcome, minutes }) }),
  deleteProblem: (id: number) => call<{ ok: boolean }>(`/api/problems/${id}`, { method: "DELETE" }),
  sqlDatabases: () => call<SqlDatabase[]>("/api/sql/databases"),
  sqlQuestions: () => call<SqlQuestion[]>("/api/sql/questions"),
  sqlRun: (db: string, query: string) =>
    call<SqlResult>("/api/sql/run", { method: "POST", body: JSON.stringify({ db, query }) }),
  sqlCheck: (question_id: string, query: string) =>
    call<{ correct: boolean; message: string; result: SqlResult }>("/api/sql/check", {
      method: "POST",
      body: JSON.stringify({ question_id, query }),
    }),
  sqlSolution: (id: string) => call<{ solution: string }>(`/api/sql/questions/${id}/solution`),
  command: (text: string) =>
    call<{ ok: boolean; kind: string; message: string }>("/api/command", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  skip: (id: number) => call<PlanItem>(`/api/plan/${id}/skip`, { method: "POST" }),
  setDay: (patch: { light?: boolean; energy?: "low" | "ok" | "high" }) =>
    call<{ light: boolean; energy: string | null }>("/api/day", { method: "POST", body: JSON.stringify(patch) }),
  removeBusy: (id: number) => call<{ ok: boolean }>(`/api/busy/${id}`, { method: "DELETE" }),
  interviews: () => call<InterviewInfo[]>("/api/interviews"),
  addInterview: (body: { company: string; role?: string; on: string }) =>
    call<InterviewInfo>("/api/interviews", { method: "POST", body: JSON.stringify(body) }),
  deleteInterview: (id: number) => call<{ ok: boolean }>(`/api/interviews/${id}`, { method: "DELETE" }),
  appInfo: () => call<AppInfo>("/api/app"),
  setAutostart: (enabled: boolean) =>
    call<{ autostart: boolean }>("/api/app/autostart", { method: "PUT", body: JSON.stringify({ enabled }) }),
  lockscreen: () => call<LockScreenStatus>("/api/lockscreen"),
  refreshWindowsLock: () => call<{ ok: boolean }>("/api/lockscreen/windows/refresh", { method: "POST" }),
  newPhoneKey: () => call<Settings>("/api/settings/phone-key", { method: "POST" }),
  settings: () => call<Settings>("/api/settings"),
  saveSettings: (patch: Partial<Settings>) =>
    call<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(patch) }),
};
