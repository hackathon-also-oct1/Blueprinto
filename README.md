# Blueprint Studio

Type a product requirement into a text box. Six agents, running as a **Pipecat** pipeline on
**Microsoft Azure**, turn it into:

- a UX flow and **wireframes** (mobile 390×844 or desktop 1280×800 frames),
- a **budget**, **timeline** and **team plan** (per-role person-days, day rates, contingency, Gantt),
- a **Miro board** or **Figma file** with the flow, plus sticky notes for budget, timeline, team and risks.

The browser shows every agent working live: status, duration, tokens and a streaming activity log.
A narrator voice (Azure AI Speech) and a **video avatar** (Anam) can be switched
on later without changing the pipeline.

```
blueprint-studio/
├── server/                     Python · Pipecat 1.12 (scaffolded with `pipecat init`)
│   ├── bot.py                  entry point: builds the pipeline per browser session
│   ├── blueprint/
│   │   ├── pipeline.py         assembles the agent chain
│   │   ├── agents/             one Pipecat FrameProcessor per agent
│   │   │   ├── orchestrator.py   client messages → runs
│   │   │   ├── requirements.py   Requirements Analyst  (Azure OpenAI)
│   │   │   ├── ux_architect.py   UX Architect          (Azure OpenAI + pattern catalog)
│   │   │   ├── wireframe.py      Wireframe Builder     (deterministic layout engine)
│   │   │   ├── estimator.py      Estimator             (Azure OpenAI + cost model)
│   │   │   ├── publisher.py      Publisher             (Miro REST API / Figma plugin JSON)
│   │   │   └── narrator.py       saves the run, sends results, speaks the summary
│   │   ├── publishers/         miro.py, figma.py
│   │   ├── azure_llm.py        Azure OpenAI (v1 API) structured-output wrapper + mock mode
│   │   ├── catalog.py          screen patterns, effort table, heuristics
│   │   ├── storage.py          runs in local JSON or Azure Cosmos DB
│   │   ├── avatar.py           optional video avatar (off by default)
│   │   ├── frames.py           custom Pipecat frames
│   │   └── models.py           pydantic models shared by all agents
│   ├── tests/test_pipeline.py  end-to-end pipeline test (mock mode)
│   ├── pyproject.toml  .env.example  Dockerfile
├── client/                     TypeScript · React 19 · Vite · Pipecat client SDK
│   └── src/
│       ├── App.tsx             Pipecat client + provider (SmallWebRTC)
│       ├── blueprint/          the studio UI
│       │   ├── Studio.tsx        layout, requirement form, tabs
│       │   ├── useBlueprint.ts   sends client messages, folds server messages into state
│       │   ├── types.ts          mirrors server models and messages
│       │   ├── estimate.ts       currency formatting
│       │   └── components/       AgentTimeline, Wireframes, EstimatePanel, PublishPanel, …
│       ├── components/pipecat/ scaffold's Pipecat UI kit (console, transcript, metrics)
│       └── hooks/              scaffold's usePipecatApp and friends
├── figma-plugin/               "Blueprint Importer" Figma plugin (TypeScript)
├── AGENTS.md / CLAUDE.md       Pipecat's guide for coding agents (from the scaffold)
└── README.md
```

> **About the reference repo.** `arnabdeypolimi/hackbarna_2026` was not readable from here (it
> appears to be private). This project follows the layout that `pipecat init` generates
> (`server/` + `client/`), which is the standard Pipecat structure. If your repo differs (folder
> names, extra services), share it and the structure can be aligned.

## How the agents work

Pipecat moves **frames** through a pipeline of **processors**. Each agent is a processor:

```
transport.input()
  → Orchestrator → Requirements Analyst → UX Architect → Wireframe Builder
  → Estimator → Publisher → Narrator
  → Azure TTS (optional) → video avatar (optional)
  → transport.output()
```

