import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

import type { ChatMessage } from '../useConversation';

/** The conversation with the presenter as chat bubbles, kept scrolled to the latest turn. */
export function ChatLog({ messages, empty, botName = 'Presenter', limit }: {
  messages: ChatMessage[];
  /** Shown while there are no messages yet. */
  empty?: ReactNode;
  /** The presenter's name on the bot's bubbles. */
  botName?: string;
  /** Show only the latest messages, this many; all of them when unset. */
  limit?: number;
}) {
  const shown = limit ? messages.slice(-limit) : messages;
  const log = useRef<HTMLDivElement>(null);
  // Scroll the log itself, not the page: scrollIntoView would also move the window
  // when the log sits below the fold.
  useEffect(() => {
    const el = log.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <div ref={log} className="chat" role="log" aria-live="polite">
      {messages.length === 0 && empty && <p className="chat-empty">{empty}</p>}
      {shown.map((m) => (
        <div key={m.id} className={`msg ${m.role}`}>
          <span className="msg-who">{m.role === 'bot' ? botName : 'You'}</span>
          {m.text || '…'}
        </div>
      ))}
    </div>
  );
}
