import { PipecatClientAudio, usePipecatClientTransportState } from '@pipecat-ai/client-react';
import { useEffect, useState } from 'react';

import { AgentTimeline } from './components/AgentTimeline';
import { ArchitecturePanel } from './components/ArchitecturePanel';
import { AvatarPanel } from './components/AvatarPanel';
import { EstimatePanel, KpiRow } from './components/EstimatePanel';
import { MiroBoard } from './components/MiroBoard';
import { PublishPanel } from './components/PublishPanel';
import { Wireframes } from './components/Wireframes';
import type { Platform, PublishTarget } from './types';
import { useBlueprint } from './useBlueprint';

const SAMPLE =
  'A booking app for a physiotherapy clinic. Patients sign in, browse therapists, book and pay for appointments, get SMS reminders, and chat with the clinic. Admins see a dashboard with revenue and utilization reports.';

type Tab = 'wf' | 'est' | 'pub' | 'arch';
const TABS: [Tab, string][] = [
  ['wf', 'Wireframes'],
  ['est', 'Budget & team'],
  ['pub', 'Publish'],
  ['arch', 'Microsoft architecture'],
];

export function Studio({ connect, disconnect, error }: {
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  error: string | null;
}) {
  const transport = usePipecatClientTransportState();
  const connected = transport === 'ready' || transport === 'connected';
  const connecting = ['initializing', 'authenticating', 'authenticated', 'connecting'].includes(transport);
  const { state, run, publish } = useBlueprint();

  const [requirement, setRequirement] = useState(SAMPLE);
  const [platform, setPlatform] = useState<Platform>('both');
  const [target, setTarget] = useState<PublishTarget>('miro');
  const [tab, setTab] = useState<Tab>('wf');

  const estimate = state.run?.estimate ?? null;

  // A run started by voice: show what the presenter understood, and the wireframes tab.
  useEffect(() => {
    if (!state.runId || !state.requirement) return;
    setRequirement(state.requirement);
    setTab('wf');
  }, [state.runId, state.requirement]);

  const onRun = () => {
    setTab('wf');
    run({ requirement, platform, target, currency: 'EUR' });
  };

  return (
    <div className="studio">
      <header className="top">
        <div>
          <h1>Blueprinto</h1>
          <p>Describe the website you have in mind, by voice or by typing. Blueprinto sketches the pages for you, estimates the budget, timeline and team you need, and can share the result to Miro or Figma.</p>
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
          <div>
            <label className="label" htmlFor="req">Requirement</label>
            <textarea id="req" value={requirement} onChange={(e) => setRequirement(e.target.value)} />
          </div>
          <label className="field">
            <span>Platform</span>
            <select id="platform" value={platform} onChange={(e) => setPlatform(e.target.value as Platform)}>
              <option value="web">Web (TypeScript SPA)</option>
              <option value="mobile">Mobile</option>
              <option value="both">Web + mobile</option>
            </select>
          </label>
          <div>
            <span className="label">Publish to</span>
            <div className="seg" role="group" aria-label="Publish target">
              {(['miro', 'figma'] as const).map((t) => (
                <button key={t} type="button" aria-pressed={target === t} onClick={() => setTarget(t)}>
                  {t === 'miro' ? 'Miro' : 'Figma'}
                </button>
              ))}
            </div>
          </div>
          <button className="btn" onClick={onRun} disabled={!connected || state.running || requirement.trim().length < 10}>
            {state.running ? 'Agents working…' : connected ? 'Run agents' : 'Connect to run'}
          </button>
          <AvatarPanel
            enabled={!!state.session?.avatar}
            voice={!!state.session?.voice}
            conversation={!!state.session?.conversation}
            issue={state.avatarIssue}
          />
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
              {estimate && state.layout && <KpiRow est={estimate} screens={state.layout.frames.length} />}
              <Wireframes layout={state.layout} screens={state.screens} running={state.running} />
              <MiroBoard
                ready={!!state.run?.layout}
                publish={state.publish}
                publishing={state.publishing}
                onPublish={publish}
              />
            </>
          )}
          {tab === 'est' && <EstimatePanel est={estimate} />}
          {tab === 'pub' && (
            <PublishPanel
              run={state.run}
              target={target}
              publish={state.publish}
              publishing={state.publishing}
              figmaPayload={state.figmaPayload}
              onPublish={publish}
            />
          )}
          {tab === 'arch' && <ArchitecturePanel />}
        </section>
      </main>
      <PipecatClientAudio />
    </div>
  );
}
