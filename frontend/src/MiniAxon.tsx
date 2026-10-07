/** A small axon for one habit: 66 internodes, one wrapped in myelin per rep. */
export function MiniAxon({ filled, total = 66 }: { filled: number; total?: number }) {
  const W = 660;
  const step = W / total;
  const wrapped = Math.min(filled, total);
  return (
    <svg className="mini-axon" viewBox={`0 0 ${W} 14`} aria-hidden="true">
      <line x1={0} x2={W} y1={7} y2={7} className="axon-line ahead" />
      {wrapped > 0 && <line x1={0} x2={wrapped * step} y1={7} y2={7} className="axon-line walked" />}
      {Array.from({ length: wrapped }, (_, i) => (
        <rect key={i} x={i * step + 1} y={1} width={step - 2} height={12} rx={4} className="sheath" />
      ))}
    </svg>
  );
}