1. The browser sends the requirement as an RTVI client message:
   `client.sendClientMessage('run_blueprint', {...})`.
2. The **Orchestrator** validates it and pushes a `BlueprintRunFrame` carrying a `BlueprintRun`.
3. Each agent fills in its part of the run (`spec`, `flow`, `layout`, `estimate`, `publish`) and
   pushes the frame on. That push is the hand-off.
4. While working, every agent pushes `RTVIServerMessageFrame`s (`agent_status`, `agent_log`,
   `wireframes`, `run_result`, `publish_result`). Pipecat's RTVI observer delivers them to the
   browser over the WebRTC data channel, which drives the live agent view.
5. The **Narrator** saves the run and, when a speech key is set, pushes a `TTSSpeakFrame` with a
   spoken summary. Azure TTS voices it, and the avatar (if enabled) lip-syncs it.
6. Publishing is a separate, explicit step: `client.sendClientMessage('publish', {run_id, target})`.

The LLM agents return **structured JSON** validated with pydantic (one automatic retry on invalid
output). Budget numbers come from a deterministic cost model, not the LLM: the Estimator's LLM only
rates each screen S/M/L and lists risks, so the same inputs always give the same budget.

**Mock mode.** With no Azure OpenAI key, agents fall back to heuristics (`catalog.py`), so you can
run the whole app, UI included, with zero credentials.

## Run it locally

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
cp server/.env.example server/.env   # fill in keys, or leave empty for mock mode
npm run setup                        # once: installs server and client dependencies
npm run dev                          # server on :7860 and client on http://localhost:5173
```

`npm run dev` runs both in one terminal; Ctrl+C stops both. To run one side alone, use
`npm run dev:server` or `npm run dev:client`.

The client connects automatically, then **Run agents** starts a run. Set `VITE_BOT_START_URL`
in `client/.env` if the server is not on `http://localhost:7860/start`.

Tests (mock mode, no keys needed):

```bash
cd server && uv run pytest -q
```

## Configuration

All settings live in `server/.env` (see `.env.example`).

| What | Variables | Notes |
|---|---|---|
| Agents (Azure OpenAI) | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` | Endpoint of your Azure OpenAI / AI Foundry resource. Uses the v1 API surface. |
| Voice agent | `SLNG_API_KEY`, `SLNG_STT_MODEL` plus the Azure OpenAI settings | With both, the presenter listens on the mic (SLNG speech to text), talks back, and starts the agents from a spoken requirement. The deployment is called through the Responses API. Typing still works. |
| Narrator voice (SLNG) | `SLNG_API_KEY`, `SLNG_WORLD_PART`, `SLNG_TTS_MODEL`, `SLNG_TTS_VOICE` | Optional. Cartesia Sonic 3 through the SLNG gateway (`pipecat-slng`). Used when the key is set. |
| Narrator voice (Azure) | `AZURE_SPEECH_API_KEY`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_VOICE_ID` | Optional fallback when no SLNG key is set. Without either there is no audio. |
| Run history | `COSMOS_ENDPOINT`, `COSMOS_KEY` (or managed identity) | Optional, `uv sync --extra cosmos`. Defaults to JSON files in `server/runs/`. |
| Miro | `MIRO_ACCESS_TOKEN`, `MIRO_BOARD_ID` | Token needs `boards:write`. Without it Publish is a dry run. Empty board id creates a new board. |
| Avatar | `AVATAR_PROVIDER`, `ANAM_API_KEY`, `ANAM_AVATAR_ID` | Off by default, see below. |

## Publishing

**Miro.** The Publisher creates one frame per screen, a shape for every wireframe block (as
children of the frame), connectors between frames for the flow, and sticky notes for budget,
timeline, team and risks. Miro positions items by their centre; child items are sent relative to
the frame's top-left. If shapes land in the wrong place on your board, flip `CHILD_RELATIVE` in
`server/blueprint/publishers/miro.py`.

