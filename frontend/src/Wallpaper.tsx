import { useCallback, useEffect, useState } from "react";
import { api, type Settings as SettingsT, type ThemeMode, type Today } from "./api";
import { FocusBadge, useFocus } from "./Focus";
import { ProgressView } from "./Progress";
import { Settings, type SaveSettings } from "./Settings";
import { clockParts, formatDate, hijriDate, isNight } from "./time";
import { InterviewCountdown, NextPrayer, TodayView } from "./Today";
import { ToolsView } from "./Tools";
import { WeekView } from "./Week";

const TABS = [
  { id: "today", label: "Today" },
  { id: "week", label: "Week" },
  { id: "progress", label: "Progress" },
  { id: "tools", label: "Tools" },
  { id: "settings", label: "Settings" },
] as const;
type Tab = (typeof TABS)[number]["id"];

// Other tabs drift back to Today after this long without a click or keypress, so the wallpaper stays simple.
const IDLE_RETURN_MS = 3 * 60_000;

function initialTab(): Tab {
  if (window.location.pathname.replace(/\/+$/, "") === "/settings") return "settings";
  const hash = window.location.hash.slice(1).split("/")[0];
  return TABS.some((t) => t.id === hash) ? (hash as Tab) : "today";
}

function useTab(): [Tab, (t: Tab, sub?: string) => void] {
  const [tab, setTab] = useState<Tab>(initialTab);
  const go = useCallback((t: Tab, sub?: string) => {
    window.history.replaceState(null, "", t === "today" ? "/" : `/#${t}${sub ? `/${sub}` : ""}`);
    setTab(t);
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

  // The desktop app's hotkey asks for the command box.
  useEffect(() => {
    const onFocusCommand = () => {
      go("today");
      window.setTimeout(() => document.getElementById("command-input")?.focus(), 80);
    };
    window.addEventListener("myelin:command", onFocusCommand);
    return () => window.removeEventListener("myelin:command", onFocusCommand);
  }, [go]);

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
  const [toolKey, setToolKey] = useState(0);

  const load = useCallback(async () => {
    try {
      setToday(await api.today());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const focus = useFocus(now, load);

  const saveSettings: SaveSettings = useCallback(
    async (patch) => {
      setSettings(await api.saveSettings(patch));
      load();
    },
    [load],
  );

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

  const goTools = (tool?: string) => {
    go("tools", tool);
    setToolKey((k) => k + 1); // re-mount so a link to a specific tool lands on it
  };

  const { time, period } = clockParts(now);
  const compact = tab === "tools" || tab === "settings";

  return (
    <main className={`wall${compact ? " is-compact" : ""}`}>
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
                onClick={() => (t.id === "tools" ? goTools() : go(t.id))}
              >
                {t.label}
              </button>
            ))}
            {settings && <ThemeToggle mode={settings.theme} onChange={(theme) => saveSettings({ theme })} />}
          </nav>
          <FocusBadge focus={focus} onOpen={() => goTools("focus")} />
          <NextPrayer
            now={now}
            prayers={today?.prayers ?? null}
            loaded={today !== null}
            onSetup={() => go("settings")}
          />
          <InterviewCountdown today={today} />
        </div>
      </header>

      {error && (
        <p className="notice" role="alert">
          Can't reach Myelin on this computer. Start it from the Start menu (or scripts\start.ps1), and this page will
          reconnect on its own.
        </p>
      )}

      <div id="view" className={`view view-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "today" && today && (
          <TodayView
            today={today}
            now={now}
            focus={focus}
            onChanged={load}
            goTools={goTools}
            goSettings={() => go("settings")}
          />
        )}
        {tab === "week" && <WeekView />}
        {tab === "progress" && <ProgressView />}
        {tab === "tools" && <ToolsView key={toolKey} focus={focus} plan={today?.plan ?? []} />}
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
