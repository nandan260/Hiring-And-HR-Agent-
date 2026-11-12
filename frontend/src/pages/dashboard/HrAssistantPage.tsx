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
    fd.append("min_role_access", session.role === "business_employee" ? "business_employee" : "business_admin");
    fd.append("workflow_slug", "recruitment-screening");
    const res = await uploadKnowledgeDoc(fd);
    if (!res.ok || !res.doc) {
      setTurnError(res.error || "Attachment upload failed");
    } else {
      setPendingAttachments((prev) => [...prev, { id: res.doc!.id, name: res.doc!.original_filename }]);
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
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs lg:col-span-3">
        <button
          type="button"
          onClick={handleNewThread}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3.5 py-2.5 text-xs font-semibold text-white hover:bg-indigo-500"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New HR Conversation
        </button>

        <div className="mt-4 space-y-1.5">
          <div className="px-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Recent Threads ({conversations.length})
          </div>
          {conversations.length === 0 ? (
            <p className="px-1 py-2 text-xs text-slate-500">
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
                    ? "bg-indigo-50 font-semibold text-indigo-800"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                <div className="truncate">{c.title}</div>
                <div className="mt-0.5 text-[10px] text-slate-400">
                  {c.message_count} messages
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Unified Chat Window */}
      <div className="flex h-[74vh] flex-col rounded-2xl border border-slate-200 bg-white shadow-xs lg:col-span-9">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <h1 className="font-display text-sm font-bold text-slate-900">
                HireFlow AI — Unified HR Assistant
              </h1>
              <p className="text-[11px] text-slate-500">
                Auto-routes internally across all 7 HR workflows while preserving multi-turn
                follow-up context.
              </p>
            </div>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 font-mono text-[11px] text-slate-700">
            Role: {session.role}
          </span>
        </div>

        {/* Messages Feed */}
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <div className="space-y-4 py-8 text-center">
              <Sparkles className="mx-auto h-7 w-7 text-indigo-500" />
              <div>
                <h2 className="font-display text-base font-bold text-slate-900">
                  Ask anything across Hiring &amp; HR
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Follow-up questions carry prior candidate, role, and workflow context across turns.
                </p>
              </div>
              <div className="mx-auto grid max-w-2xl gap-2 sm:grid-cols-2">
                {QUICK_SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setInput(s)}
                    className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-left text-xs text-slate-700 hover:border-indigo-300 hover:bg-indigo-50/40"
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
              const citations = Array.isArray(meta.citations) ? (meta.citations as string[]) : [];
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
                        ? "bg-indigo-600 text-white"
                        : isGuard
                          ? "border border-rose-200 bg-rose-50 text-rose-950"
                          : "border border-slate-200 bg-slate-50 text-slate-800"
                    }`}
                  >
                    {!isUser && wfName && (
                      <div className="mb-1.5 flex items-center gap-2 text-[11px]">
                        <span className="rounded-full bg-indigo-100 px-2 py-0.5 font-semibold text-indigo-800">
                          {wfName}
                        </span>
                        {m.classifier_result && (
                          <span className="font-mono text-slate-500">{m.classifier_result}</span>
                        )}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                    {citations.length > 0 && (
                      <div className="mt-2 border-t border-slate-200 pt-2 text-[11px] text-slate-600">
                        <strong>Sources:</strong> {citations.join(" • ")}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {turnError && (
          <div className="mx-5 mb-2 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2 text-xs font-medium text-rose-800">
            <ShieldAlert className="h-4 w-4 shrink-0 text-rose-600" />
            <span>{turnError}</span>
          </div>
        )}

        {pendingAttachments.length > 0 && (
          <div className="mx-5 mb-2 flex flex-wrap gap-1.5 text-xs">
            {pendingAttachments.map((att) => (
              <span
                key={att.id}
                className="rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1 font-medium text-indigo-700"
              >
                Attached: {att.name}
              </span>
            ))}
          </div>
        )}

        {/* Composer */}
        <form
          onSubmit={handleSend}
          className="flex items-center gap-2 border-t border-slate-200 p-4"
        >
          <label
            title="Upload resume or document to attach"
            className="cursor-pointer rounded-xl border border-slate-200 p-2.5 text-slate-600 hover:bg-slate-50"
          >
            <Paperclip className="h-4 w-4" />
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md,.csv"
              className="hidden"
              onChange={handleAttachFile}
            />
          </label>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask HireFlow AI (policy, screening, JD, shortlisting, interviews, onboarding, analytics)..."
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-indigo-400"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            <Send className="h-4 w-4" />
            {sending ? "Routing..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
};
