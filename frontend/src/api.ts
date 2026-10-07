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

export interface Settings {
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
  calc_method: string;
  asr_method: string;
  started_on: string | null;
  has_location: boolean;
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

export const api = {
  today: () => call<Today>("/api/today"),
  week: () => call<Week>("/api/week"),
  progress: () => call<Progress>("/api/progress"),
  toggle: (id: number) => call<PlanItem>(`/api/plan/${id}/toggle`, { method: "POST" }),
  settings: () => call<Settings>("/api/settings"),
  saveSettings: (patch: Partial<Settings>) =>
    call<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(patch) }),
};
