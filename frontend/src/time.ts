import type { PrayerName, Prayers } from "./api";

export const PRAYER_LABEL: Record<PrayerName, string> = {
  fajr: "Fajr",
  sunrise: "Sunrise",
  dhuhr: "Dhuhr",
  asr: "Asr",
  maghrib: "Maghrib",
  isha: "Isha",
};

const clockFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const dateFmt = new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long" });
const hijriFmt = new Intl.DateTimeFormat("en-u-ca-islamic-umalqura", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

/** "7:42 PM" split into the time and the day-period, so they can be set at different sizes. */
export function clockParts(d: Date): { time: string; period: string } {
  const parts = clockFmt.formatToParts(d);
  const period = parts.find((p) => p.type === "dayPeriod")?.value ?? "";
  const time = parts
    .filter((p) => p.type !== "dayPeriod")
    .map((p) => p.value)
    .join("")
    .trim();
  return { time, period };
}

export const formatTime = (d: Date) => clockFmt.format(d);
export const formatDate = (d: Date) => dateFmt.format(d);

/** The Islamic day begins at Maghrib, so after sunset show tomorrow's Hijri date. */
export function hijriDate(now: Date, prayers: Prayers | null): string {
  const maghrib = prayers?.times.find((t) => t.name === "maghrib");
  const afterMaghrib = maghrib ? now >= new Date(maghrib.at) : false;
  const d = new Date(now);
  if (afterMaghrib) d.setDate(d.getDate() + 1);
  return hijriFmt.format(d).replace(/\s*AH$/, " AH");
}

/** "1 h 18 min", "42 min", "under a minute". */
export function until(from: Date, to: Date): string {
  const mins = Math.max(0, Math.round((to.getTime() - from.getTime()) / 60000));
  if (mins < 1) return "under a minute";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} h`;
  return `${h} h ${m} min`;
}

/** Night view runs from Maghrib until sunrise. Without prayer times, follow the system theme. */
export function isNight(now: Date, prayers: Prayers | null): boolean | null {
  if (!prayers) return null;
  const at = (n: PrayerName) => new Date(prayers.times.find((t) => t.name === n)!.at);
  return now >= at("maghrib") || now < at("sunrise");
}
