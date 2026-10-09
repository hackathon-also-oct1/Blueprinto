import { usePipecatClientTransportState } from '@pipecat-ai/client-react';
import { useState } from 'react';

import { AgentTimeline } from './components/AgentTimeline';
import { ArchitecturePanel } from './components/ArchitecturePanel';
import { AvatarPanel } from './components/AvatarPanel';
import { ConversationPanel } from './components/ConversationPanel';
import { KpiRow } from './components/EstimatePanel';
import { Wireframes } from './components/Wireframes';
import type { Blueprint } from './useBlueprint';
import type { ChatMessage } from './useConversation';

type Tab = 'wf' | 'arch';
const TABS: [Tab, string][] = [
  ['wf', 'Wireframes'],
  ['arch', 'Microsoft architecture'],
];

/** The agent orchestration page: presenter and brief on the left, the agent run in the middle, deliverables on the right. */
export function Studio({ blueprint, messages, draft, manual: typed, connect, disconnect, error, onBack }: {
  blueprint: Blueprint;
  messages: ChatMessage[];
  /** A brief carried over from the site, e.g. a sentence typed on the landing page. */
  draft: string;
  /** Start with the brief form rather than the conversation. */
  manual: boolean;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  error: string | null;
  onBack: () => void;
}) {
  const transport = usePipecatClientTransportState();
  const connected = transport === 'ready' || transport === 'connected';
  const connecting = ['initializing', 'authenticating', 'authenticated', 'connecting'].includes(transport);
  const { state, run } = blueprint;

  const [requirement, setRequirement] = useState(draft);
  const [tab, setTab] = useState<Tab>('wf');

  // With the voice agent on, the left pane is a chat until "build it" produces a
  // requirement (or the user chooses to type one); then the requirement takes its place.
  const [manual, setManual] = useState(typed);
  const showChat = !!state.session?.conversation && !state.requirement && !manual;

  // A run started by voice: show what the presenter understood, on the wireframes tab.
  const [seenRun, setSeenRun] = useState<string | null>(null);
  if (state.runId && state.runId !== seenRun) {
    setSeenRun(state.runId);
    if (state.requirement) setRequirement(state.requirement);
    setTab('wf');
  }

  const onRun = () => {
    setTab('wf');
    run({ requirement, platform: 'web', currency: 'EUR' });
  };

  return (
    <div className="studio">
      <header className="top">
        <div>
          <button type="button" className="crumb" onClick={onBack}>← Back to the site</button>
          <h1>Blueprinto</h1>
          <p>Describe the website you have in mind, by voice or by typing. Blueprinto sketches the pages for you.</p>
        </div>
        <div className="row center">
          {state.session?.mock && <span className="badge warn">Mock mode · no Azure OpenAI key</span>}
          <span className={`badge ${connected ? 'ok' : ''}`}>{connected ? 'Connected' : transport}</span>
          <button className="btn ghost" onClick={() => (connected ? disconnect() : connect())} disabled={connecting}>
            {connected ? 'Disconnect' : connecting ? 'Connecting…' : 'Connect'}
          </button>
        </div>
      </header>
      {error && <div className="alert">{error} — is the server running on port 7860?</div>}
      {state.error && <div className="alert">{state.error}</div>}

      <main className="grid">
        <section className="pane stack" aria-label="Requirement">
          <AvatarPanel
            enabled={!!state.session?.avatar}
            voice={!!state.session?.voice}
            conversation={!!state.session?.conversation}
            issue={state.avatarIssue}
          />
          {showChat ? (
            <ConversationPanel messages={messages} onType={() => setManual(true)} />
          ) : (
            <>
              <div>
                <label className="label" htmlFor="req">Requirement</label>
                <textarea
                  id="req"
                  value={requirement}
                  placeholder="Filled in when the presenter has your brief. You can also type one here."
                  onChange={(e) => setRequirement(e.target.value)}
                />
              </div>
              <button className="btn" onClick={onRun} disabled={!connected || state.running || requirement.trim().length < 10}>
                {state.running ? 'Agents working…' : connected ? 'Run agents' : 'Connect to run'}
              </button>
            </>
          )}
        </section>

        <AgentTimeline agents={state.agents} log={state.log} runId={state.runId} />

        <section className="pane out" aria-label="Deliverables">
          <div className="tabs" role="tablist">
            {TABS.map(([id, label]) => (
              <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
                {label}
              </button>
            ))}
          </div>
          {tab === 'wf' && (
            <>
              {state.kpis && state.layout && <KpiRow est={state.kpis} screens={state.layout.frames.length} />}
              <Wireframes layout={state.layout} screens={state.screens} running={state.running} />
            </>
          )}
          {tab === 'arch' && <ArchitecturePanel />}
        </section>
      </main>
    </div>
  );
}
