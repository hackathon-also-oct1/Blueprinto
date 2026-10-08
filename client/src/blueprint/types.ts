/** Types mirroring server/blueprint/models.py and the RTVI server messages. */

export type Platform = 'web' | 'mobile' | 'both';
export type PublishTarget = 'miro' | 'figma';
export type AgentStatus = 'idle' | 'working' | 'done' | 'error';

export type BlockType =
  | 'header' | 'title' | 'text' | 'input' | 'button' | 'image' | 'cards' | 'list'
  | 'calendar' | 'slots' | 'chart' | 'table' | 'chat' | 'map' | 'avatar' | 'tabbar' | 'upload';

export type PageCategory = 'home' | 'about' | 'services' | 'service_detail' | 'contact' | 'error_404';

export interface RunRequest {
  requirement: string;
  platform: Platform;
  target: PublishTarget;
  currency: string;
}

export interface Screen {
  id: string;
  name: string;
  purpose: string;
  persona: string;
  blocks: BlockType[];
  links_to: string[];
  category?: PageCategory | null;
}

export interface LayoutNode {
  type: BlockType;
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
}

export interface LayoutFrame {
  screen_id: string;
  name: string;
  x: number;
  y: number;
  w: number;
  h: number;
  nodes: LayoutNode[];
  category?: PageCategory | null;
  /** Reference screenshot path inside screenshots/ ("<domain>/<file>"), shown instead of the blocks. */
  screenshot?: string | null;
}

export interface Layout {
  device: 'mobile' | 'desktop';
  frames: LayoutFrame[];
  links: [string, string][];
  reference_set?: string | null;
  reference_name?: string;
  reference_domain?: string;
}

export interface RoleLine {
  role_id: string;
  name: string;
  headcount: number;
  days: number;
  day_rate: number;
  cost: number;
}

export interface Phase {
  name: string;
  start_week: number;
  weeks: number;
}

export interface Estimate {
  currency: string;
  screens: { screen_id: string; complexity: 'S' | 'M' | 'L'; fe_days: number; be_days: number }[];
  lines: RoleLine[];
  subtotal: number;
  contingency_pct: number;
  total: number;
  low: number;
  high: number;
  weeks: number;
  people: number;
  fte: number;
  phases: Phase[];
  risks: string[];
  assumptions: string[];
}

export interface PublishResult {
  target: PublishTarget;
  status: 'prepared' | 'published' | 'dry_run' | 'failed';
  url?: string | null;
  detail: string;
  items_created: number;
}

export interface DomainMatch {
  domain: string;
  name: string;
  reference_set: string;
  score: number;
  confidence: number;
  matched: string[];
  fallback: boolean;
}

export interface BlueprintRun {
  run_id: string;
  created_at: string;
  request: RunRequest;
  domain?: DomainMatch | null;
  spec: {
    summary: string;
    personas: string[];
    features: { name: string; description: string; priority: string }[];
    non_functional: string[];
  } | null;
  flow: { screens: Screen[] } | null;
  layout: Layout | null;
  estimate: Estimate | null;
  publish: PublishResult | null;
  error: string | null;
  tokens: number;
}

export interface AgentInfo {
  id: string;
  title: string;
  service: string;
}

export interface AgentState extends AgentInfo {
  status: AgentStatus;
  note?: string;
  duration_ms?: number;
  tokens?: number;
}

export interface LogLine {
  at: string;
  agent: string;
  message: string;
}

/** Messages the server sends with RTVIServerMessageFrame. */
export type ServerMessage =
  | { type: 'session_ready'; mock: boolean; voice: boolean; avatar: boolean; conversation?: boolean }
  | { type: 'avatar_unavailable'; reason: string }
  | { type: 'run_started'; run_id: string; mock: boolean; agents: AgentInfo[]; requirement?: string }
  | {
      type: 'agent_status';
      run_id: string;
      agent: string;
      status: AgentStatus;
      note?: string;
      duration_ms?: number;
      tokens?: number;
    }
  | { type: 'agent_log'; run_id: string; agent: string; message: string }
  | { type: 'wireframes'; run_id: string; flow: { screens: Screen[] }; layout: Layout }
  | { type: 'run_result'; run: BlueprintRun }
  | { type: 'run_error'; run_id: string | null; error: string }
  | {
      type: 'publish_result';
      run_id: string;
      publish: PublishResult;
      figma_payload?: unknown;
    };
