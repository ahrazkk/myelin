import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, type FocusState, type PlanItem } from "./api";
import { Segmented } from "./Settings";

export interface FocusApi {
  state: FocusState | null;
  remainingMs: number | null;
  timeUp: boolean;
  start: (opts: { plan_item_id?: number; label?: string; minutes: number }) => Promise<void>;
  stop: (markDone?: boolean) => Promise<void>;
  extend: (minutes: number) => Promise<void>;
  refresh: () => Promise<void>;
}

/** A soft two-note chime, so time's up is noticed without being jarring. */
function chime() {
  try {
    const ctx = new AudioContext();
    [659.25, 880].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      const t = ctx.currentTime + i * 0.22;
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.12, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.9);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 1);
    });
  } catch {
    /* no audio available */
  }
}

export function useFocus(now: Date, onChange?: () => void): FocusApi {
  const [state, setState] = useState<FocusState | null>(null);

  const refresh = useCallback(async () => {
    try {
      setState(await api.focus());
    } catch {
      /* the wallpaper shows connection problems elsewhere */
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = window.setInterval(refresh, 20_000);
    return () => window.clearInterval(t);
  }, [refresh]);

  const active = state?.active ?? null;
  const remainingMs = active ? new Date(active.ends_at).getTime() - now.getTime() : null;
  const timeUp = remainingMs !== null && remainingMs <= 0;

  const chimedFor = useRef<number | null>(null);
  useEffect(() => {
    if (timeUp && active && chimedFor.current !== active.id) {
      chimedFor.current = active.id;
      chime();
    }
  }, [timeUp, active]);

  const start = useCallback<FocusApi["start"]>(
    async (opts) => {
      await api.startFocus(opts);
      await refresh();
    },
    [refresh],
  );

  const stop = useCallback<FocusApi["stop"]>(
    async (markDone = false) => {
      await api.stopFocus(markDone);
      await refresh();
      onChange?.();
    },
    [refresh, onChange],
  );

  const extend = useCallback<FocusApi["extend"]>(
    async (minutes) => {
      if (!active) return;
      // Keep going: close this session and open a short follow-on with the same label.
      await api.stopFocus(false);
      await api.startFocus({ plan_item_id: active.plan_item_id ?? undefined, label: active.label, minutes });
      await refresh();
    },
    [active, refresh],
  );

  return { state, remainingMs, timeUp, start, stop, extend, refresh };
}

export function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return `${h ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

/** Compact timer under the tabs, visible on every tab while a session runs. */
export function FocusBadge({ focus, onOpen }: { focus: FocusApi; onOpen: () => void }) {
  const active = focus.state?.active;
  if (!active || focus.remainingMs === null) return null;

  if (focus.timeUp) {
    return (
      <div className="focus-badge is-up" role="status">
        <p>
          Time's up: <strong>{active.label}</strong>
        </p>
        <div className="focus-badge-actions">
          {active.plan_item_id !== null && (
            <button type="button" className="btn primary" onClick={() => focus.stop(true)}>
              Mark done
            </button>
          )}
          <button type="button" className="btn" onClick={() => focus.extend(10)}>
            10 more minutes
          </button>
          <button type="button" className="btn quiet" onClick={() => focus.stop(false)}>
            Stop
          </button>
        </div>
      </div>
    );
  }

  return (
    <button type="button" className="focus-badge" onClick={onOpen} aria-label={`Focus timer: ${active.label}`}>
      <span className="focus-badge-time">{formatRemaining(focus.remainingMs)}</span>
      <span className="focus-badge-label">{active.label}</span>
    </button>
  );
}

const PRESETS: [string, string][] = [
  ["15", "15 min"],
  ["25", "25 min"],
  ["45", "45 min"],
  ["60", "60 min"],
];

export function FocusPanel({ focus, plan }: { focus: FocusApi; plan: PlanItem[] }) {
  const open = plan.filter((p) => !p.done);
  const [itemId, setItemId] = useState<string>(open[0] ? String(open[0].id) : "free");
  const [label, setLabel] = useState("");
  const chosen = open.find((p) => String(p.id) === itemId);
  const [minutes, setMinutes] = useState<string>(String(chosen?.minutes ?? 25));
  const active = focus.state?.active;

  const pick = (id: string) => {
    setItemId(id);
    const item = open.find((p) => String(p.id) === id);
    if (item) setMinutes(String(item.minutes));
  };

  const begin = (e: FormEvent) => {
    e.preventDefault();
    focus.start({
      plan_item_id: chosen?.id,
      label: chosen ? undefined : label.trim() || "Focus",
      minutes: Math.max(1, Number(minutes) || 25),
    });
  };

  const total = active ? active.planned_minutes * 60_000 : 1;
  const left = focus.remainingMs ?? 0;
  const done = active ? Math.min(1, Math.max(0, 1 - left / total)) : 0;

  return (
    <div className="tool-columns">
      <section className="focus-main" aria-label="Focus timer">
        {active ? (
          <>
            <p className="focus-label">{active.label}</p>
            <p className="focus-time">{formatRemaining(left)}</p>
            <div className="focus-sheath" aria-hidden="true">
              <span style={{ width: `${done * 100}%` }} />
            </div>
            <div className="focus-actions">
              {active.plan_item_id !== null && (
                <button type="button" className="btn primary" onClick={() => focus.stop(true)}>
                  {focus.timeUp ? "Mark done" : "Done early"}
                </button>
              )}
              {focus.timeUp && (
                <button type="button" className="btn" onClick={() => focus.extend(10)}>
                  10 more minutes
                </button>
              )}
              <button type="button" className="btn quiet" onClick={() => focus.stop(false)}>
                Stop
              </button>
            </div>
          </>
        ) : (
          <form className="focus-setup" onSubmit={begin}>
            <label className="field">
              What are you focusing on?
              <select className="input" value={itemId} onChange={(e) => pick(e.target.value)}>
                {open.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
                <option value="free">Something else</option>
              </select>
            </label>
            {!chosen && (
              <label className="field">
                Name it
                <input
                  className="input"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="Reading, Kafka course, cleaning my desk"
                />
              </label>
            )}
            <p className="field-label">How long</p>
            <Segmented label="Length" value={minutes} options={withCustom(PRESETS, minutes)} onChange={setMinutes} />
            <div className="focus-actions">
              <button type="submit" className="btn primary">
                Start focus
              </button>
            </div>
            <p className="hint">
              Phone face down, one tab open. If a stray thought shows up, park it on the right and keep going.
            </p>
          </form>
        )}
      </section>

      <div className="focus-side">
        <ParkThought />
        <section aria-labelledby="sessions-heading" className="tool-block">
          <h3 id="sessions-heading">Today</h3>
          {focus.state && focus.state.sessions.length > 0 ? (
            <>
              <p className="tool-sub">{focus.state.today_minutes} minutes of focus so far.</p>
              <ol className="session-list">
                {focus.state.sessions.map((s) => (
                  <li key={s.id}>
                    <span>{s.label}</span>
                    <span className="muted">{s.ended_at ? `${s.minutes} min` : "running"}</span>
                  </li>
                ))}
              </ol>
            </>
          ) : (
            <p className="tool-sub">No focus sessions yet today. Start one from here or from any block on Today.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function withCustom(options: [string, string][], value: string): [string, string][] {
  return options.some(([v]) => v === value) ? options : [...options, [value, `${value} min`]];
}

/** One-line brain dump, available while focusing. */
export function ParkThought({ onAdded }: { onAdded?: () => void }) {
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    await api.addNote(text.trim());
    setText("");
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
    onAdded?.();
  };

  return (
    <form className="park tool-block" onSubmit={submit}>
      <h3>
        <label htmlFor="park-input">Park a thought</label>
      </h3>
      <div className="park-row">
        <input
          id="park-input"
          className="input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Email the recruiter back"
          autoComplete="off"
        />
        <button type="submit" className="btn">
          Park it
        </button>
      </div>
      <p className="tool-sub" aria-live="polite">
        {saved ? "Parked in your brain dump." : "It waits in your brain dump until you're done."}
      </p>
    </form>
  );
}
