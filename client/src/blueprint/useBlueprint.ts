import { RTVIEvent } from '@pipecat-ai/client-js';
import { usePipecatClient, useRTVIClientEvent } from '@pipecat-ai/client-react';
import { useCallback, useReducer } from 'react';

import type {
  AgentInfo,
  AgentState,
  BlueprintRun,
  Estimate,
  Layout,
  LogLine,
  RunRequest,
  Screen,
  ServerMessage,
} from './types';

/** Shown before the first run so the agent view is never empty. */
export const DEFAULT_AGENTS: AgentInfo[] = [
  { id: 'orch', title: 'Orchestrator', service: 'Pipecat pipeline · Azure Container Apps' },
  { id: 'dom', title: 'Domain Classifier', service: 'Rules engine · weighted keywords' },
  { id: 'req', title: 'Requirements Analyst', service: 'Azure OpenAI · structured output' },
  { id: 'ux', title: 'UX Architect', service: 'Azure OpenAI · pattern library' },
  { id: 'wf', title: 'Wireframe Builder', service: 'Layout engine · 390×844 / 1280×800 frames' },
];

export interface BlueprintState {
  session: { mock: boolean; voice: boolean; avatar: boolean; conversation: boolean } | null;
  /** Why the video presenter is missing although it is configured. */
  avatarIssue: string | null;
  runId: string | null;
  /** Requirement of the current run; set by the server, so it covers spoken ones too. */
  requirement: string | null;
  running: boolean;
  agents: AgentState[];
  log: LogLine[];
  screens: Screen[];
  layout: Layout | null;
  run: BlueprintRun | null;
  /** Budget, timeline and team shown above the wireframes. */
  kpis: Estimate | null;
  error: string | null;
}

const idle = (agents: AgentInfo[]): AgentState[] =>
  agents.map((a) => ({ ...a, status: 'idle' as const }));

const initial: BlueprintState = {
  session: null,
  avatarIssue: null,
  runId: null,
  requirement: null,
  running: false,
  agents: idle(DEFAULT_AGENTS),
  log: [],
  screens: [],
  layout: null,
  run: null,
  kpis: null,
  error: null,
};

type Action =
  | { type: 'message'; msg: ServerMessage }
  | { type: 'run_requested' };

const now = () => new Date().toTimeString().slice(0, 8);

function reducer(state: BlueprintState, action: Action): BlueprintState {
  if (action.type === 'run_requested') {
    return { ...state, running: true, error: null, log: [] };
  }

  const msg = action.msg;
  switch (msg.type) {
    case 'session_ready':
      return {
        ...state,
        avatarIssue: null,
        session: { mock: msg.mock, voice: msg.voice, avatar: msg.avatar, conversation: !!msg.conversation },
      };
    case 'avatar_unavailable':
      return {
        ...state,
        session: state.session && { ...state.session, avatar: false },
        avatarIssue: msg.reason,
      };
    case 'run_started':
      return {
        ...state,
        runId: msg.run_id,
        requirement: msg.requirement ?? state.requirement,
        running: true,
        // A run the presenter started never went through run_requested, so reset here too.
        error: null,
        log: [],
        agents: idle(msg.agents),
        screens: [],
        layout: null,
        run: null,
        kpis: null,
      };
    case 'agent_status':
      return {
        ...state,
        agents: state.agents.map((a) =>
          a.id === msg.agent
            ? {
                ...a,
                status: msg.status,
                note: msg.note ?? a.note,
                duration_ms: msg.duration_ms ?? a.duration_ms,
                tokens: msg.tokens ?? a.tokens,
              }
            : a,
        ),
      };
    case 'agent_log':
      return {
        ...state,
        log: [...state.log, { at: now(), agent: msg.agent, message: msg.message }].slice(-200),
      };
    case 'wireframes':
      return { ...state, screens: msg.flow?.screens ?? [], layout: msg.layout };
    case 'run_result':
      return {
        ...state,
        running: false,
        run: msg.run,
        kpis: msg.kpis ?? null,
        screens: msg.run.flow?.screens ?? state.screens,
        layout: msg.run.layout ?? state.layout,
        error: msg.run.error,
      };
    case 'run_error':
      return { ...state, running: false, error: msg.error };
    default:
      return state;
  }
}

/** Talks to the Pipecat bot: sends client messages, folds server messages into state. */
export function useBlueprint() {
  const client = usePipecatClient();
  const [state, dispatch] = useReducer(reducer, initial);

  useRTVIClientEvent(RTVIEvent.ServerMessage, (data: ServerMessage) => {
    if (data && typeof data === 'object' && 'type' in data) dispatch({ type: 'message', msg: data });
  });

  const run = useCallback(
    (request: RunRequest) => {
      if (!client) return;
      dispatch({ type: 'run_requested' });
      client.sendClientMessage('run_blueprint', request);
    },
    [client],
  );

  return { state, run };
}

/** What `useBlueprint` returns; the studio takes it as a prop so the session outlives the page. */
export type Blueprint = ReturnType<typeof useBlueprint>;
