import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type BusyTime, type PlanItem, type Prayers, type Streak, type Today, type Track } from "./api";
import { Axon } from "./Axon";
import type { FocusApi } from "./Focus";
import { QuickLog } from "./LeetCode";
import { PRAYER_LABEL, formatTime, until } from "./time";

const rangeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const fmtRange = (a: string, b: string) => rangeFmt.formatRange(new Date(a), new Date(b));

const EXAMPLES = ["busy till 3", "meeting 2-4", "free 12-1", "light day", "skip gym", "note call the bank"];

export function streakLine(s: Streak, light: boolean): string {
  if (s.today_complete) return `Today's segment is wrapped. ${s.current}-day streak.`;
  const goal = light ? "a 20-minute block" : "today's interview hour";
  if (s.current === 0) return `Finish ${goal} to wrap your first segment.`;
  return `${s.current}-day streak. Finish ${goal} to keep it growing.`;
}

export function TodayView({
  today,
  now,
  focus,
  onChanged,
  goTools,
  goSettings,
}: {
  today: Today;
  now: Date;
  focus: FocusApi;
  onChanged: () => void;
  goTools: (tool?: string) => void;
  goSettings: () => void;
}) {
  const [logFor, setLogFor] = useState<{ id: number; track: Track } | null>(null);

  const toggle = async (item: PlanItem) => {
    await api.toggle(item.id);
    if (!item.done && item.track.startsWith("leetcode")) {
      setLogFor({ id: item.id, track: item.track === "leetcode_sql" ? "sql" : "python" });
    }
    onChanged();
  };

  return (
    <>
      <section className="pathway" aria-label="Streak">
        <Axon streak={today.streak} />
        <p className="streak-line">{streakLine(today.streak, today.day.light)}</p>
      </section>

      <div className="lower">
        <section className="today" aria-labelledby="today-heading">
          <div className="today-head">
            <h2 id="today-heading">Today</h2>
            <DayControls today={today} onChanged={onChanged} />
            <CommandBar onDone={onChanged} />
          </div>
          <ol className="plan">
            {today.plan.map((item) => (
              <PlanRow
                key={item.id}
                item={item}
                isNext={item === nextBlock(today.plan)}
                focus={focus}
                onToggle={() => toggle(item)}
                onSkip={async () => (await api.skip(item.id), onChanged())}
                logging={logFor?.id === item.id ? logFor.track : null}
                onLogDone={() => setLogFor(null)}
              />
            ))}
          </ol>
          <PlanFooter today={today} goTools={goTools} />
        </section>

        <aside className="day-side">
          <PrayerTimes now={now} prayers={today.prayers} onChange={goSettings} />
          <BusyList busy={today.day.busy} errors={today.day.calendar_errors} onChanged={onChanged} />
        </aside>
      </div>
    </>
  );
}

function nextBlock(plan: PlanItem[]): PlanItem | undefined {
  const scheduled = plan.filter((p) => !p.done && p.status === "scheduled" && p.start);
  scheduled.sort((a, b) => (a.start! < b.start! ? -1 : 1));
  return scheduled[0];
}

function CommandBar({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState("");
  const [reply, setReply] = useState<{ ok: boolean; text: string } | null>(null);
  const [example, setExample] = useState(0);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const t = window.setInterval(() => setExample((e) => (e + 1) % EXAMPLES.length), 6000);
    return () => window.clearInterval(t);
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    try {
      const r = await api.command(text);
      setReply({ ok: true, text: r.message });
      setText("");
      onDone();
    } catch (err) {
      setReply({ ok: false, text: err instanceof Error ? err.message : String(err) });
    }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setReply(null), 9000);
  };

  return (
    <form className="command" onSubmit={submit}>
      <label className="sr-only" htmlFor="command-input">
        Tell Myelin about your day
      </label>
      <input
        id="command-input"
        className="input command-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={`Tell Myelin: "${EXAMPLES[example]}"`}
        autoComplete="off"
      />
      {reply && (
        <p className={`command-reply${reply.ok ? "" : " is-error"}`} role="status">
          {reply.text}
        </p>
      )}
    </form>
  );
}

const ENERGY: ["low" | "ok" | "high", string][] = [
  ["low", "Low"],
  ["ok", "OK"],
  ["high", "High"],
];

function DayControls({ today, onChanged }: { today: Today; onChanged: () => void }) {
  const { light, auto_light, energy } = today.day;
  const [editing, setEditing] = useState(false);
  const set = async (patch: { light?: boolean; energy?: "low" | "ok" | "high" }) => {
    await api.setDay(patch);
    setEditing(false);
    onChanged();
  };

  return (
    <div className="day-controls">
      {energy === null || editing ? (
        <div className="energy" role="group" aria-label="How's your energy today?">
          <span className="muted">Energy today?</span>
          {ENERGY.map(([v, label]) => (
            <button
              key={v}
              type="button"
              className={`chip${energy === v ? " is-on" : ""}`}
              onClick={() => set({ energy: v })}
            >
              {label}
            </button>
          ))}
        </div>
      ) : (
        <span className="muted">
          Energy {ENERGY.find(([v]) => v === energy)?.[1].toLowerCase()}.{" "}
          <button type="button" className="link-button" onClick={() => setEditing(true)}>
            Change
          </button>
        </span>
      )}
      {auto_light ? (
        <span className="chip is-on is-static">Light day: no room for the full hour</span>
      ) : energy === "low" ? (
        <span className="chip is-on is-static">Light day: low energy</span>
      ) : (
        <button
          type="button"
          className={`chip${light ? " is-on" : ""}`}
          aria-pressed={light}
          onClick={() => set({ light: !light })}
          title="A light day needs one 20-minute block to keep the streak"
        >
          {light ? "Light day" : "Make it a light day"}
        </button>
      )}
    </div>
  );
}

