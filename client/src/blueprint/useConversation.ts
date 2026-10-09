import { RTVIEvent } from '@pipecat-ai/client-js';
import { useRTVIClientEvent } from '@pipecat-ai/client-react';
import { useCallback, useState } from 'react';

export interface ChatMessage {
  id: number;
  role: 'user' | 'bot';
  text: string;
  /** False while the presenter is still producing this reply. */
  final: boolean;
}

export interface Conversation {
  messages: ChatMessage[];
  /**
   * Record a sentence the user typed. The server appends typed text to the LLM
   * context without a transcript event, so it only shows up here if we add it.
   */
  addUser: (text: string) => void;
}

/** The conversation with the presenter, spoken or typed, as chat messages. */
export function useConversation(): Conversation {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const addUser = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((m) => [...m, { id: m.length, role: 'user', text: trimmed, final: true }]);
  }, []);

  useRTVIClientEvent(RTVIEvent.UserTranscript, (data) => {
    if (!data.final || !data.text.trim()) return;
    setMessages((m) => [...m, { id: m.length, role: 'user', text: data.text.trim(), final: true }]);
  });

  useRTVIClientEvent(RTVIEvent.BotLlmStarted, () => {
    setMessages((m) => [...m, { id: m.length, role: 'bot', text: '', final: false }]);
  });

  useRTVIClientEvent(RTVIEvent.BotLlmText, (data) => {
    setMessages((m) => {
      const last = m[m.length - 1];
      if (!last || last.role !== 'bot' || last.final) {
        return [...m, { id: m.length, role: 'bot', text: data.text, final: false }];
      }
      return [...m.slice(0, -1), { ...last, text: last.text + data.text }];
    });
  });

  useRTVIClientEvent(RTVIEvent.BotLlmStopped, () => {
    setMessages((m) => {
      const last = m[m.length - 1];
      if (!last || last.role !== 'bot' || last.final) return m;
      // A turn that only called a tool produces no text; drop the empty bubble.
      return last.text.trim() ? [...m.slice(0, -1), { ...last, final: true }] : m.slice(0, -1);
    });
  });

  return { messages, addUser };
}
