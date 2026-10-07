import { useEffect, useState } from "react";
import { api, type Progress } from "./api";
import { MiniAxon } from "./MiniAxon";

const longDate = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "long" });
const monthFmt = new Intl.DateTimeFormat(undefined, { month: "short" });
const asDate = (iso: string) => new Date(`${iso}T12:00:00`);

export function ProgressView() {
  const [p, setP] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.progress().then(setP, (e) => setError(e.message));
  }, []);

  if (error) return <p className="notice" role="alert">{error}</p>;
  if (!p) return null;

  return (
    <section className="progress" aria-label="Progress">
      <div className="progress-days">
        <p className="view-lead">
          {p.current}-day streak. Your best is {p.best}.
        </p>
        <p className="progress-sub">
          {p.days_done} of {p.days_since_start} {p.days_since_start === 1 ? "day" : "days"} wrapped since{" "}
          {longDate.format(asDate(p.started_on))}.
        </p>
        <Heatmap weeks={p.weeks} />
      </div>

      <div className="habits">
        <h2>Reps toward automatic</h2>
        <p className="progress-sub">
          Each finished block is one rep. Daily habits took a median of 66 days to run on their own.
        </p>
        <ol className="habit-list">
          {p.habits.map((h) => (
            <li key={h.track}>
              <p className="habit-head">
                <span className="habit-name">{h.name}</span>
                <span className="habit-count">
                  {h.reps >= h.target ? "Automatic" : `${h.reps} of ${h.target}`}
                </span>
              </p>
              <MiniAxon filled={h.reps} total={h.target} />
              {h.per_week > 0 && (
                <p className="habit-week">
                  {h.this_week} of {h.per_week} this week
                </p>
              )}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

const CELL = 14;
const GAP = 4;
const LEFT = 34;
const TOP = 20;
const ROW_LABELS: Record<number, string> = { 0: "Mon", 2: "Wed", 4: "Fri" };

function Heatmap({ weeks }: { weeks: Progress["weeks"] }) {
  const width = LEFT + weeks.length * (CELL + GAP);
  const height = TOP + 7 * (CELL + GAP);
  const done = weeks.flat().filter((d) => d.status === "done").length;

  return (
    <figure className="heatmap">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: `min(100%, ${width * 2.2}px)` }}
        role="img"
        aria-label={`Calendar of the last ${weeks.length} weeks. ${done} days wrapped.`}
      >
        {Object.entries(ROW_LABELS).map(([row, label]) => (
          <text key={row} x={0} y={TOP + Number(row) * (CELL + GAP) + CELL - 3} className="heat-label">
            {label}
          </text>
        ))}
        {weeks.map((week, w) => {
          const first = asDate(week[0].date);
          const prev = w > 0 ? asDate(weeks[w - 1][0].date) : null;
          const showMonth = !prev || prev.getMonth() !== first.getMonth();
          return (
            <g key={week[0].date}>
              {showMonth && (
                <text x={LEFT + w * (CELL + GAP)} y={12} className="heat-label">
                  {monthFmt.format(first)}
                </text>
              )}
              {week.map((d, row) => (
                <rect
                  key={d.date}
                  x={LEFT + w * (CELL + GAP)}
                  y={TOP + row * (CELL + GAP)}
                  width={CELL}
                  height={CELL}
                  rx={3}
                  className={`heat is-${d.status}`}
                >
                  <title>{`${longDate.format(asDate(d.date))}: ${d.status === "done" ? "wrapped" : d.status}`}</title>
                </rect>
              ))}
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
