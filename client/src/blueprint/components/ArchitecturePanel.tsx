const LAYERS = [
  {
    title: 'Frontend',
    items: [
      ['React + TypeScript (Vite)', 'hosted on Azure Static Web Apps'],
      ['Pipecat client SDK', 'SmallWebRTC transport, RTVI messages'],
      ['Microsoft Entra ID', 'sign-in (Static Web Apps auth)'],
    ],
  },
  {
    title: 'Agent pipeline',
    items: [
      ['Pipecat', 'one FrameProcessor per agent, frames hand off the run'],
      ['Azure OpenAI', 'structured JSON output for each agent'],
      ['Azure Container Apps', 'runs the Pipecat server'],
    ],
  },
  {
    title: 'Voice & avatar',
    items: [
      ['Azure AI Speech', 'narrator voice (TTS)'],
      ['Anam', 'video avatar via Pipecat, optional'],
    ],
  },
  {
    title: 'Data & ops',
    items: [
      ['Azure Cosmos DB', 'run history and past estimates'],
      ['Azure Key Vault', 'Azure OpenAI and speech keys'],
      ['Application Insights', 'logs and traces'],
    ],
  },
];

export function ArchitecturePanel() {
  return (
    <div className="arch">
      {LAYERS.map((l) => (
        <div className="layer" key={l.title}>
          <h3>{l.title}</h3>
          <ul>
            {l.items.map(([name, what]) => (
              <li key={name}><code>{name}</code> {what}</li>
            ))}
          </ul>
        </div>
      ))}
      <pre className="flowtext">{`browser ──RTVI client message──▶ Orchestrator
  ▲                                   │ BlueprintRunFrame
  │                                   ▼
  │            Requirements Analyst → UX Architect → Wireframe Builder
  │                                   → Narrator
  │                                                              │
  └──── RTVI server messages (status, logs, results) ◀───────────┤
                      Azure TTS → avatar → WebRTC audio/video ◀──┘`}</pre>
    </div>
  );
}
