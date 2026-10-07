import { useEffect, useState } from "react";
import { api, type Week, type WeekDay } from "./api";

const weekdayFmt = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const dayFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const asDate = (iso: string) => new Date(`${iso}T12:00:00`);

export function WeekView() {
  const [week, setWeek] = useState<Week | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.week().then(setWeek, (e) => setError(e.message));
  }, []);

  if (error) return <p className="notice" role="alert">{error}</p>;
  if (!week) return null;

  const counted = week.days.filter((d) => d.status === "done" || d.status === "missed" || d.status === "today");
  const wrapped = week.days.filter((d) => d.status === "done").length;

  return (
    <section className="week" aria-label="This week">
      <p className="view-lead">
        {counted.length === 0
          ? "Your week starts here."
          : `${wrapped} of ${counted.length} ${counted.length === 1 ? "day" : "days"} wrapped so far this week.`}
      </p>
      <ol className="week-grid">
        {week.days.map((d) => (
          <DayColumn key={d.date} day={d} isToday={d.date === week.today} />
        ))}
      </ol>
    </section>
  );
}

function DayColumn({ day, isToday }: { day: WeekDay; isToday: boolean }) {
  const date = asDate(day.date);
  return (
    <li className={`week-day is-${day.status}${isToday ? " is-current" : ""}`} aria-current={isToday ? "date" : undefined}>
      <p className="week-day-name">
        <span>{weekdayFmt.format(date)}</span>
        <span className="week-day-date">{dayFmt.format(date)}</span>
      </p>
      <div className="week-segment" aria-hidden="true">
        <span />
      </div>
      <ul className="week-blocks">
        {day.blocks.map((b, i) => (
          <li key={i} className={b.done ? "is-done" : ""}>
            <span className="week-block-title">{b.title}</span>
            <span className="week-block-detail">{b.detail || `${b.minutes} min`}</span>
          </li>
        ))}
      </ul>
    </li>
  );
}
