import { RTVIEvent } from '@pipecat-ai/client-js';
import {
  PipecatClientAudio,
  PipecatClientProvider,
  usePipecatClient,
  usePipecatClientMicControl,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from '@pipecat-ai/client-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Landing } from '@/blueprint/Landing';
import { Studio } from '@/blueprint/Studio';
import type { ServerMessage } from '@/blueprint/types';
import { useBlueprint } from '@/blueprint/useBlueprint';
import { useConversation } from '@/blueprint/useConversation';
import { usePipecatApp, type UsePipecatAppReturn } from '@/hooks/use-pipecat-app';

import { DEFAULT_TRANSPORT, TRANSPORT_FACTORIES, TRANSPORT_PROPS } from '@/config';

/**
 * Blueprint Studio client.
 *
 * Uses the scaffold's `usePipecatApp` hook to own the Pipecat client lifecycle
 * (SmallWebRTC transport, POST /start on the bot server). The site's landing page
 * comes first; the session (and with it the presenter's video) starts when the
 * visitor switches the video on. The conversation happens there, and the studio
 * opens when "build it" starts the agent run.
 * Requirements go to the bot as RTVI client messages; agent status comes back as
 * RTVI server messages.
 *
 * The scaffold's full developer console is still available in
 * src/components/pipecat/console if you want transcripts and metrics.
 */
export function App() {
  const app = usePipecatApp({
    transportType: DEFAULT_TRANSPORT,
    transportFactory: TRANSPORT_FACTORIES[DEFAULT_TRANSPORT],
    ...TRANSPORT_PROPS[DEFAULT_TRANSPORT],
    // The mic feeds the voice agent, but starts muted: an open mic in a noisy room
    // makes the presenter answer the room. "Talk to Nuno" and the Presenter panel turn it on.
    clientOptions: { enableMic: false, enableCam: false },
    // No session on page load: an avatar session is only started on request.
    connectOnMount: false,
  });

  if (!app.client) {
    return <div className="boot">{app.error ?? 'Loading…'}</div>;
  }

  return (
    <PipecatClientProvider client={app.client}>
      <Shell app={app} />
    </PipecatClientProvider>
  );
}

type View = 'landing' | 'studio';

/** Owns the session-level state both pages share, so nothing is lost when the page changes. */
function Shell({ app }: { app: UsePipecatAppReturn }) {
  const client = usePipecatClient();
  const transport = usePipecatClientTransportState();
  const connected = transport === 'ready' || transport === 'connected';
  const { enableMic } = usePipecatClientMicControl();
  const blueprint = useBlueprint();
  const { messages, addUser } = useConversation();

  const [view, setView] = useState<View>('landing');
  const [draft, setDraft] = useState('');
  const [manual, setManual] = useState(false);

  // Intent that outlives a page change: open the mic once connected, and a typed
  // sentence waiting for the presenter.
  const wantMic = useRef(false);
  const pending = useRef<string | null>(null);
  // The presenter has finished its opening line, so a typed sentence won't cut it off.
  const greeted = useRef(false);

  const openStudio = useCallback((opts?: { manual?: boolean; draft?: string }) => {
    if (opts?.draft !== undefined) setDraft(opts.draft);
    if (opts?.manual) setManual(true);
    setView('studio');
  }, []);

  const { connect, disconnect } = app;
  const setVideo = useCallback(
    (on: boolean, opts?: { mic?: boolean }) => {
      if (on) {
        if (opts?.mic) wantMic.current = true;
        void connect();
      } else {
        wantMic.current = false;
        pending.current = null;
        greeted.current = false;
        void disconnect();
      }
    },
    [connect, disconnect],
  );

  useEffect(() => {
    if (connected && wantMic.current) {
      wantMic.current = false;
      enableMic(true);
    }
  }, [connected, enableMic]);

  // A typed sentence goes to the voice agent as the user's turn, once the presenter has
  // greeted. True when it has been delivered.
  const session = blueprint.state.session;
  const deliver = useCallback(
    (text: string): boolean => {
      if (!client || !connected || !session?.conversation || !greeted.current) return false;
      void client.sendText(text, { run_immediately: true, audio_response: true });
      addUser(text);
      return true;
    },
    [client, connected, session, addUser],
  );

  const say = useCallback(
    (text: string) => {
      if (deliver(text)) return;
      pending.current = text;
      void connect();
    },
    [deliver, connect],
  );

  useRTVIClientEvent(
    RTVIEvent.BotStoppedSpeaking,
    useCallback(() => {
      greeted.current = true;
      if (pending.current && deliver(pending.current)) pending.current = null;
    }, [deliver]),
  );

  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback(
      (msg: ServerMessage) => {
        if (!msg || typeof msg !== 'object') return;
        // "Build it" started the agent team: the orchestration page takes over.
        if (msg.type === 'run_started') {
          openStudio();
          return;
        }
        // Without the voice agent nobody can take the sentence, so it becomes the brief in the studio.
        if (msg.type !== 'session_ready' || msg.conversation || !pending.current) return;
        const text = pending.current;
        pending.current = null;
        openStudio({ draft: text, manual: true });
      },
      [openStudio],
    ),
  );

  return (
    <>
      {view === 'landing' ? (
        <Landing
          state={blueprint.state}
          messages={messages}
          error={app.error}
          setVideo={setVideo}
          say={say}
          openStudio={openStudio}
        />
      ) : (
        <Studio
          blueprint={blueprint}
          messages={messages}
          draft={draft}
          manual={manual}
          connect={connect}
          disconnect={disconnect}
          error={app.error}
          onBack={() => setView('landing')}
        />
      )}
      <PipecatClientAudio />
    </>
  );
}
