import { money } from '../estimate';
import type { Estimate } from '../types';

export function KpiRow({ est, screens }: { est: Estimate; screens: number }) {
  return (
    <div className="kpis">
      <div className="kpi"><div className="v">{money(est.total, est.currency)}</div><div className="k">Budget incl. {est.contingency_pct}% contingency</div></div>
      <div className="kpi"><div className="v">{est.weeks} weeks</div><div className="k">Time to launch</div></div>
      <div className="kpi"><div className="v">{est.people} people</div><div className="k">Team ({est.fte.toFixed(1)} FTE)</div></div>
      <div className="kpi"><div className="v">{screens}</div><div className="k">Screens in flow</div></div>
    </div>
  );
}

export function EstimatePanel({ est }: { est: Estimate | null }) {
  if (!est) return <div className="empty">The Estimator's budget, timeline and team appear here after a run.</div>;
  const W = est.weeks;
  const c = est.currency;
  return (
    <div>
      <div className="kpis">
        <div className="kpi"><div className="v">{money(est.total, c)}</div><div className="k">Expected budget</div></div>
        <div className="kpi"><div className="v">{money(est.low, c)} – {money(est.high, c)}</div><div className="k">Likely range</div></div>
        <div className="kpi"><div className="v">{W} weeks</div><div className="k">{Math.ceil(W / 2)} two-week sprints</div></div>
        <div className="kpi"><div className="v">{est.people} people</div><div className="k">{est.fte.toFixed(1)} FTE</div></div>
      </div>
      <div className="tbl-wrap">
        <table>
          <thead>
            <tr><th>Role</th><th className="n">Headcount</th><th className="n">Person-days</th><th className="n">Day rate</th><th className="n">Cost</th></tr>
          </thead>
          <tbody>
            {est.lines.map((l) => (
              <tr key={l.role_id}>
                <td>{l.name}</td><td className="n">{l.headcount}</td><td className="n">{l.days}</td>
                <td className="n">{money(l.day_rate, c)}</td><td className="n">{money(l.cost, c)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td>Subtotal</td><td /><td className="n">{est.lines.reduce((a, l) => a + l.days, 0)}</td><td /><td className="n">{money(est.subtotal, c)}</td></tr>
            <tr><td>Contingency {est.contingency_pct}%</td><td /><td /><td /><td className="n">{money(est.total - est.subtotal, c)}</td></tr>
            <tr><td>Total</td><td /><td /><td /><td className="n">{money(est.total, c)}</td></tr>
          </tfoot>
        </table>
      </div>

      <div className="gantt" aria-label="Timeline">
        {est.phases.map((p) => (
          <div className="gantt-row" key={p.name}>
            <span>{p.name}</span>
            <div className="gbar">
              <span
                className={p.name.startsWith('QA') || p.name === 'Launch' ? 'alt' : ''}
                style={{ left: `${(p.start_week / W) * 100}%`, width: `${(p.weeks / W) * 100}%` }}
              />
            </div>
          </div>
        ))}
        <div className="gscale">
          {Array.from({ length: W + 1 }, (_, i) => (
            <span key={i}>{i % 2 === 0 || i === W ? `W${i}` : ''}</span>
          ))}
        </div>
      </div>

      {est.risks.length > 0 && (
        <>
          <span className="label" style={{ marginTop: 18 }}>Delivery risks</span>
          <ul className="risks">{est.risks.map((r) => <li key={r}>{r}</li>)}</ul>
        </>
      )}
      <p className="assume">{est.assumptions.join(' ')}</p>
    </div>
  );
}
