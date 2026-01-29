"use client";

import { useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import {
  askDecisionRag,
  getDocument,
  getMeeting,
  listDocuments,
  listMeetings
} from "@/app/lib/apiClient";
import { useLanguage } from "../../providers/LanguageProvider";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export default function DialogPage() {
  const { data: session } = useSession();
  const backendToken = (session as any)?.backendToken as string | undefined;
  const { language } = useLanguage();
  const auth = useMemo(() => ({ token: backendToken }), [backendToken]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [meetings, setMeetings] = useState<any[]>([]);
  const [ownerType, setOwnerType] = useState<"document" | "meeting">("document");
  const [ownerId, setOwnerId] = useState<string>("");
  const [personas, setPersonas] = useState<any[]>([]);
  const [target, setTarget] = useState<string>("all");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const copy =
    language === "zh"
      ? {
          title: "決策對話",
          subtitle: "選擇文件或會議，再用決策語境提問。",
          sourceType: "來源類型",
          source: "來源",
          agent: "對話角色",
          allAgents: "全部角色",
          empty: "詢問風險、邊界或不可亂試的原因。",
          placeholder: "輸入你的決策問題…",
          send: "送出",
          thinking: "正在思考...",
          unable: "無法回答。",
          document: "文件",
          meeting: "會議",
          select: "請選擇..."
        }
      : {
          title: "Ask your decision agents",
          subtitle:
            "Select a document or meeting, then ask questions grounded in its decision record.",
          sourceType: "Source type",
          source: "Source",
          agent: "Agent focus",
          allAgents: "All agents",
          empty: "Ask how this decision should be handled, or what risks remain.",
          placeholder: "Ask a decision question...",
          send: "Send",
          thinking: "Thinking...",
          unable: "Unable to answer.",
          document: "Document",
          meeting: "Meeting",
          select: "Select..."
        };

  useEffect(() => {
    if (!backendToken) return;
    listDocuments(auth).then(result => setDocuments(result.documents || []));
    listMeetings(auth).then(result => setMeetings(result.meetings || []));
  }, [auth, backendToken]);

  useEffect(() => {
    const handler = (event: StorageEvent) => {
      if (event.key === "documents_updated" && backendToken) {
        listDocuments(auth).then(result => setDocuments(result.documents || []));
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [auth, backendToken]);

  useEffect(() => {
    if (!ownerId || !backendToken) return;
    if (ownerType === "meeting") {
      getMeeting(auth, ownerId).then(result => {
        setPersonas(result.personas || []);
      });
    } else {
      getDocument(auth, ownerId).then(() => setPersonas([]));
    }
  }, [auth, ownerId, ownerType, backendToken]);

  const handleSend = () => {
    if (!input.trim() || !ownerId) return;
    const message = { id: `user-${Date.now()}`, role: "user" as const, content: input };
    setMessages(prev => [...prev, message]);
    setInput("");
    setStatus(copy.thinking);
    askDecisionRag(auth, {
      query: message.content,
      owner_type: ownerType,
      owner_id: ownerId,
      target,
      language
    })
      .then(result => {
        setMessages(prev => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: result.answer
          }
        ]);
        setStatus(null);
      })
      .catch(() => {
        setStatus(copy.unable);
      });
  };

  return (
    <main className="page dialog-page">
      <section className="hero hero-compact">
        <div>
          <div className="eyebrow">Decision Dialog</div>
          <h1 className="hero-title">{copy.title}</h1>
          <p className="hero-subtitle">{copy.subtitle}</p>
        </div>
      </section>

      <div className="panel dialog-controls">
        <div className="dialog-row">
          <label className="field">
            {copy.sourceType}
            <select
              value={ownerType}
              onChange={event => {
                setOwnerType(event.target.value as "document" | "meeting");
                setOwnerId("");
                setPersonas([]);
              }}
            >
              <option value="document">{copy.document}</option>
              <option value="meeting">{copy.meeting}</option>
            </select>
          </label>

          <label className="field">
            {copy.source}
            <select value={ownerId} onChange={event => setOwnerId(event.target.value)}>
              <option value="">{copy.select}</option>
              {(ownerType === "document" ? documents : meetings).map(item => (
                <option
                  key={ownerType === "document" ? item.document_id : item.meeting_id}
                  value={ownerType === "document" ? item.document_id : item.meeting_id}
                >
                  {item.title || item.source_filename || "Untitled"}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            {copy.agent}
            <select value={target} onChange={event => setTarget(event.target.value)}>
              <option value="all">{copy.allAgents}</option>
              {personas.map(persona => (
                <option key={persona.persona_id} value={persona.name}>
                  {persona.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="panel dialog-chat">
        <div className="chat-window">
          {messages.length ? (
            messages.map(message => (
              <div
                key={message.id}
                className={`chat-message chat-message--${message.role}`}
              >
                {message.content}
              </div>
            ))
          ) : (
            <div className="empty-state">{copy.empty}</div>
          )}
          {status ? <div className="chat-status">{status}</div> : null}
        </div>
        <div className="chat-input">
          <input
            type="text"
            placeholder={copy.placeholder}
            value={input}
            onChange={event => setInput(event.target.value)}
          />
          <button type="button" className="button" onClick={handleSend}>
            {copy.send}
          </button>
        </div>
      </div>
    </main>
  );
}
