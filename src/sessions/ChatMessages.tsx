import { useLayoutEffect, useRef } from "react";
import type { Message } from "./types";

const roles = { user: "你", assistant: "助手", system: "系统" };

export function ChatMessages({ messages }: { messages: readonly Message[] }) {
  const end = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const scroller = end.current?.closest<HTMLElement>(".session-content");
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [messages.length]);
  return <div className="mt-4">
    {messages.length === 0 ? <p className="text-[var(--theme-text-muted)]">还没有消息，从下面输入开始。</p>
      : <ol aria-label="聊天消息" className="space-y-3">
        {messages.map((message) => <li key={message.id} data-message-role={message.role}
          className={`max-w-full rounded-xl p-3 ${message.role === "user" ? "ml-6 bg-violet-400/10" : "mr-6 bg-[var(--theme-chat-message-background)]"}`}>
          <p className="mb-1 text-xs text-[var(--theme-text-secondary)]">{roles[message.role]}</p>
          <p className="whitespace-pre-wrap break-words text-[var(--theme-text-secondary)] [overflow-wrap:anywhere]">{message.content}</p>
          {message.attachments.length > 0 && <ul aria-label="消息附件" className="mt-2 text-xs text-[var(--theme-text-secondary)]">
            {message.attachments.map((path, index) => <li key={`${index}-${path}`} className="break-all">附件：{path}</li>)}
          </ul>}
        </li>)}
      </ol>}
    <div ref={end} />
  </div>;
}
