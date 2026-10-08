import { PipecatClientProvider } from '@pipecat-ai/client-react';

import { Studio } from '@/blueprint/Studio';
import { usePipecatApp } from '@/hooks/use-pipecat-app';

import { DEFAULT_TRANSPORT, TRANSPORT_FACTORIES, TRANSPORT_PROPS } from '@/config';

/**
 * Blueprint Studio client.
 *
 * Uses the scaffold's `usePipecatApp` hook to own the Pipecat client lifecycle
 * (SmallWebRTC transport, POST /start on the bot server), then renders the
 * studio inside a PipecatClientProvider. Requirements go to the bot as RTVI
 * client messages; agent status comes back as RTVI server messages.
 *
 * The scaffold's full developer console is still available in
 * src/components/pipecat/console if you want transcripts and metrics.
 */
export function App() {
  const app = usePipecatApp({
    transportType: DEFAULT_TRANSPORT,
    transportFactory: TRANSPORT_FACTORIES[DEFAULT_TRANSPORT],
    ...TRANSPORT_PROPS[DEFAULT_TRANSPORT],
    // Mic in for the voice agent (typing still works), presenter audio and video out.
    clientOptions: { enableMic: true, enableCam: false },
    connectOnMount: true,
  });

  if (!app.client) {
    return <div className="boot">{app.error ?? 'Loading…'}</div>;
  }

  return (
    <PipecatClientProvider client={app.client}>
      <Studio connect={app.connect} disconnect={app.disconnect} error={app.error} />
    </PipecatClientProvider>
  );
}
