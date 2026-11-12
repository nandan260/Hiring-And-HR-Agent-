import React, { useEffect, useState } from "react";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { UnifiedConversationMessage } from "../../types/agent";

export const HrAssistantPage: React.FC = () => {
  const { conversations, createConversation, sendConversationTurn, uploadKnowledgeDoc } =
    useApp();

  const [activeConvId, setActiveConvId] = useState<string>("");
  const [messages, setMessages] = useState<UnifiedConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<
    Array<{ id: string; title: string }>
  >([]);
  const [sending, setSending] = useState(false);
  const [turnError, setTurnError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeConvId && conversations.length > 0) {
      setActiveConvId(conversations[0].id);
    }
  }, [conversations, activeConvId]);

  useEffect(() => {
    if (!activeConvId) return;
    apiClient
      .listHrConversationMessages(activeConvId)
      .then((res) => setMessages(Array.isArray(res) ? res : []))
      .catch(() => setMessages([]));
  }, [activeConvId]);

  const handleNewChat = async () => {
    const conv = await createConversation("HR Assistant");
    if (conv) {
      setActiveConvId(conv.id);
      setMessages([]);
    }
  };

  const handleFileAttach = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("category", "hr_policy");
    fd.append("title", `Chat Upload - ${file.name}`);
    const res = await uploadKnowledgeDoc(fd);
    if (res.ok && res.doc) {
      setPendingAttachments((prev) => [...prev, { id: res.doc!.id, title: res.doc!.title }]);
    }
    e.target.value = "";
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    let targetId = activeConvId;
    if (!targetId) {
      const created = await createConversation(input.slice(0, 42));
      if (!created) return;
      targetId = created.id;
      setActiveConvId(targetId);
    }

    const userText = input.trim();
    setInput("");
    setSending(true);
    setTurnError(null);

    const optimisticUser: UnifiedConversationMessage = {
      id: `local-${Date.now()}`,
      conversation_id: targetId,
      role: "user",
      content: userText,
      classifier_result: null,
      metadata_json: {},
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);

    const res = await sendConversationTurn(targetId, {
      content: userText,
      attachments: pendingAttachments.map((a) => a.id),
    });
    setPendingAttachments([]);
    setSending(false);

    if (res.ok && res.data) {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticUser.id),
        res.data!.user_message,
        res.data!.assistant_message,
      ]);
    } else {
      setTurnError(res.error || "Message failed.");
    }
  };

  return (
    <div className="grid h-full min-h-0 grid-cols-12 gap-3">
      <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-3">
        <div className="mb-2 flex flex-none items-center justify-between">
          <h1 className="hf-h2">Threads</h1>
          <button type="button" onClick={handleNewChat} className="hf-btn hf-btn-primary hf-btn-sm">
            New
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="hf-empty">No threads.</div>
          ) : (
            conversations.map((c) => {
              const active = c.id === activeConvId;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setActiveConvId(c.id)}
                  className={`w-full rounded-[var(--r-field)] border px-2.5 py-2 text-left text-xs transition ${
                    active
                      ? "border-[var(--fg)] bg-[var(--inv-bg)] font-semibold text-[var(--inv-fg)]"
                      : "border-[var(--border)] bg-transparent text-[var(--fg)] hover:bg-[var(--surface-hover)]"
                  }`}
                >
                  <div className="truncate">{c.title}</div>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-9">
        <div className="mb-2 flex flex-none items-center justify-between border-b border-[var(--border)] pb-2">
          <span className="hf-h2">HR Assistant</span>
          <span className="font-mono text-[11px] text-[var(--muted)]">
            {messages.length} messages
          </span>
        </div>

        <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto pr-1">
          {messages.length === 0 ? (
            <div className="hf-empty my-auto">Send a message to start.</div>
          ) : (
            messages.map((msg) => {
              const routedWorkflow = msg.metadata_json?.routed_workflow as string | undefined;
              const citations = (msg.metadata_json?.citations as string[] | undefined) || [];
              return (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[82%] rounded-[var(--r-field)] border px-3 py-2 text-[13px] ${
                      msg.role === "user"
                        ? "border-[var(--fg)] bg-[var(--inv-bg)] text-[var(--inv-fg)]"
                        : "border-[var(--border)] bg-[var(--surface)] text-[var(--fg)]"
                    }`}
                  >
                    {(routedWorkflow || msg.classifier_result) && (
                      <div className="mb-1 flex items-center gap-2 font-mono text-[10px] text-[var(--muted)]">
                        {routedWorkflow && <span>{routedWorkflow}</span>}
                        {msg.classifier_result && <span>{msg.classifier_result}</span>}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                    {citations.length > 0 && (
                      <div className="mt-1.5 border-t border-[var(--border)] pt-1 text-[11px] text-[var(--muted)]">
                        {citations.join(" | ")}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {turnError && (
          <div className="mt-2 flex-none rounded-[var(--r-field)] border border-[var(--fg)] px-2.5 py-1.5 text-xs text-[var(--fg)]">
            {turnError}
          </div>
        )}

        {pendingAttachments.length > 0 && (
          <div className="mt-2 flex flex-none flex-wrap gap-1.5">
            {pendingAttachments.map((a) => (
              <span key={a.id} className="hf-chip hf-chip-plain">
                {a.title}
              </span>
            ))}
          </div>
        )}

        <form
          onSubmit={handleSend}
          className="mt-2.5 flex flex-none items-center gap-2 border-t border-[var(--border)] pt-2.5"
        >
          <label className="hf-btn hf-btn-sm cursor-pointer">
            Attach
            <input type="file" onChange={handleFileAttach} className="hidden" />
          </label>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask HireFlow AI about candidates, leave policy, interviews..."
            className="hf-input flex-1"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="hf-btn hf-btn-primary"
          >
            {sending ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
};
