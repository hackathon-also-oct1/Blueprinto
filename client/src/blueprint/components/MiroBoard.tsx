import type { PublishResult, PublishTarget } from '../types';

/** Board id from the URL the Miro publisher returns (https://miro.com/app/board/{id}/). */
const boardId = (url: string) => url.match(/\/board\/([^/?#]+)/)?.[1] ?? null;

/** The published Miro board, embedded live. Before publishing it offers the Publish button. */
export function MiroBoard({
  ready,
  publish,
  publishing,
  onPublish,
}: {
  ready: boolean;
  publish: PublishResult | null;
  publishing: boolean;
  onPublish: (t: PublishTarget) => void;
}) {
  if (!ready) return null;
  const miro = publish?.target === 'miro' ? publish : null;
  const id = miro?.status === 'published' && miro.url ? boardId(miro.url) : null;

  return (
    <div className="miro">
      <div className="miro-head">
        <span className="label">Miro board</span>
        {id && miro?.url && <a href={miro.url} target="_blank" rel="noreferrer">Open in Miro</a>}
      </div>
      {id ? (
        <iframe
          className="miro-frame"
          title="Miro board"
          src={`https://miro.com/app/live-embed/${id}/?autoplay=true`}
          allow="fullscreen; clipboard-read; clipboard-write"
          allowFullScreen
        />
      ) : (
        <div className="miro-empty">
          <p className="hint">
            {miro?.status === 'dry_run' || miro?.status === 'failed'
              ? miro.detail
              : 'Publish the wireframes to see the Miro board here.'}
          </p>
          <button className="btn ghost" disabled={publishing} onClick={() => onPublish('miro')}>
            {publishing ? 'Publishing…' : 'Publish to Miro'}
          </button>
        </div>
      )}
    </div>
  );
}