function PlanRow({
  item,
  isNext,
  focus,
  onToggle,
  onSkip,
  logging,
  onLogDone,
}: {
  item: PlanItem;
  isNext: boolean;
  focus: FocusApi;
  onToggle: () => void;
  onSkip: () => void;
  logging: Track | null;
  onLogDone: () => void;
}) {
  const running = focus.state?.active?.plan_item_id === item.id;
  const minutes = item.scheduled_minutes ?? item.minutes;
  const cls = [
    "plan-item",
    item.done && "is-done",
    isNext && "is-next",
    item.skipped && "is-skipped",
    (item.bonus || item.optional) && "is-bonus",
    item.status === "no_room" && "is-unplaced",
  ]
    .filter(Boolean)
    .join(" ");

  let when: string;
  if (item.done) when = "Done";
  else if (item.skipped) when = "Skipped today";
  else if (item.status === "no_room") when = item.optional || item.bonus ? "Bonus, if time allows" : "No room left today";
  else if (item.start && item.end) when = fmtRange(item.start, item.end);
  else when = `${minutes} min`;

  return (
    <>
      <li className={cls}>
        <button
          type="button"
          className="check"
          aria-pressed={item.done}
          aria-label={`${item.done ? "Mark not done" : "Mark done"}: ${item.title}`}
          onClick={onToggle}
        >
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path d="M5 10.5l3.2 3.2L15 7" />
          </svg>
        </button>
        <div className="plan-text">
          <span className="plan-title">{item.title}</span>
          <span className="plan-detail">
            {item.detail}
            {item.scheduled_minutes && item.scheduled_minutes < item.minutes ? ` (rescue: ${minutes} min)` : ""}
            {item.optional && !item.bonus ? " (optional today)" : ""}
          </span>
        </div>
        <div className="plan-when">
          {!item.done && (
            <span className="plan-actions">
              {!item.skipped && !running && (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => focus.start({ plan_item_id: item.id, minutes })}
                  aria-label={`Start a ${minutes}-minute focus on ${item.title}`}
                >
                  Start
                </button>
              )}
              {running && <span className="muted">Focusing</span>}
              {!item.counts_for_streak && (
                <button type="button" className="link-button" onClick={onSkip}>
                  {item.skipped ? "Unskip" : "Skip"}
                </button>
              )}
            </span>
          )}
          <span className="plan-time">{when}</span>
        </div>
      </li>
      {logging && (
        <li className="quick-log-row">
          <QuickLog track={logging} onDone={onLogDone} />
        </li>
      )}
    </>
  );
}

function PlanFooter({ today, goTools }: { today: Today; goTools: (tool?: string) => void }) {
  const hour = today.plan.filter((p) => p.counts_for_streak);
  const done = hour.filter((p) => p.done).length;
  const due = today.resolves_due.length;
  let line: string;
  if (today.streak.today_complete) line = today.day.light ? "Rescue done. The streak is safe." : "Interview hour done.";
  else if (today.day.light) line = "Light day: one finished interview block keeps the streak.";
  else line = `Interview hour: ${done} of ${hour.length} blocks done.`;

  return (
    <p className="plan-progress">
      {line}
      {due > 0 && (
        <>
          {" "}
          <button type="button" className="link-button" onClick={() => goTools("leetcode")}>
            {due} problem{due === 1 ? "" : "s"} due for a re-solve
          </button>
          .
        </>
      )}
    </p>
  );
}

export function NextPrayer({
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

function PrayerTimes({ now, prayers, onChange }: { now: Date; prayers: Prayers | null; onChange: () => void }) {
  if (!prayers) return null;
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

function BusyList({ busy, errors, onChanged }: { busy: BusyTime[]; errors: string[]; onChanged: () => void }) {
  // Work and commute are your routine; list only what's different about today.
  const shown = busy.filter((b) => b.source !== "work");
  if (shown.length === 0 && errors.length === 0) return null;
  return (
    <section className="busy" aria-labelledby="busy-heading">
      <h2 id="busy-heading">Around your day</h2>
      <ul className="busy-list">
        {shown.map((b, i) => (
          <li key={`${b.start}-${i}`} className={b.free ? "is-free" : ""}>
            <span className="busy-label">
              {b.free ? `Free: ${b.label === "Free" ? "time you made" : b.label}` : b.label}
              {b.source === "calendar" && <span className="muted small"> calendar</span>}
            </span>
            <span className="busy-time">{fmtRange(b.start, b.end)}</span>
            {b.source === "you" && b.id !== null ? (
              <button
                type="button"
                className="link-button small"
                onClick={async () => (await api.removeBusy(b.id!), onChanged())}
                aria-label={`Remove ${b.label}`}
              >
                Remove
              </button>
            ) : (
              <span />
            )}
          </li>
        ))}
      </ul>
      {errors.length > 0 && <p className="muted small">A calendar couldn't be reached, so I used the last copy.</p>}
    </section>
  );
}

export function InterviewCountdown({ today }: { today: Today | null }) {
  const next = today?.interviews.find((i) => i.days_left >= 0 && i.days_left <= 30);
  if (!next) return null;
  const when = next.days_left === 0 ? "today" : next.days_left === 1 ? "tomorrow" : `in ${next.days_left} days`;
  return (
    <p className="interview-next">
      {next.company} interview {when}
    </p>
  );
}
