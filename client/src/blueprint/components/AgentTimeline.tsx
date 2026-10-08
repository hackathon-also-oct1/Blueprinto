import { useEffect, useRef } from 'react';

import type { AgentState, LogLine } from '../types';

export function AgentTimeline({ agents, log, runId }: { agents: AgentState[]; log: LogLine[]; runId: string | null }) {
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log.length]);
  const titles = new Map(agents.map((a) => [a.id, a.title]));

  return (
    <section className="pane" aria-label="Agent run">
      <span className="label">Agent run · {runId ?? 'not started'}</span>
      <ol className="agents">
        {agents.map((a, i) => (
          <li className="agent" data-s={a.status} key={a.id}>
            <div className="dot">{i + 1}</div>
            <div>
              <h3>{a.title}</h3>
              <div className="svc">{a.service}</div>
              <div className="meta">
                <span className="chip">{a.status}</span>
                {a.duration_ms != null && <span>{(a.duration_ms / 1000).toFixed(1)}s</span>}
                {!!a.tokens && <span>{a.tokens.toLocaleString()} tok</span>}
              </div>
              {a.note && <div className="note">{a.note}</div>}
            </div>
          </li>
        ))}
      </ol>
      <div className="log" ref={logRef} aria-live="polite">
        {log.length === 0 && <div>Agent activity streams here during a run.</div>}
        {log.map((l, i) => (
          <div key={i}>
            {l.at} <i>{titles.get(l.agent) ?? l.agent}</i> {l.message}
          </div>
        ))}
      </div>
    </section>
  );
}
