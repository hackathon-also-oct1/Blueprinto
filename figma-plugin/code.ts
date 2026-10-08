// Blueprint Importer — builds wireframe frames in Figma from the layout JSON
// prepared by the Blueprint Studio Publisher agent.

type BlockType =
  | 'header' | 'title' | 'text' | 'input' | 'button' | 'image' | 'cards' | 'list'
  | 'calendar' | 'slots' | 'chart' | 'table' | 'chat' | 'map' | 'avatar' | 'tabbar' | 'upload';

interface LayoutNode { type: BlockType; x: number; y: number; w: number; h: number; label: string }
interface LayoutFrame { screen_id: string; name: string; x: number; y: number; w: number; h: number; nodes: LayoutNode[] }
interface Payload {
  version: number;
  run_id: string;
  title: string;
  device: 'mobile' | 'desktop';
  frames: LayoutFrame[];
  links: [string, string][];
  notes: string[];
}

const GREY: RGB = { r: 0.79, g: 0.81, b: 0.86 };
const DARK: RGB = { r: 0.54, g: 0.57, b: 0.65 };
const PAPER: RGB = { r: 0.98, g: 0.98, b: 0.99 };
const NOTE: RGB = { r: 1, g: 0.95, b: 0.75 };

const LABELS: Record<BlockType, string> = {
  header: '', title: 'Title', text: 'Body text', input: 'Input', button: 'Button', image: 'Image',
  cards: 'Cards', list: 'List', calendar: 'Calendar', slots: 'Time slots', chart: 'Chart',
  table: 'Table', chat: 'Messages', map: 'Map', avatar: 'Avatar', tabbar: 'Tab bar', upload: 'Upload',
};

function solid(color: RGB): SolidPaint[] {
  return [{ type: 'SOLID', color }];
}

function text(content: string, size = 12, color = DARK): TextNode {
  const t = figma.createText();
  t.characters = content;
  t.fontSize = size;
  t.fills = solid(color);
  return t;
}

function block(n: LayoutNode, frameName: string): SceneNode {
  const g = figma.createFrame();
  g.name = n.type;
  g.x = n.x;
  g.y = n.y;
  g.resize(Math.max(1, n.w), Math.max(1, n.h));
  g.cornerRadius = n.type === 'avatar' ? n.w / 2 : n.type === 'header' || n.type === 'tabbar' ? 0 : 6;
  g.fills = n.type === 'button' ? solid(DARK) : n.type === 'header' ? solid(GREY) : [];
  g.strokes = n.type === 'button' || n.type === 'header' ? [] : solid(GREY);
  g.strokeWeight = 1.5;
  if (n.type === 'upload') g.dashPattern = [6, 4];
  const label = text(
    n.type === 'header' ? frameName : LABELS[n.type],
    n.type === 'header' ? 16 : 12,
    n.type === 'button' ? { r: 1, g: 1, b: 1 } : DARK,
  );
  label.x = 12;
  label.y = Math.max(0, (n.h - label.height) / 2);
  g.appendChild(label);
  return g;
}

async function build(payload: Payload): Promise<number> {
  await figma.loadFontAsync({ family: 'Inter', style: 'Regular' });
  const page = figma.currentPage;
  const frames = new Map<string, FrameNode>();
  const origin = figma.viewport.center;

  for (const f of payload.frames) {
    const frame = figma.createFrame();
    frame.name = f.name;
    frame.x = origin.x + f.x;
    frame.y = origin.y + f.y;
    frame.resize(f.w, f.h);
    frame.cornerRadius = payload.device === 'mobile' ? 24 : 8;
    frame.fills = solid(PAPER);
    frame.strokes = solid(GREY);
    for (const n of f.nodes) frame.appendChild(block(n, f.name));
    page.appendChild(frame);
    frames.set(f.screen_id, frame);
  }

  // Prototype links: the first button (or the whole frame) navigates to the next screen.
  for (const [from, to] of payload.links) {
    const src = frames.get(from);
    const dst = frames.get(to);
    if (!src || !dst) continue;
    const trigger = (src.findOne((n) => n.name === 'button') as FrameNode | null) ?? src;
    try {
      await trigger.setReactionsAsync([
        {
          trigger: { type: 'ON_CLICK' },
          actions: [{ type: 'NODE', destinationId: dst.id, navigation: 'NAVIGATE', transition: null }],
        },
      ]);
    } catch (e) {
      console.warn('Could not add prototype link', from, to, e);
    }
  }

  if (payload.notes.length) {
    const note = figma.createFrame();
    note.name = 'Budget, timeline, team';
    note.layoutMode = 'VERTICAL';
    note.itemSpacing = 8;
    note.paddingLeft = note.paddingRight = note.paddingTop = note.paddingBottom = 20;
    note.primaryAxisSizingMode = 'AUTO';
    note.counterAxisSizingMode = 'FIXED';
    note.resize(420, 100);
    note.fills = solid(NOTE);
    note.cornerRadius = 8;
    note.appendChild(text(payload.title, 16, { r: 0.08, g: 0.1, b: 0.15 }));
    for (const line of payload.notes) {
      const t = text(line, 13, { r: 0.08, g: 0.1, b: 0.15 });
      t.layoutAlign = 'STRETCH';
      t.textAutoResize = 'HEIGHT';
      note.appendChild(t);
    }
    const first = payload.frames[0];
    note.x = origin.x + (first?.x ?? 0);
    note.y = origin.y + (first?.h ?? 800) + 120;
    page.appendChild(note);
  }

  const all = [...frames.values()];
  figma.viewport.scrollAndZoomIntoView(all);
  return all.length;
}

figma.showUI(__html__, { width: 420, height: 420 });

figma.ui.onmessage = async (msg: { type: string; json?: string }) => {
  if (msg.type !== 'import' || !msg.json) return;
  try {
    const payload = JSON.parse(msg.json) as Payload;
    if (!Array.isArray(payload.frames)) throw new Error('This JSON has no "frames" list.');
    const count = await build(payload);
    figma.notify(`Imported ${count} screens from ${payload.run_id}`);
    figma.ui.postMessage({ type: 'done', count });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    figma.ui.postMessage({ type: 'error', message });
  }
};