**Figma.** Figma's REST API can read files but cannot create design nodes, so writing goes through
a plugin:

```bash
cd figma-plugin && npm install && npm run build
```

In Figma desktop: *Plugins → Development → Import plugin from manifest…* and pick
`figma-plugin/manifest.json`. In Blueprint Studio choose **Figma**, press **Publish**, then
**Copy for Figma plugin**, and paste into the plugin. It builds the frames, prototype links between
screens, and a notes card with budget, timeline, team and risks.

## Adding the video avatar later

The pipeline already ends `… → Narrator → TTS → avatar → transport.output()`, and the client
already renders the bot's video track (`AvatarPanel.tsx`). To turn it on with **Anam**,
through Anam's `pipecat-anam` plugin (pick an avatar and create an API key at
[lab.anam.ai](https://lab.anam.ai)):

```bash
cd server
uv sync --extra anam
# .env
AZURE_SPEECH_API_KEY=...      # the avatar lip-syncs the narrator's voice
AVATAR_PROVIDER=anam
ANAM_API_KEY=...
ANAM_AVATAR_ID=...            # the avatar's id, not a persona id
```

Restart the server. The transport switches on video output (720×480) automatically and the
presenter appears in the left column.

For **Tavus** or **HeyGen**, add a branch in `server/blueprint/avatar.py` using Pipecat's
`TavusVideoService` or `HeyGenVideoService`. Both need an `aiohttp.ClientSession` for the
session's lifetime. To let the avatar also *listen* (talk to it about the estimate), add Azure STT
plus an `AzureLLMService` with a context aggregator in front of the Narrator, as in the cascade
template `pipecat init` generates.

## Deploying on Azure

| Piece | Azure service |
|---|---|
| Pipecat server (`server/Dockerfile`) | Azure Container Apps (min replicas 1, sticky sessions, port 7860) |
| Client (`npm run build` → `client/dist`) | Azure Static Web Apps, with Entra ID sign-in |
| Agents' model | Azure OpenAI deployment in Azure AI Foundry |
| Narrator voice | Azure AI Speech |
| Run history | Azure Cosmos DB (serverless is fine) |
| Secrets (Azure keys, Miro token) | Azure Key Vault, referenced as Container Apps secrets |
| Logs and traces | Application Insights (Container Apps log analytics) |

Sketch:

```bash
az group create -n rg-blueprint -l westeurope
az acr create -g rg-blueprint -n <acr> --sku Basic
az acr build -r <acr> -t blueprint-server:latest server/
az containerapp up -g rg-blueprint -n blueprint-server \
  --image <acr>.azurecr.io/blueprint-server:latest --ingress external --target-port 7860 \
  --env-vars AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_DEPLOYMENT=... \
  --secrets ... # or Key Vault references
```

Then build the client with `VITE_BOT_START_URL=https://<container-app-fqdn>/start` and deploy
`client/dist` to Static Web Apps.

WebRTC through cloud NAT usually needs a TURN server. For production, either add TURN credentials
to the SmallWebRTC ICE config, or switch the transport to Daily (`pipecat init` can add it with
`-t daily`) and keep everything else unchanged.

## Extending

- **New agent**: subclass `AgentProcessor` (`agents/base.py`), implement `run()`, add it to
  `build_agent_chain()` and to `DEFAULT_AGENTS` in `client/src/blueprint/useBlueprint.ts`.
- **Parallel agents**: Wireframe Builder and Estimator only depend on the UX flow. Pipecat's
  `ParallelPipeline` can run them side by side if runs get slow.
- **Grounded estimates**: the Estimator is labelled "Cosmos DB history". Past runs are already
  stored there; feed the closest ones into its prompt (or index them in Azure AI Search) to
  calibrate complexity ratings against your own delivery data.
- **Text conversation**: the scaffold's developer console (`src/components/pipecat/console`) is
  still in the project if you want transcripts and metrics while iterating.
