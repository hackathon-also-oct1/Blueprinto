import { useState } from 'react';

import { money } from '../estimate';
import type { BlueprintRun, PublishResult, PublishTarget } from '../types';

const STATUS_TEXT: Record<PublishResult['status'], string> = {
  prepared: 'Ready',
  published: 'Published',
  dry_run: 'Dry run (no Miro token on the server)',
  failed: 'Failed',
};

export function PublishPanel({
  run,
  target,
  publish,
  publishing,
  figmaPayload,
  onPublish,
}: {
  run: BlueprintRun | null;
  target: PublishTarget;
  publish: PublishResult | null;
  publishing: boolean;
  figmaPayload: unknown;
  onPublish: (t: PublishTarget) => void;
}) {
  const [copied, setCopied] = useState(false);
  if (!run?.layout) return <div className="empty">After a run, the Publisher prepares a Miro board or Figma file here.</div>;
  const est = run.estimate;
  const isMiro = target === 'miro';

  const copy = async () => {
    const text = JSON.stringify(figmaPayload, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt('Copy the layout JSON', text);
    }
  };

  const shown = publish && publish.target === target ? publish : null;

  return (
    <div>
      <span className="label">{isMiro ? 'Miro board' : 'Figma file'} preview</span>
      <div className="board">
        {run.layout.frames.map((f, i) => (
          <div className="bframe" key={f.screen_id}><b>{f.name}</b>Frame {i + 1} · {f.nodes.length} blocks</div>
        ))}
        {est && (
          <>
            <div className="bframe sticky"><b>Budget</b>{money(est.total, est.currency)}</div>
            <div className="bframe sticky"><b>Timeline</b>{est.weeks} weeks</div>
            <div className="bframe sticky"><b>Team</b>{est.people} people</div>
          </>
        )}
      </div>
      <p className="hint">
        {isMiro
          ? 'Creates one frame per screen, shapes for each block, connectors for the flow and sticky notes for budget, timeline, team and risks.'
          : "Figma's REST API can't create design nodes, so the server prepares layout JSON for the Blueprint Importer plugin (figma-plugin/)."}
      </p>
      <div className="row center">
        <button className="btn ghost" disabled={publishing} onClick={() => onPublish(target)}>
          {publishing ? 'Publishing…' : `Publish to ${isMiro ? 'Miro' : 'Figma'}`}
        </button>
        {shown && (
          <span className={`status ${shown.status}`}>
            {STATUS_TEXT[shown.status]} · {shown.detail}
            {shown.url && (
              <> · <a href={shown.url} target="_blank" rel="noreferrer">Open board</a></>
            )}
          </span>
        )}
        {!isMiro && figmaPayload != null && (
          <button className="btn ghost" onClick={copy}>{copied ? 'Copied' : 'Copy for Figma plugin'}</button>
        )}
      </div>
    </div>
  );
}
