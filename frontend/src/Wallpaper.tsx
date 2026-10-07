import { useCallback, useEffect, useState } from "react";
import {
  api,
  type PlanItem,
  type Prayers,
  type Settings as SettingsT,
  type Streak,
  type ThemeMode,
  type Today,
} from "./api";
import { Axon } from "./Axon";
import { ProgressView } from "./Progress";
import { Settings, type SaveSettings } from "./Settings";
import { PRAYER_LABEL, clockParts, formatDate, formatTime, hijriDate, isNight, until } from "./time";
import { WeekView } from "./Week";

const TABS = [
  { id: "today", label: "Today" },
  { id: "week", label: "Week" },
  { id: "progress", label: "Progress" },
  { id: "settings", label: "Settings" },
] as const;
type Tab = (typeof TABS)[number]["id"];

// Other tabs drift back to Today after this long without a click or keypress, so the wallpaper stays simple.
const IDLE_RETURN_MS = 3 * 60_000;

function initialTab(): Tab {
  if (window.location.pathname.replace(/\/+$/, "") === "/settings") return "settings";
  const hash = window.location.hash.slice(1);
  return TABS.some((t) => t.id === hash) ? (hash as Tab) : "today";
}

function useTab(): [Tab, (t: Tab) => void] {
  const [tab, setTab] = useState<Tab>(initialTab);
  const go = useCallback((t: Tab) => {
    setTab(t);
    window.history.replaceState(null, "", t === "today" ? "/" : `/#${t}`);
  }, []);

  useEffect(() => {
    if (tab === "today") return;
    let timer = window.setTimeout(() => go("today"), IDLE_RETURN_MS);
    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => go("today"), IDLE_RETURN_MS);
    };
    const events = ["pointerdown", "keydown", "wheel"] as const;
    events.forEach((e) => window.addEventListener(e, reset));
    return () => {
      window.clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [tab, go]);

  return [tab, go];
}

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
  const [tab, go] = useTab();
  const [today, setToday] = useState<Today | null>(null);
  const [settings, setSettings] = useState<SettingsT | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setToday(await api.today());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const saveSettings: SaveSettings = useCallback(async (patch) => {
    setSettings(await api.saveSettings(patch));
  }, []);

  // First run: record this computer's time zone so "today" matches the clock on the wall.
  useEffect(() => {
    (async () => {
      try {
        let s = await api.settings();
        if (!s.timezone) {
          s = await api.saveSettings({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
        }
        setSettings(s);
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

  // Coming back to Today (say, after saving a location in Settings) shows fresh data right away.
  useEffect(() => {
    if (tab === "today") load();
  }, [tab, load]);

  const theme = resolveTheme(settings?.theme ?? "auto", isNight(now, today?.prayers ?? null));
  useEffect(() => {
    const root = document.documentElement;
    if (theme === null) delete root.dataset.theme;
    else root.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.text = settings?.text_size ?? "normal";
    if (settings?.reduced_motion) root.dataset.motion = "reduce";
    else delete root.dataset.motion;
  }, [settings?.text_size, settings?.reduced_motion]);

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
        <div className="top-right">
          <nav className="tabs" role="tablist" aria-label="Views">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls="view"
                className="tab"
                onClick={() => go(t.id)}
              >
                {t.label}
              </button>
            ))}
            {settings && (
              <ThemeToggle mode={settings.theme} onChange={(theme) => saveSettings({ theme })} />
            )}
          </nav>
          <NextPrayer
            now={now}
            prayers={today?.prayers ?? null}
            loaded={today !== null}
            onSetup={() => go("settings")}
          />
        </div>
      </header>

      {error && (
        <p className="notice" role="alert">
          Can't reach Myelin on this computer. Start it with scripts\start.ps1, and this page will reconnect on its own.
        </p>
      )}

      <div id="view" className={`view view-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "today" && today && (
          <>
            <section className="pathway" aria-label="Streak">
              <Axon streak={today.streak} />
              <p className="streak-line">{streakLine(today.streak)}</p>
            </section>

            <div className="lower">
              <TodayPlan plan={today.plan} onToggle={toggle} />
              <PrayerTimes now={now} prayers={today.prayers} onChange={() => go("settings")} />
            </div>
          </>
        )}
        {tab === "week" && <WeekView />}
        {tab === "progress" && <ProgressView />}
        {tab === "settings" && settings && <Settings settings={settings} onSave={saveSettings} />}
      </div>
    </main>
  );
}

/** The theme to apply: "day", "night", or null to follow the system. */
function resolveTheme(mode: ThemeMode, night: boolean | null): "day" | "night" | null {
  if (mode === "light") return "day";
  if (mode === "dark") return "night";
  if (mode === "system" || night === null) return null;
  return night ? "night" : "day";
}

const NEXT_THEME: Record<ThemeMode, ThemeMode> = { auto: "light", light: "dark", dark: "auto", system: "auto" };
const THEME_NAME: Record<ThemeMode, string> = {
  auto: "Auto, switches at Maghrib",
  light: "Light",
  dark: "Dark",
  system: "Follows Windows",
};

function ThemeToggle({ mode, onChange }: { mode: ThemeMode; onChange: (m: ThemeMode) => void }) {
  const next = NEXT_THEME[mode];
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => onChange(next)}
      aria-label={`Theme: ${THEME_NAME[mode]}. Switch to ${THEME_NAME[next]}`}
      title={`Theme: ${THEME_NAME[mode]}`}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        {mode === "light" && (
          <>
            <circle cx="12" cy="12" r="4.2" />
            {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
              <line key={a} x1="12" y1="2.8" x2="12" y2="5.2" transform={`rotate(${a} 12 12)`} />
            ))}
          </>
        )}
        {mode === "dark" && <path d="M15.5 3.5a8.5 8.5 0 1 0 5 13.7A7 7 0 0 1 15.5 3.5z" />}
        {(mode === "auto" || mode === "system") && (
          <>
            <circle cx="12" cy="12" r="8" />
            <path d="M12 4a8 8 0 0 1 0 16z" className="fill" />
          </>
        )}
      </svg>
    </button>
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

function NextPrayer({
  now,
  prayers,
  loaded,
  onSetup,
}: {
  now: Date;
  prayers: Prayers | null;
  loaded: boolean;
  onSetup: () => void;
}) {
  if (!prayers) {
    if (!loaded) return null;
    return (
      <div className="next-prayer">
        <button type="button" className="link-button setup-link" onClick={onSetup}>
          Set your location to see prayer times
        </button>
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

function PrayerTimes({ now, prayers, onChange }: { now: Date; prayers: Prayers | null; onChange: () => void }) {
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
        <button type="button" className="link-button" onClick={onChange}>
          Change
        </button>
      </p>
    </section>
  );
}
