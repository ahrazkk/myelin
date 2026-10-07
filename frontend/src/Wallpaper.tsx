import { useCallback, useEffect, useState } from "react";
import { api, type PlanItem, type Prayers, type Streak, type Today } from "./api";
import { Axon } from "./Axon";
import { PRAYER_LABEL, clockParts, formatDate, formatTime, hijriDate, isNight, until } from "./time";

function useNow(intervalMs = 1000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function Wallpaper() {
  const now = useNow();
  const [today, setToday] = useState<Today | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setToday(await api.today());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // First run: record this computer's time zone so "today" matches the clock on the wall.
  useEffect(() => {
    (async () => {
      try {
        const s = await api.settings();
        if (!s.timezone) {
          await api.saveSettings({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
        }
      } catch {
        /* load() below reports the problem */
      }
      load();
    })();
    const poll = window.setInterval(load, 60_000);
    window.addEventListener("focus", load);
    return () => {
      window.clearInterval(poll);
      window.removeEventListener("focus", load);
    };
  }, [load]);

  // Roll over to the new day's plan at midnight without waiting for the next poll.
  const localDate = now.toLocaleDateString("en-CA");
  useEffect(() => {
    if (today && today.date !== localDate && today.timezone === Intl.DateTimeFormat().resolvedOptions().timeZone) load();
  }, [localDate, today, load]);

  const night = isNight(now, today?.prayers ?? null);
  useEffect(() => {
    const root = document.documentElement;
    if (night === null) delete root.dataset.theme;
    else root.dataset.theme = night ? "night" : "day";
  }, [night]);

  const toggle = async (item: PlanItem) => {
    setToday((t) => t && { ...t, plan: t.plan.map((p) => (p.id === item.id ? { ...p, done: !p.done } : p)) });
    try {
      await api.toggle(item.id);
    } finally {
      load();
    }
  };

  const { time, period } = clockParts(now);

  return (
    <main className="wall">
      <header className="top">
        <div className="clock">
          <p className="clock-face">
            <span className="clock-time">{time}</span>
            {period && <span className="clock-period">{period}</span>}
          </p>
          <p className="date">{formatDate(now)}</p>
          <p className="hijri">{hijriDate(now, today?.prayers ?? null)}</p>
        </div>
        <NextPrayer now={now} prayers={today?.prayers ?? null} loaded={today !== null} />
      </header>

      {error && (
        <p className="notice" role="alert">
          Can't reach Myelin on this computer. Start it with scripts\start.ps1, and this page will reconnect on its own.
        </p>
      )}

      {today && (
        <>
          <section className="pathway" aria-label="Streak">
            <Axon streak={today.streak} />
            <p className="streak-line">{streakLine(today.streak)}</p>
          </section>

          <div className="lower">
            <TodayPlan plan={today.plan} onToggle={toggle} />
            <PrayerTimes now={now} prayers={today.prayers} />
          </div>
        </>
      )}
    </main>
  );
}

function streakLine(s: Streak): string {
  if (s.today_complete) {
    return `Today's segment is wrapped. ${s.current}-day streak.`;
  }
  if (s.current === 0) {
    return "Finish today's interview hour to wrap your first segment.";
  }
  return `${s.current}-day streak. Finish today's hour to keep it growing.`;
}

function NextPrayer({ now, prayers, loaded }: { now: Date; prayers: Prayers | null; loaded: boolean }) {
  if (!prayers) {
    if (!loaded) return null;
    return (
      <div className="next-prayer">
        <a className="setup-link" href="/settings">
          Set your location to see prayer times
        </a>
      </div>
    );
  }
  const at = new Date(prayers.next.at);
  return (
    <div className="next-prayer">
      <p className="next-line">
        {PRAYER_LABEL[prayers.next.name]} in {until(now, at)}
      </p>
      <p className="next-at">at {formatTime(at)}</p>
    </div>
  );
}

function TodayPlan({ plan, onToggle }: { plan: PlanItem[]; onToggle: (i: PlanItem) => void }) {
  const next = plan.find((p) => !p.done);
  const hour = plan.filter((p) => p.counts_for_streak);
  const hourDone = hour.filter((p) => p.done).length;

  return (
    <section className="today" aria-labelledby="today-heading">
      <h2 id="today-heading">Today</h2>
      <ol className="plan">
        {plan.map((item) => (
          <li key={item.id} className={`plan-item${item.done ? " is-done" : ""}${item === next ? " is-next" : ""}`}>
            <button
              type="button"
              className="check"
              aria-pressed={item.done}
              aria-label={`${item.done ? "Mark not done" : "Mark done"}: ${item.title}`}
              onClick={() => onToggle(item)}
            >
              <svg viewBox="0 0 20 20" aria-hidden="true">
                <path d="M5 10.5l3.2 3.2L15 7" />
              </svg>
            </button>
            <div className="plan-text">
              <span className="plan-title">{item.title}</span>
              <span className="plan-detail">{item.detail}</span>
            </div>
            <span className="plan-minutes">{item.minutes} min</span>
          </li>
        ))}
      </ol>
      <p className="plan-progress">
        {hourDone === hour.length
          ? "Interview hour done."
          : `Interview hour: ${hourDone} of ${hour.length} blocks done.`}
      </p>
    </section>
  );
}

function PrayerTimes({ now, prayers }: { now: Date; prayers: Prayers | null }) {
  if (!prayers) return <section className="prayers" aria-hidden="true" />;
  return (
    <section className="prayers" aria-labelledby="prayers-heading">
      <h2 id="prayers-heading">Prayer times</h2>
      <ol className="prayer-list">
        {prayers.times.map((t) => {
          const at = new Date(t.at);
          const isNext = t.name === prayers.next.name && t.at === prayers.next.at;
          const cls = [
            "prayer",
            t.name === "sunrise" ? "is-sunrise" : "",
            at <= now && !isNext ? "is-past" : "",
            isNext ? "is-next" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <li key={t.name} className={cls}>
              <span>{PRAYER_LABEL[t.name]}</span>
              <span className="prayer-time">{formatTime(at)}</span>
            </li>
          );
        })}
      </ol>
      <p className="prayer-method">
        {prayers.method === "NORTH_AMERICA" ? "ISNA" : prayers.method.replaceAll("_", " ").toLowerCase()},{" "}
        {prayers.asr_method === "HANAFI" ? "Hanafi Asr" : "standard Asr"}.{" "}
        <a href="/settings">Change</a>
      </p>
    </section>
  );
}
