import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type Difficulty, type Outcome, type Problem, type Problems, type Track } from "./api";
import { openLink } from "./links";
import { Segmented } from "./Settings";

const TRACKS: [Track, string][] = [
  ["python", "Python"],
  ["sql", "SQL"],
];
const DIFFICULTIES: [Difficulty, string][] = [
  ["easy", "Easy"],
  ["medium", "Medium"],
  ["hard", "Hard"],
];
const OUTCOMES: [Outcome, string][] = [
  ["solved", "Solved"],
  ["hint", "Needed a hint"],
  ["stuck", "Stuck"],
];
const OUTCOME_WORD: Record<Outcome, string> = { solved: "Solved", hint: "Hint", stuck: "Stuck" };

const dayFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const asDate = (iso: string) => new Date(`${iso}T12:00:00`);

export function LogForm({
  patternNames,
  initialTrack = "python",
  compact = false,
  onSaved,
  onCancel,
}: {
  patternNames: Record<Track, string[]>;
  initialTrack?: Track;
  compact?: boolean;
  onSaved: (p: Problem & { was_new: boolean }) => void;
  onCancel?: () => void;
}) {
  const [link, setLink] = useState("");
  const [track, setTrack] = useState<Track>(initialTrack);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [pattern, setPattern] = useState("");
  const [outcome, setOutcome] = useState<Outcome>("solved");
  const [minutes, setMinutes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const text = link.trim();
    if (!text) {
      setError("Paste the problem link or type its name.");
      return;
    }
    const isUrl = /^https?:\/\//i.test(text);
    try {
      const saved = await api.logProblem({
        url: isUrl ? text : "",
        title: isUrl ? undefined : text,
        track,
        difficulty,
        pattern,
        outcome,
        minutes: Number(minutes) || 0,
      });
      setLink("");
      setMinutes("");
      setError(null);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <form className={`log-form${compact ? " is-compact" : ""}`} onSubmit={submit}>
      <label className="field wide">
        Problem link or name
        <input
          className="input"
          value={link}
          onChange={(e) => setLink(e.target.value)}
          placeholder="https://leetcode.com/problems/two-sum/"
          autoComplete="off"
        />
      </label>
      <div className="log-row">
        <Segmented label="Track" value={track} options={TRACKS} onChange={(t) => (setTrack(t), setPattern(""))} />
        <Segmented label="Difficulty" value={difficulty} options={DIFFICULTIES} onChange={setDifficulty} />
      </div>
      <div className="log-row">
        <label className="field">
          Pattern
          <select className="input" value={pattern} onChange={(e) => setPattern(e.target.value)}>
            <option value="">Not sure</option>
            {patternNames[track].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Minutes
          <input
            className="input minutes"
            inputMode="numeric"
            value={minutes}
            onChange={(e) => setMinutes(e.target.value.replace(/\D/g, ""))}
            placeholder="20"
          />
        </label>
      </div>
      <p className="field-label">How did it go?</p>
      <Segmented label="Outcome" value={outcome} options={OUTCOMES} onChange={setOutcome} />
      {error && <p className="form-error">{error}</p>}
      <div className="form-actions">
        <button type="submit" className="btn primary">
          Log problem
        </button>
        {onCancel && (
          <button type="button" className="btn quiet" onClick={onCancel}>
            Skip
          </button>
        )}
      </div>
    </form>
  );
}

function ProblemTitle({ p }: { p: Problem }) {
  return p.url ? (
    <button type="button" className="link-button problem-title" onClick={() => openLink(p.url)}>
      {p.title}
    </button>
  ) : (
    <span className="problem-title">{p.title}</span>
  );
}

export function LeetCodePanel() {
  const [data, setData] = useState<Problems | null>(null);
  const [statsTrack, setStatsTrack] = useState<Track>("python");
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => setData(await api.problems()), []);
  useEffect(() => {
    load();
  }, [load]);

  if (!data) return null;

  const resolve = async (p: Problem, outcome: Outcome) => {
    const after = await api.attempt(p.id, outcome);
    setMessage(
      after.mastered
        ? `${p.title} is mastered. It won't come back.`
        : `${p.title} comes back on ${dayFmt.format(asDate(after.due_on!))}.`,
    );
    load();
  };

  const next = data.stats.next[statsTrack];
  const rows = data.stats.patterns.filter((r) => r.track === statsTrack);

  return (
    <div className="leetcode">
      <div className="tool-columns">
        <section className="tool-block" aria-labelledby="log-heading">
          <h3 id="log-heading">Log a problem</h3>
          <LogForm
            patternNames={data.pattern_names}
            onSaved={(p) => {
              setMessage(
                p.due_on
                  ? `Logged ${p.title}. It comes back on ${dayFmt.format(asDate(p.due_on))}.`
                  : `Logged ${p.title}.`,
              );
              load();
            }}
          />
          {message && (
            <p className="status" role="status">
              {message}
            </p>
          )}
        </section>

        <div>
          <section className="tool-block" aria-labelledby="due-heading">
            <h3 id="due-heading">Due for a re-solve</h3>
            <p className="tool-sub">
              Solve it again from memory, without looking at your old code. Clean solves push the next one further
              out: {data.ladder_days.map((d) => `+${d}`).join(", ")} days.
            </p>
            {data.due.length === 0 ? (
              <p className="tool-sub">Nothing due today.</p>
            ) : (
              <ul className="due-list">
                {data.due.map((p) => (
                  <li key={p.id}>
                    <div>
                      <ProblemTitle p={p} />
                      <span className="muted small">
                        {p.pattern || "No pattern"}, last: {p.last_outcome ? OUTCOME_WORD[p.last_outcome] : "new"}
                      </span>
                    </div>
                    <div className="due-actions" role="group" aria-label={`How did ${p.title} go?`}>
                      <button type="button" className="btn primary small" onClick={() => resolve(p, "solved")}>
                        Solved
                      </button>
                      <button type="button" className="btn small" onClick={() => resolve(p, "hint")}>
                        Hint
                      </button>
                      <button type="button" className="btn quiet small" onClick={() => resolve(p, "stuck")}>
                        Stuck
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="tool-block" aria-labelledby="patterns-heading">
            <div className="block-head">
              <h3 id="patterns-heading">Patterns</h3>
              <Segmented label="Track" value={statsTrack} options={TRACKS} onChange={setStatsTrack} />
            </div>
            {next && (
              <p className="next-pattern">
                Next up: <strong>{next.pattern}</strong>, {next.why}.
              </p>
            )}
            <ol className="pattern-list">
              {rows.map((r) => (
                <li key={r.pattern} className={r.attempts ? "" : "is-untried"}>
                  <span>{r.pattern}</span>
                  <span className="pattern-bar" aria-hidden="true">
                    <span style={{ width: `${(r.solve_rate ?? 0) * 100}%` }} />
                  </span>
                  <span className="muted small pattern-num">
                    {r.attempts ? `${Math.round((r.solve_rate ?? 0) * 100)}% of ${r.attempts}` : "not yet"}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>

      {data.problems.length > 0 && (
        <section className="tool-block" aria-labelledby="all-heading">
          <h3 id="all-heading">All problems ({data.problems.length})</h3>
          <table className="problem-table">
            <thead>
              <tr>
                <th>Problem</th>
                <th>Pattern</th>
                <th>Difficulty</th>
                <th>Last time</th>
                <th>Next re-solve</th>
                <th>
                  <span className="sr-only">Remove</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.problems.map((p) => (
                <tr key={p.id}>
                  <td>
                    <ProblemTitle p={p} />
                  </td>
                  <td>{p.pattern || <span className="muted">None</span>}</td>
                  <td className="cap">{p.difficulty}</td>
                  <td>
                    {p.last_outcome ? OUTCOME_WORD[p.last_outcome] : "None"}
                    {p.last_minutes ? <span className="muted">, {p.last_minutes} min</span> : null}
                  </td>
                  <td className={p.is_due ? "is-due" : ""}>
                    {p.mastered ? "Mastered" : p.is_due ? "Today" : dayFmt.format(asDate(p.due_on!))}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn quiet small"
                      onClick={async () => {
                        await api.deleteProblem(p.id);
                        load();
                      }}
                      aria-label={`Remove ${p.title}`}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

/** Shown under a LeetCode block on Today right after it's checked off. */
export function QuickLog({ track, onDone }: { track: Track; onDone: () => void }) {
  const [names, setNames] = useState<Record<Track, string[]> | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    api.problems().then((p) => setNames(p.pattern_names), () => setNames({ python: [], sql: [] }));
  }, []);

  if (saved) {
    return (
      <div className="quick-log" role="status">
        <p>{saved}</p>
        <button type="button" className="btn quiet" onClick={onDone}>
          Close
        </button>
      </div>
    );
  }
  if (!names) return null;
  return (
    <div className="quick-log">
      <p className="quick-log-title">Log it for your re-solve queue?</p>
      <LogForm
        compact
        patternNames={names}
        initialTrack={track}
        onCancel={onDone}
        onSaved={(p) =>
          setSaved(p.due_on ? `Logged. ${p.title} comes back on ${dayFmt.format(asDate(p.due_on))}.` : "Logged.")
        }
      />
    </div>
  );
}
