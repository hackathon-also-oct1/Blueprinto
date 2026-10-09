import { PipecatClientVideo, usePipecatClient, usePipecatClientMicControl } from '@pipecat-ai/client-react';

/** The presenter: the bot's video track (with AVATAR_PROVIDER set) and the mic for talking to it. */
export function AvatarPanel({ enabled, voice, conversation, issue }: {
  enabled: boolean;
  voice: boolean;
  conversation: boolean;
  issue: string | null;
}) {
  const { enableMic, isMicEnabled } = usePipecatClientMicControl();
  const client = usePipecatClient();

  return (
    <div className={enabled ? 'avatar' : 'avatar-off'}>
      <span className="label">Presenter</span>
      {enabled && (
        <PipecatClientVideo
          participant="bot"
          fit="cover"
          className="avatar-video"
          // The presenter greets once its video is showing (see server/bot.py).
          onPlaying={() => client?.sendClientMessage('presenter_ready')}
        />
      )}
      {issue && (
        <p className="hint">
          Video presenter unavailable, voice only. {issue.includes('concurrent_session_limit')
            ? 'Anam allows one avatar session at a time; close other tabs and reconnect in a few minutes.'
            : issue}
        </p>
      )}
      {conversation ? (
        <>
          <p className="hint">
            {isMicEnabled
              ? 'Listening. Answer Nuno\'s questions, then say "build it" to start the agents.'
              : 'Microphone is off. Turn it on to talk to the presenter.'}
          </p>
          <button className="btn ghost" aria-pressed={isMicEnabled} onClick={() => enableMic(!isMicEnabled)}>
            {isMicEnabled ? 'Mute microphone' : 'Turn on microphone'}
          </button>
        </>
      ) : (
        !enabled && !issue && (
          <p className="hint">
            {voice
              ? 'Narration is on, voice only. Set AVATAR_PROVIDER=anam and ANAM_API_KEY on the server to add a video presenter.'
              : 'Add an SLNG or Azure AI Speech key for narration, then AVATAR_PROVIDER=anam for a video presenter.'}
          </p>
        )
      )}
    </div>
  );
}
