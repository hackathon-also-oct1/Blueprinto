import type { ChatMessage } from '../useConversation';
import { ChatLog } from './ChatLog';

/** The conversation with the presenter as a chat. Shown until "build it" produces a requirement. */
export function ConversationPanel({ messages, onType }: {
  messages: ChatMessage[];
  onType: () => void;
}) {
  return (
    <div>
      <span className="label">Conversation</span>
      <ChatLog
        messages={messages}
        empty='Turn on the microphone and answer the presenter. Say "build it" when you are ready.'
      />
      <button type="button" className="link" onClick={onType}>Type a brief instead</button>
    </div>
  );
}
