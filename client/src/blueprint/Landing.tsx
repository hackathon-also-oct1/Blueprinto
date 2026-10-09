import {
  PipecatClientVideo,
  usePipecatClient,
  usePipecatClientMicControl,
  usePipecatClientTransportState,
} from '@pipecat-ai/client-react';
import { Mic, MicOff, User, Video, VideoOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { ChatLog } from './components/ChatLog';
import type { BlueprintState } from './useBlueprint';
import type { ChatMessage } from './useConversation';

/** The presenter's name on the site. The bot's own script lives in server/blueprint/conversation.py. */
const AGENT = 'Nuno';
/** Shown in the footer; replace with the studio's real address. */
const CONTACT_EMAIL = 'hello@blueprinto.studio';
const CHIPS = ['A new website', 'Redesign my current site', 'Online store', 'Landing page', 'Just want a price'];
const OPENER = `Hi, I'm ${AGENT}. What kind of website are you thinking about?`;

const CONNECTING = ['initializing', 'authenticating', 'authenticated', 'connecting'];

export interface LandingProps {
  state: BlueprintState;
  messages: ChatMessage[];
  error: string | null;
  /** Start or stop the session; the presenter's video comes with it. `mic` also opens the microphone. */
  setVideo: (on: boolean, opts?: { mic?: boolean }) => void;
  /** Hand a typed sentence to the presenter, starting the session if needed. */
  say: (text: string) => void;
  /** Open the agent orchestration page. */
  openStudio: (opts?: { manual?: boolean }) => void;
}

/**
 * The site's first screen. It loads without a session: the presenter's video (and
 * the avatar session behind it) starts only when the visitor switches it on. The
 * whole conversation happens here; the studio opens when "build it" starts the agents.
 */
export function Landing({ state, messages, error, setVideo, say, openStudio }: LandingProps) {
  const client = usePipecatClient();
  const transport = usePipecatClientTransportState();
  const connected = transport === 'ready' || transport === 'connected';
  const connecting = CONNECTING.includes(transport);
  const { enableMic, isMicEnabled } = usePipecatClientMicControl();

  // The switch shows what the visitor asked for; the transport state says how far it got.
  const [on, setOn] = useState(connected || connecting);
  // The first video frame has arrived.
  const [live, setLive] = useState(false);
  const [sentence, setSentence] = useState('');

  // The presenter speaks only once the visitor can see him: tell the server when the
  // video starts showing. Once per session; the server ignores repeats anyway.
  const announced = useRef(false);
  useEffect(() => {
    if (!connected) announced.current = false;
  }, [connected]);
  const onLive = () => {
    setLive(true);
    if (announced.current) return;
    announced.current = true;
    client?.sendClientMessage('presenter_ready');
  };

  const avatar = !!state.session?.avatar;
  const conversation = !!state.session?.conversation;
  const showVideo = on && connected && avatar;
  const listening = connected && isMicEnabled;

  const switchVideo = (next: boolean, mic = false) => {
    setOn(next);
    if (next) {
      setVideo(true, { mic });
    } else {
      setLive(false);
      setVideo(false);
    }
  };
  const talk = () => switchVideo(true, true);
  // Before the session: start it with the mic open. During it: mute and unmute.
  const onMic = () => (connected ? enableMic(!isMicEnabled) : talk());
  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setOn(true);
    setSentence('');
    say(trimmed);
  };

  // While the presenter is off, both the stage and the chat say how to begin.
  const ready = (
    <>
      <strong>{AGENT} is ready when you are</strong>
      Press start and he’ll ask a few quick questions about your website.
    </>
  );
  // Once started, and until the presenter has said anything, the chat previews its opening line.
  const shown: ChatMessage[] =
    messages.length || !on ? messages : [{ id: -1, role: 'bot', text: OPENER, final: true }];

  let stageHint: ReactNode;
  if (!on) stageHint = ready;
  else if (connecting) stageHint = `Connecting to ${AGENT}…`;
  else if (!connected) stageHint = error ?? 'Not connected. Switch the video off and on to retry.';
  else if (!state.session || avatar) stageHint = `${AGENT} is joining…`;
  else if (state.avatarIssue) stageHint = 'Video presenter unavailable, voice only.';
  else if (state.session.voice) stageHint = `Voice only on this server. ${AGENT} can still hear you.`;
  else stageHint = 'Text only on this server.';

  let status: string | null = null;
  if (connected && conversation) {
    status = listening
      ? `Listening. Answer ${AGENT}'s questions, then say "build it" to start the agents.`
      : `Tap the microphone to talk to ${AGENT}, or type a sentence.`;
  } else if (connected && state.session) {
    status = `Pick an option or type a sentence; the brief opens in the studio.`;
  }

  return (
    <div className="landing">
      <div className="site">
        <header className="nav">
          <a className="brand" href="#top">
            <span className="brand-mark" aria-hidden="true" />
            Blueprinto Studio
          </a>
          <nav className="nav-links" aria-label="Site">
            <a href="#work">Work</a>
            <a href="#services">Services</a>
            <a href="#pricing">Pricing</a>
            <button type="button" className="nav-link" onClick={() => openStudio()}>Studio</button>
            <button type="button" className="btn dark" onClick={talk}>Start a project</button>
          </nav>
        </header>

        <main>
          <section className="hero" id="top">
            <div className="hero-copy">
              <span className="pill">
                <i className="dot" aria-hidden="true" />
                {AGENT} is available now — no forms, no waiting for a call back
              </span>
              <h1>Tell us about your website. We’ll write the brief.</h1>
              <p className="lede">
                Have a short conversation with {AGENT}, our AI project consultant. He asks the right questions,
                shows you examples, and turns your answers into a clear project brief — then a real project lead
                takes it from there.
              </p>
              <div className="hero-cta">
                <button type="button" className="btn dark" onClick={talk}>
                  <Video size={18} aria-hidden="true" /> Talk to {AGENT}
                </button>
                <button type="button" className="btn outline" onClick={() => openStudio({ manual: true })}>
                  Fill in a form instead
                </button>
              </div>
              <p className="fine">Your camera stays off. You get the written brief by email either way.</p>
            </div>

            <section className="agent-panel" aria-label={`${AGENT}, AI project consultant`}>
              <div className="agent-top">
                <span className="agent-tag">
                  <i className={connected ? 'dot live' : 'dot'} aria-hidden="true" />
                  {AGENT} · AI project consultant
                </span>
                <button type="button" className="switch" role="switch" aria-checked={on} onClick={() => switchVideo(!on)}>
                  {on ? <Video size={14} aria-hidden="true" /> : <VideoOff size={14} aria-hidden="true" />}
                  Video {on ? 'on' : 'off'}
                  <i className="knob" aria-hidden="true" />
                </button>
              </div>

              <div className="agent-stage">
                {showVideo && (
                  <PipecatClientVideo
                    participant="bot"
                    fit="cover"
                    className="agent-video"
                    onResize={(d) => { if (d.width > 0) onLive(); }}
                    onPlaying={onLive}
                  />
                )}
                {!(showVideo && live) && (
                  <div className="agent-placeholder" role="status">
                    <User size={64} strokeWidth={1.25} aria-hidden="true" />
                    <span>{stageHint}</span>
                  </div>
                )}
              </div>

              {/* Only the latest turn, one row: the panel stays level with the copy on the left. */}
              <ChatLog messages={shown} botName={AGENT} limit={1} empty={ready} />

              <div className="chips">
                {CHIPS.map((chip) => (
                  <button key={chip} type="button" className="chip-btn" onClick={() => send(chip)}>{chip}</button>
                ))}
              </div>

              <form className="say" onSubmit={(e) => { e.preventDefault(); send(sentence); }}>
                <input
                  aria-label="Describe your project"
                  value={sentence}
                  placeholder="Or describe your project in a sentence..."
                  onChange={(e) => setSentence(e.target.value)}
                />
                <button
                  type="button"
                  className="mic"
                  aria-pressed={listening}
                  aria-label={listening ? 'Mute microphone' : `Talk to ${AGENT}`}
                  onClick={onMic}
                >
                  {connected && !isMicEnabled ? <MicOff size={18} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
                </button>
              </form>
              {status && <p className="agent-status" role="status">{status}</p>}
            </section>
          </section>

          <section className="steps" id="services">
            <h2>From first hello to proposal</h2>
            <div className="cards">
              <article className="card">
                <span className="n">01 · Talk</span>
                <h3>A short discovery chat</h3>
                <p>{AGENT} asks about your business, who the site is for, and what it needs to do. Answer by voice, by typing, or by tapping.</p>
              </article>
              <article className="card">
                <span className="n">02 · See it take shape</span>
                <h3>Your brief fills in live</h3>
                <p>Every answer lands in a project brief beside the conversation. Correct anything on the spot, and pick example sites you like.</p>
              </article>
              <article className="card">
                <span className="n">03 · Meet your project lead</span>
                <h3>A human sends the proposal</h3>
                <p>Book a call with a real project lead who has already read your brief. Your quote comes from them, not from the AI.</p>
              </article>
            </div>
          </section>
        </main>
      </div>

      <footer className="foot">
        <div className="site foot-in">
          <span className="brand">Blueprinto Studio</span>
          <nav className="foot-links" aria-label="Legal">
            <a href="#privacy">Privacy</a>
            <a href="#how">How {AGENT} uses your answers</a>
            <a href="#accessibility">Accessibility</a>
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
