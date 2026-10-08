import { useCallback, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { api, type SqlDatabase, type SqlQuestion, type SqlResult } from "./api";

const FREE = (db: string) => `free:${db}`;

function loadDraft(key: string): string | null {
  try {
    return localStorage.getItem(`myelin.sql.${key}`);
  } catch {
    return null;
  }
}
function saveDraft(key: string, text: string) {
  try {
    localStorage.setItem(`myelin.sql.${key}`, text);
  } catch {
    /* drafts are a convenience */
  }
}

export function SqlPanel() {
  const [dbs, setDbs] = useState<SqlDatabase[] | null>(null);
  const [questions, setQuestions] = useState<SqlQuestion[]>([]);
  const [selected, setSelected] = useState<string>("company-second-salary");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SqlResult | null>(null);
  const [verdict, setVerdict] = useState<{ correct: boolean; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [solution, setSolution] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadQuestions = useCallback(async () => setQuestions(await api.sqlQuestions()), []);
  useEffect(() => {
    api.sqlDatabases().then(setDbs);
    loadQuestions();
  }, [loadQuestions]);

  const question = questions.find((q) => q.id === selected) ?? null;
  const dbId = question ? question.db : selected.replace("free:", "");
  const db = dbs?.find((d) => d.id === dbId) ?? null;

  useEffect(() => {
    const draft = loadDraft(selected);
    setQuery(draft ?? (question ? "SELECT " : `SELECT * FROM ${db?.tables[0]?.name ?? ""} LIMIT 10`));
    setResult(null);
    setVerdict(null);
    setError(null);
    setSolution(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, dbs]);

  const grouped = useMemo(() => {
    const by: Record<string, SqlQuestion[]> = {};
    for (const q of questions) (by[q.db] ??= []).push(q);
    return by;
  }, [questions]);

  const edit = (text: string) => {
    setQuery(text);
    saveDraft(selected, text);
  };

  const run = async () => {
    setBusy(true);
    setVerdict(null);
    try {
      setResult(await api.sqlRun(dbId, query));
      setError(null);
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    if (!question) return;
    setBusy(true);
    try {
      const r = await api.sqlCheck(question.id, query);
      setResult(r.result);
      setVerdict({ correct: r.correct, message: r.message });
      setError(null);
      if (r.correct) loadQuestions();
    } catch (e) {
      setResult(null);
      setVerdict(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      question ? check() : run();
    } else if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      const el = e.currentTarget;
      const { selectionStart: s, selectionEnd: end } = el;
      const next = `${query.slice(0, s)}  ${query.slice(end)}`;
      edit(next);
      requestAnimationFrame(() => el.setSelectionRange(s + 2, s + 2));
    }
  };

  const solvedCount = questions.filter((q) => q.solved).length;

  return (
    <div className="sql">
      <nav className="sql-list" aria-label="SQL questions">
        <p className="tool-sub">
          {solvedCount} of {questions.length} solved
        </p>
        {dbs?.map((d) => (
          <div key={d.id} className="sql-group">
            <h3>{d.description.split(":")[0]}</h3>
            <ul>
              {(grouped[d.id] ?? []).map((q) => (
                <li key={q.id}>
                  <button
                    type="button"
                    className={`sql-q${selected === q.id ? " is-selected" : ""}${q.solved ? " is-solved" : ""}`}
                    onClick={() => setSelected(q.id)}
                    aria-current={selected === q.id}
                  >
                    <span className="sql-q-mark" aria-hidden="true" />
                    <span>{q.title}</span>
                    <span className="sr-only">{q.solved ? ", solved" : ""}</span>
                  </button>
                </li>
              ))}
              <li>
                <button
                  type="button"
                  className={`sql-q is-free${selected === FREE(d.id) ? " is-selected" : ""}`}
                  onClick={() => setSelected(FREE(d.id))}
                >
                  <span className="sql-q-mark" aria-hidden="true" />
                  <span>Free practice</span>
                </button>
              </li>
            </ul>
          </div>
        ))}
      </nav>

      <section className="sql-work" aria-label="Query">
        {question ? (
          <>
            <p className="sql-meta muted small">
              <span className="cap">{question.difficulty}</span>, {question.pattern}
            </p>
            <h3 className="sql-title">{question.title}</h3>
            <p className="sql-prompt">{question.prompt}</p>
          </>
        ) : (
          <>
            <h3 className="sql-title">Free practice</h3>
            <p className="sql-prompt">{db?.description}. Anything you run works on a fresh copy, so experiment freely.</p>
          </>
        )}

        {db && (
          <details className="schema" open>
            <summary>Tables</summary>
            <ul>
              {db.tables.map((t) => (
                <li key={t.name}>
                  <strong>{t.name}</strong>{" "}
                  <span className="muted">
                    ({t.columns.map((c) => c.name).join(", ")}), {t.rows} rows
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}

        <label className="sr-only" htmlFor="sql-editor">
          SQL query
        </label>
        <textarea
          id="sql-editor"
          className="sql-editor"
          value={query}
          onChange={(e) => edit(e.target.value)}
          onKeyDown={onKey}
          spellCheck={false}
          rows={7}
        />

        <div className="form-actions">
          {question && (
            <button type="button" className="btn primary" onClick={check} disabled={busy}>
              Check answer
            </button>
          )}
          <button type="button" className={question ? "btn" : "btn primary"} onClick={run} disabled={busy}>
            Run
          </button>
          <span className="muted small">Ctrl+Enter {question ? "checks" : "runs"}</span>
          {question && !solution && (
            <button
              type="button"
              className="btn quiet push-right"
              onClick={async () => setSolution((await api.sqlSolution(question.id)).solution)}
            >
              Show a solution
            </button>
          )}
        </div>

        {verdict && (
          <p className={`verdict ${verdict.correct ? "is-correct" : "is-wrong"}`} role="status">
            {verdict.message}
          </p>
        )}
        {error && (
          <p className="verdict is-wrong" role="alert">
            {error}
          </p>
        )}
        {solution && (
          <div className="solution">
            <p className="muted small">One way to solve it:</p>
            <pre>{solution}</pre>
          </div>
        )}
        {result && <ResultTable result={result} />}
      </section>
    </div>
  );
}

function ResultTable({ result }: { result: SqlResult }) {
  if (result.columns.length === 0) {
    return <p className="tool-sub">Ran in {result.ms} ms. No rows to show.</p>;
  }
  return (
    <div className="result">
      <p className="muted small">
        {result.rows.length}
        {result.truncated ? "+" : ""} row{result.rows.length === 1 ? "" : "s"} in {result.ms} ms
      </p>
      <div className="result-scroll">
        <table>
          <thead>
            <tr>
              {result.columns.map((c, i) => (
                <th key={i}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, i) => (
              <tr key={i}>
                {row.map((v, j) => (
                  <td key={j} className={typeof v === "number" ? "num" : ""}>
                    {v === null ? <span className="muted">NULL</span> : String(v)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
