import { useCallback, useEffect, useState } from "react";
import { api, type Note } from "./api";
import { ParkThought } from "./Focus";

const timeFmt = new Intl.DateTimeFormat(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });

export function NotesPanel() {
  const [notes, setNotes] = useState<{ open: Note[]; cleared: Note[] } | null>(null);
  const [showCleared, setShowCleared] = useState(false);

  const load = useCallback(async () => setNotes(await api.notes()), []);
  useEffect(() => {
    load();
  }, [load]);

  const mark = async (n: Note, done: boolean) => {
    await api.editNote(n.id, { done });
    load();
  };
  const remove = async (n: Note) => {
    await api.deleteNote(n.id);
    load();
  };

  return (
    <div className="tool-columns">
      <div>
        <ParkThought onAdded={load} />
        <p className="hint">
          Your working memory holds only a few things at once. Parking a thought frees it up, so it stops tugging at
          you mid-focus.
        </p>
      </div>
      <section aria-labelledby="dump-heading" className="tool-block">
        <h3 id="dump-heading">Parked thoughts</h3>
        {notes && notes.open.length === 0 && <p className="tool-sub">Nothing parked. Your head is clear.</p>}
        <ul className="note-list">
          {notes?.open.map((n) => (
            <li key={n.id}>
              <button type="button" className="check small" aria-label={`Clear: ${n.text}`} onClick={() => mark(n, true)}>
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M5 10.5l3.2 3.2L15 7" />
                </svg>
              </button>
              <span className="note-text">{n.text}</span>
              <span className="muted note-time">{timeFmt.format(new Date(n.created_at))}</span>
            </li>
          ))}
        </ul>
        {notes && notes.cleared.length > 0 && (
          <>
            <button type="button" className="btn quiet" onClick={() => setShowCleared((v) => !v)}>
              {showCleared ? "Hide" : "Show"} cleared this week ({notes.cleared.length})
            </button>
            {showCleared && (
              <ul className="note-list is-cleared">
                {notes.cleared.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      className="check small is-on"
                      aria-label={`Bring back: ${n.text}`}
                      onClick={() => mark(n, false)}
                    >
                      <svg viewBox="0 0 20 20" aria-hidden="true">
                        <path d="M5 10.5l3.2 3.2L15 7" />
                      </svg>
                    </button>
                    <span className="note-text">{n.text}</span>
                    <button type="button" className="btn quiet" onClick={() => remove(n)}>
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  );
}
