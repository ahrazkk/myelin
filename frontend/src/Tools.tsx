import { useState } from "react";
import type { PlanItem } from "./api";
import { FocusPanel, type FocusApi } from "./Focus";
import { LeetCodePanel } from "./LeetCode";
import { NotesPanel } from "./Notes";
import { Segmented } from "./Settings";
import { SqlPanel } from "./SqlPlayground";

export const TOOLS = [
  ["focus", "Focus timer"],
  ["notes", "Brain dump"],
  ["leetcode", "LeetCode log"],
  ["sql", "SQL playground"],
] as const;
export type Tool = (typeof TOOLS)[number][0];

export function initialTool(): Tool {
  const sub = window.location.hash.split("/")[1];
  return TOOLS.some(([id]) => id === sub) ? (sub as Tool) : "focus";
}

export function ToolsView({ focus, plan }: { focus: FocusApi; plan: PlanItem[] }) {
  const [tool, setTool] = useState<Tool>(initialTool);
  const pick = (t: Tool) => {
    setTool(t);
    window.history.replaceState(null, "", `/#tools/${t}`);
  };

  return (
    <section className="tools" aria-label="Tools">
      <Segmented label="Tool" value={tool} options={TOOLS.map(([a, b]) => [a, b] as [Tool, string])} onChange={pick} />
      <div className="tool-body">
        {tool === "focus" && <FocusPanel focus={focus} plan={plan} />}
        {tool === "notes" && <NotesPanel />}
        {tool === "leetcode" && <LeetCodePanel />}
        {tool === "sql" && <SqlPanel />}
      </div>
    </section>
  );
}
