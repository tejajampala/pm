"use client";

import { useState, type FormEvent } from "react";
import type { BoardData } from "@/lib/kanban";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type AIChatSidebarProps = {
  board: BoardData;
  username: string;
  onBoardUpdate: (board: BoardData) => void;
  onBeforeSend: () => Promise<void>;
};

const MAX_HISTORY_TURNS = 20;

export const AIChatSidebar = ({ board, username, onBoardUpdate, onBeforeSend }: AIChatSidebarProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [isSending, setIsSending] = useState(false);

  const sendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = prompt.trim();
    if (!message || isSending) return;

    setPrompt("");
    setError("");
    setMessages((current) => [...current, { role: "user", content: message }]);
    setIsSending(true);

    try {
      // Let pending board saves finish so the AI works from, and then replaces, the latest saved board.
      await onBeforeSend();
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          message,
          board,
          history: messages.slice(-MAX_HISTORY_TURNS),
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(
          typeof payload?.detail === "string"
            ? payload.detail
            : `AI request failed with status ${response.status}`
        );
      }

      setMessages((current) => [...current, { role: "assistant", content: payload.reply }]);
      if (payload.boardUpdate) onBoardUpdate(payload.boardUpdate as BoardData);
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "Unable to reach the AI assistant.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <aside className="flex min-h-[520px] flex-col border-t border-[var(--stroke)] bg-white 2xl:min-h-0 2xl:border-l 2xl:border-t-0">
      <header className="flex items-center justify-between border-b border-[var(--stroke)] px-5 py-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--gray-text)]">
            Assistant
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[var(--navy-dark)]">Board chat</h2>
        </div>
        <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-yellow)]" aria-label="AI assistant" />
      </header>

      <div
        className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-4"
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
      >
        {messages.length === 0 ? (
          <p className="text-sm leading-6 text-[var(--gray-text)]">
            Ask about the board or request a card change.
          </p>
        ) : null}
        {messages.map((entry, index) => (
          <div
            key={`${entry.role}-${index}`}
            className={`max-w-[92%] whitespace-pre-wrap rounded-lg px-3 py-2.5 text-sm leading-5 ${
              entry.role === "user"
                ? "self-end bg-[var(--navy-dark)] text-white"
                : "self-start border border-[var(--stroke)] bg-[var(--surface)] text-[var(--navy-dark)]"
            }`}
          >
            {entry.content}
          </div>
        ))}
        {isSending ? <p className="text-sm text-[var(--gray-text)]">Thinking...</p> : null}
      </div>

      {error ? <p className="px-4 pb-2 text-sm text-red-700" role="alert">{error}</p> : null}

      <form onSubmit={sendMessage} className="border-t border-[var(--stroke)] p-4">
        <label htmlFor="assistant-prompt" className="sr-only">Message the assistant</label>
        <textarea
          id="assistant-prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ask about your board..."
          rows={3}
          className="w-full resize-y rounded-lg border border-[var(--stroke)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
        />
        <button
          type="submit"
          disabled={isSending || !prompt.trim()}
          className="mt-2 w-full rounded-lg bg-[var(--secondary-purple)] px-4 py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSending ? "Sending..." : "Send"}
        </button>
      </form>
    </aside>
  );
};