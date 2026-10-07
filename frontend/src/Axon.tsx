import { useEffect, useRef, useState } from "react";
import type { Streak } from "./api";

const W = 1000; // SVG units; the drawing scales to the column width
const H = 40;
const PAD = 6;
const AXON_Y = 18;
const SHEATH_H = 18;
const NODE_GAP = 1.8; // the node of Ranvier between two sheaths
const MILESTONES = [
  { day: 7, label: "7 days" },
  { day: 30, label: "30 days" },
  { day: 66, label: "66 days: automatic" },
];

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * The streak drawn as an axon. Each day of the 66-day cycle is one internode;
 * a completed day wraps that internode in myelin. Missed days stay bare, without penalty colours.
 */
export function Axon({ streak }: { streak: Streak }) {
  const n = streak.cycle_length;
  const step = (W - PAD * 2) / n;
  const x = (i: number) => PAD + i * step;
  const todayIndex = streak.cycle_day - 1;
  const lastPast = todayIndex;

  // When today's segment gets wrapped, send one signal hopping node to node along the myelinated stretch:
  // saltatory conduction, the reason myelin makes signals fast.
  const [signal, setSignal] = useState<number | null>(null);
  const wasComplete = useRef(streak.today_complete);
  useEffect(() => {
    const justCompleted = streak.today_complete && !wasComplete.current;
    wasComplete.current = streak.today_complete;
    if (!justCompleted || prefersReducedMotion()) return;
    let i = 0;
    setSignal(0);
    const timer = window.setInterval(() => {
      i += 1;
      if (i > lastPast + 1) {
        window.clearInterval(timer);
        setSignal(null);
      } else {
        setSignal(i);
      }
    }, 45);
    return () => window.clearInterval(timer);
  }, [streak.today_complete, lastPast]);

  return (
    <figure className="axon" aria-label={describe(streak)}>
      <div className="axon-today" style={{ left: `${((x(lastPast) + step / 2) / W) * 100}%` }}>
        Day {streak.cycle_day}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
        {/* bare axon: walked so far, then still ahead */}
        <line x1={PAD} x2={x(lastPast + 1)} y1={AXON_Y} y2={AXON_Y} className="axon-line walked" />
        <line x1={x(lastPast + 1)} x2={W - PAD} y1={AXON_Y} y2={AXON_Y} className="axon-line ahead" />

        {streak.cycle.map((d, i) => {
          const x0 = x(i) + NODE_GAP;
          const w = step - NODE_GAP * 2;
          const y0 = AXON_Y - SHEATH_H / 2;
          if (d.status === "done") {
            return <rect key={d.date} x={x0} y={y0} width={w} height={SHEATH_H} rx={Math.min(6, w / 2)} className="sheath" />;
          }
          if (i === todayIndex) {
            return <rect key={d.date} x={x0} y={y0} width={w} height={SHEATH_H} rx={Math.min(6, w / 2)} className="sheath-today" />;
          }
          return null;
        })}

        {MILESTONES.map((m) => (
          <line key={m.day} x1={x(m.day)} x2={x(m.day)} y1={AXON_Y + 14} y2={AXON_Y + 20} className="milestone-tick" />
        ))}

        {signal !== null && <circle cx={x(signal)} cy={AXON_Y} r={5} className="signal" />}
      </svg>
      <div className="axon-milestones" aria-hidden="true">
        {MILESTONES.map((m) => (
          <span key={m.day} style={{ left: `${(x(m.day) / W) * 100}%` }} className={m.day === n ? "end" : ""}>
            {m.label}
          </span>
        ))}
      </div>
    </figure>
  );
}

function describe(s: Streak): string {
  const wrapped = s.cycle.filter((d) => d.status === "done").length;
  return `Day ${s.cycle_day} of ${s.cycle_length}. ${wrapped} segments myelinated. Current streak ${s.current} days.`;
}
