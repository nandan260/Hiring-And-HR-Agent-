import React, { useEffect, useState } from "react";
import {
  Bot,
  MessageSquarePlus,
  Paperclip,
  Send,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { UnifiedConversationMessage } from "../../types/agent";

const QUICK_SUGGESTIONS = [
  "How many days of PTO and paid parental leave do employees receive?",
  "Draft an inclusive Job Description for Senior Frontend Engineer (React, TypeScript).",
  "Compare and shortlist top candidates for Senior Backend Engineer.",
  "Show hiring pipeline metrics and monthly workflow token analytics.",
];

export const HrAssistantPage: React.FC = () => {
  const {
    conversations,
    createConversation,
    sendConversationTurn,
    uploadKnowledgeDoc,
    session,
  } = useApp();

  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UnifiedConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingAttachments, setPendingAttachments] = useState<{ id: string; name: string }[]>([]);
  const [sending, setSending] = useState(false);
  const [turnError, setTurnError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeConvId && conversations.length > 0) {
      setActiveConvId(conversations[0].id);
    }
  }, [activeConvId, conversations]);

  useEffect(() => {
    if (!activeConvId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    apiClient
      .listHrConversationMessages(activeConvId)
      .then((rows) => {
        if (!cancelled) setMessages(rows);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeConvId]);

  const handleNewThread = async () => {
    setTurnError(null);
    const created = await createConversation(`HR Session ${new Date().toLocaleTimeString()}`);
    if (created) {
      setActiveConvId(created.id);
      setMessages([]);
    }
  };

  const handleAttachFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setTurnError(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", file.name);
    fd.append("source_type", "resume");
    fd.append(
      "min_role_access",
      session.role === "business_employee" ? "business_employee" : "business_admin"
    );
    fd.append("workflow_slug", "recruitment-screening");
    const res = await uploadKnowledgeDoc(fd);
    if (!res.ok || !res.doc) {
      setTurnError(res.error || "Attachment upload failed");
    } else {
      setPendingAttachments((prev) => [
        ...prev,
        { id: res.doc!.id, name: res.doc!.original_filename },
      ]);
    }
    e.target.value = "";
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sending) return;
    setTurnError(null);
    setSending(true);

    let convId = activeConvId;
    if (!convId) {
      const created = await createConversation(input.trim().slice(0, 60));
      if (!created) {
        setSending(false);
        return;
      }
      convId = created.id;
      setActiveConvId(convId);
    }

    const res = await sendConversationTurn(convId, {
      content: input.trim(),
      attachments: pendingAttachments.map((a) => a.id),
    });
    setSending(false);

    if (!res.ok) {
      setTurnError(res.error || "Message failed");
      return;
    }

    setInput("");
    setPendingAttachments([]);
    const refreshed = await apiClient.listHrConversationMessages(convId);
    setMessages(refreshed);
  };

  return (
    <div className="grid gap-5 lg:grid-cols-12">
      {/* Threads Sidebar */}
      <div className="hf-card flex flex-col p-4 lg:col-span-3">
        <button
          type="button"
          onClick={handleNewThread}
          className="hf-btn hf-btn-primary w-full text-xs"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New HR Conversation
        </button>

        <div className="mt-4 space-y-1">
          <div className="px-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            Recent Threads ({conversations.length})
          </div>
          {conversations.length === 0 ? (
            <p className="px-1 py-2 text-xs text-[var(--muted)]">
              Start a conversation to ask policy, hiring, onboarding, or analytics questions.
            </p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setActiveConvId(c.id)}
                className={`w-full rounded-xl px-3 py-2 text-left text-xs transition ${
                  c.id === activeConvId
                    ? "bg-[var(--field)] font-semibold text-[var(--ink)]"
                    : "text-[var(--ink-2)] hover:bg-[var(--field)] hover:text-[var(--ink)]"
                }`}
              >
                <div className="truncate">{c.title}</div>
                <div className="mt-0.5 text-[10.5px] text-[var(--muted)]">
                  {c.message_count} messages
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Unified Chat Window */}
      <div className="hf-card flex h-[74vh] flex-col p-0 overflow-hidden lg:col-span-9">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--field)] text-[var(--ink)]">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-[var(--ink)]">
                HireFlow AI &mdash; Unified HR Assistant
              </h1>
              <p className="text-[11px] text-[var(--muted)]">
                Auto-routes internally across all 7 HR workflows while preserving multi-turn
                follow-up context.
              </p>
            </div>
          </div>
          <span className="hf-chip hf-chip-plain font-mono">Role: {session.role}</span>
        </div>

        {/* Messages Feed */}
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <div className="space-y-4 py-8 text-center">
              <Sparkles className="mx-auto h-7 w-7 text-[var(--pass)]" />
              <div>
                <h2 className="text-base font-bold text-[var(--ink)]">
                  Ask anything across Hiring &amp; HR
                </h2>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Follow-up questions carry prior candidate, role, and workflow context across turns.
                </p>
              </div>
              <div className="mx-auto grid max-w-2xl gap-2.5 sm:grid-cols-2">
                {QUICK_SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setInput(s)}
                    className="rounded-xl border border-[var(--line)] bg-[var(--field)] px-3.5 py-2.5 text-left text-xs text-[var(--ink-2)] transition hover:border-[var(--muted)] hover:bg-[var(--field-hover)] hover:text-[var(--ink)]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => {
              const meta = m.metadata_json || {};
              const wfName = typeof meta.workflow_name === "string" ? meta.workflow_name : "";
              const citations = Array.isArray(meta.citations)
                ? (meta.citations as string[])
                : [];
              const isUser = m.role === "user";
              const isGuard = m.role === "system_guardrail";

              return (
                <div
                  key={m.id}
                  className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                      isUser
                        ? "bg-[var(--action)] text-[var(--action-ink)]"
                        : isGuard
                          ? "border border-[color:var(--block-soft)] bg-[var(--block-soft)] text-[var(--ink)]"
                          : "border border-[var(--line)] bg-[var(--field)] text-[var(--ink)]"
                    }`}
                  >
                    {!isUser && wfName && (
                      <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="hf-chip hf-chip-plain">{wfName}</span>
                        {m.classifier_result && (
                          <span className="font-mono text-[var(--muted)]">
                            {m.classifier_result}
                          </span>
                        )}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                    {citations.length > 0 && (
                      <div className="mt-2.5 border-t border-[var(--line)] pt-2 text-[11px] text-[var(--muted)]">
                        <strong className="text-[var(--ink-2)]">Sources:</strong>{" "}
                        {citations.join(" • ")}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {turnError && (
          <div className="mx-5 mb-2 flex items-center gap-2 rounded-xl border border-[color:var(--block-soft)] bg-[var(--block-soft)] px-3.5 py-2 text-xs font-medium text-[var(--block)]">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>{turnError}</span>
          </div>
        )}

        {pendingAttachments.length > 0 && (
          <div className="mx-5 mb-2 flex flex-wrap gap-1.5 text-xs">
            {pendingAttachments.map((att) => (
              <span key={att.id} className="hf-chip hf-chip-pass">
                Attached: {att.name}
              </span>
            ))}
          </div>
        )}

        {/* Composer */}
        <form onSubmit={handleSend} className="border-t border-[var(--line)] p-4">
          <div className="hf-composer flex items-center gap-2 !rounded-2xl !p-2">
            <label
              className="hf-icon-btn h-9 w-9 shrink-0 cursor-pointer border-0"
              title="Upload resume or document to attach"
            >
              <Paperclip className="h-4 w-4" />
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md,.json,.csv"
                onChange={handleAttachFile}
                className="hidden"
              />
            </label>

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask HireFlow AI (policy, screening, JD, shortlisting, interviews, onboarding, analytics)..."
              className="flex-1 border-0 bg-transparent px-2 text-sm text-[var(--ink)] outline-none placeholder:text-[var(--muted)]"
            />

            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="hf-send"
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
