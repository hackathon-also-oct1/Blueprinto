import { screenshotUrl } from '../references';
import type { Layout, LayoutFrame, LayoutNode, PageCategory, Screen } from '../types';

const PREVIEW_WIDTH = { mobile: 168, desktop: 360 };

const CATEGORY_LABEL: Record<PageCategory, string> = {
  home: 'Home page',
  about: 'About us',
  services: 'Services',
  service_detail: 'Detail',
  contact: 'Contact',
  error_404: 'Error 404',
};

function Block({ node, scale }: { node: LayoutNode; scale: number }) {
  const style = {
    left: node.x * scale,
    top: node.y * scale,
    width: node.w * scale,
    height: node.h * scale,
  };
  let inner: React.ReactNode = null;
  switch (node.type) {
    case 'cards':
    case 'slots':
      inner = (
        <div className="wf-grid">
          {Array.from({ length: node.type === 'cards' ? 4 : 6 }, (_, i) => (
            <span key={i} />
          ))}
        </div>
      );
      break;
    case 'list':
    case 'table':
      inner = Array.from({ length: Math.max(2, Math.floor((node.h * scale) / 16)) }, (_, i) => (
        <div className="wf-row" key={i}>
          {node.type === 'list' && <i />}
          <b style={{ width: `${55 + ((i * 17) % 35)}%` }} />
        </div>
      ));
      break;
    case 'calendar':
      inner = (
        <div className="wf-cal">
          {Array.from({ length: 28 }, (_, i) => (
            <span key={i} className={i === 17 ? 'on' : ''} />
          ))}
        </div>
      );
      break;
    case 'chart':
      inner = (
        <div className="wf-chart">
          {[40, 65, 50, 80, 70, 95, 60].map((h, i) => (
            <span key={i} style={{ height: `${h}%` }} />
          ))}
        </div>
      );
      break;
    case 'chat':
      inner = (
        <div className="wf-chat">
          {[0, 1, 0, 1, 0, 1].map((me, i) => (
            <span key={i} className={me ? 'me' : ''} style={{ width: `${45 + i * 6}%` }} />
          ))}
        </div>
      );
      break;
    case 'tabbar':
      inner = (
        <div className="wf-tabs">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} />
          ))}
        </div>
      );
      break;
  }
  return (
    <div className={`wf wf-${node.type}`} style={style} title={node.type}>
      {inner}
    </div>
  );
}

function Frame({ frame, device, index }: { frame: LayoutFrame; device: Layout['device']; index: number }) {
  const shot = screenshotUrl(frame.screenshot);
  if (shot && frame.category) {
    // Reference screenshots are desktop captures, so they use the desktop preview width.
    return (
      <figure className="wf-screen">
        <a className="wf-frame wf-desktop wf-shot" href={shot} target="_blank" rel="noreferrer"
          style={{ width: PREVIEW_WIDTH.desktop }}>
          <img src={shot} alt={`${frame.name}: reference design (${CATEGORY_LABEL[frame.category]})`} loading="lazy" />
        </a>
        <figcaption>
          {frame.name}
          <small>{String(index + 1).padStart(2, '0')} · {CATEGORY_LABEL[frame.category]} reference</small>
        </figcaption>
      </figure>
    );
  }
  const width = PREVIEW_WIDTH[device];
  const scale = width / frame.w;
  return (
    <figure className="wf-screen">
      <div
        className={`wf-frame wf-${device}`}
        style={{ width, height: frame.h * scale }}
        aria-label={`${frame.name} wireframe`}
      >
        {frame.nodes.map((n, i) => (
          <Block key={i} node={n} scale={scale} />
        ))}
      </div>
      <figcaption>
        {frame.name}
        <small>{String(index + 1).padStart(2, '0')} · {frame.nodes.length} blocks</small>
      </figcaption>
    </figure>
  );
}

export function Wireframes({
  layout,
  screens,
  running,
}: {
  layout: Layout | null;
  screens: Screen[];
  running: boolean;
}) {
  if (!layout) {
    return (
      <div className="empty">
        {running
          ? 'The UX Architect and Wireframe Builder are working on the flow…'
          : 'Type a requirement and press Run agents. The screen flow appears here.'}
      </div>
    );
  }
  const personas = [...new Set(screens.map((s) => s.persona).filter(Boolean))];
  return (
    <div>
      <span className="label">
        User flow · {layout.frames.length} screens · {layout.device}
        {layout.reference_set
          ? ` · domain ${layout.reference_domain} · reference ${layout.reference_set} (${layout.reference_name})`
          : ''}
        {personas.length ? ` · personas: ${personas.join(', ')}` : ''}
      </span>
      <div className="wf-flow">
        {layout.frames.map((f, i) => (
          <div className="wf-step" key={f.screen_id}>
            {i > 0 && <span className="wf-arrow" aria-hidden="true">→</span>}
            <Frame frame={f} device={layout.device} index={i} />
          </div>
        ))}
      </div>
    </div>
  );
}
