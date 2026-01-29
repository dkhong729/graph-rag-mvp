"use client";

import { useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  createMeeting,
  finalizeMeetingPage,
  getPage,
  listMeetingPages,
  listMeetings,
  renderMeetingPage,
  streamMeetingPage,
  transcribeMeetingAudio,
  updateMeetingTranscript,
  updatePage
} from "@/app/lib/apiClient";
import { consumeSse } from "../../lib/sse";
import { ensureHtmlDocument } from "../../lib/html";
import { useLanguage } from "../../providers/LanguageProvider";

const styleOptions = [
  { value: "technical", label: "Technical" },
  { value: "business", label: "Business" },
  { value: "executive", label: "Executive" }
];

type MeetingStage = "Idle" | "Parsing" | "Decision Structuring" | "HTML Rendering" | "Finalizing";

type ProgressState = {
  stage: MeetingStage;
  percent: number;
  message: string;
};

export default function MeetingsPage() {
  const { data: session } = useSession();
  const backendToken = (session as any)?.backendToken as string | undefined;
  const auth = useMemo(() => ({ token: backendToken }), [backendToken]);
  const { language } = useLanguage();
  const router = useRouter();
  const searchParams = useSearchParams();
  const copy =
    language === "zh"
      ? {
          title: "決策化會議紀錄",
          subtitle: "上傳音檔或貼上逐字稿，生成可下載的決策紀錄。",
          uploadTitle: "上傳音檔",
          uploadLabel: "上傳 WAV / MP3",
          uploadAction: "上傳會議音檔",
          transcribe: "語音轉錄",
          transcribing: "語音轉錄中...",
          createFromTranscript: "用逐字稿建立會議",
          transcriptReady: "逐字稿已完成",
          pasteLabel: "或貼上逐字稿",
          pastePlaceholder: "貼上帶有說話者標記的逐字稿...",
          generate: "生成會議決策頁",
          previewTitle: "會議決策頁",
          previewSubtitle: "分層呈現事實、立場與價值。",
          downloadHtml: "下載 HTML",
          downloadPdf: "下載 PDF",
          save: "保存編輯",
          fullscreen: "全螢幕",
          exitFullscreen: "退出全螢幕",
          empty: "生成後的會議頁面會顯示在這裡。",
          stages: ["解析", "決策結構化", "HTML 渲染", "收尾"],
          idle: "上傳會議音檔以開始。",
          outputLang: "輸出語言",
          pageLimit: "頁數上限"
        }
      : {
          title: "Decision-ready meeting records",
          subtitle: "Upload audio, generate layered decision notes, and export to HTML/PDF.",
          uploadTitle: "Audio Upload",
          uploadLabel: "Upload WAV / MP3",
          uploadAction: "Upload meeting audio",
          transcribe: "Transcribe audio",
          transcribing: "Transcribing audio...",
          createFromTranscript: "Create meeting from transcript",
          transcriptReady: "Transcript ready.",
          pasteLabel: "or paste transcript",
          pastePlaceholder: "Paste transcript with speaker labels...",
          generate: "Generate meeting decision page",
          previewTitle: "Meeting Decision Page",
          previewSubtitle: "Layered facts, stances, and values.",
          downloadHtml: "Download HTML",
          downloadPdf: "Download PDF",
          save: "Save edits",
          fullscreen: "Fullscreen",
          exitFullscreen: "Exit fullscreen",
          empty: "Generated meeting page appears here.",
          stages: ["Parsing", "Decision Structuring", "HTML Rendering", "Finalizing"],
          idle: "Upload meeting audio to begin.",
          outputLang: "Output language",
          pageLimit: "Page limit"
        };
  const stageMap: Record<MeetingStage, string> = {
    Idle: copy.stages[0],
    Parsing: copy.stages[0],
    "Decision Structuring": copy.stages[1],
    "HTML Rendering": copy.stages[2],
    Finalizing: copy.stages[3]
  };

  const [file, setFile] = useState<File | null>(null);
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [style, setStyle] = useState("executive");
  const [outputLanguage, setOutputLanguage] = useState<"zh" | "en">("en");
  const [pageLimit, setPageLimit] = useState(2);
  const [status, setStatus] = useState(copy.idle);
  const [html, setHtml] = useState("");
  const [transcript, setTranscript] = useState("");
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [pageId, setPageId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressState>({
    stage: "Idle",
    percent: 0,
    message: ""
  });
  const [error, setError] = useState<string | null>(null);
  const [previewFullscreen, setPreviewFullscreen] = useState(false);
  const [meetings, setMeetings] = useState<any[]>([]);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);

  const displayStage = stageMap[progress.stage] ?? progress.stage;

  useEffect(() => {
    if (
      (status === "Upload meeting audio to begin." || status === "上傳會議音檔以開始。") &&
      status !== copy.idle
    ) {
      setStatus(copy.idle);
    }
  }, [copy.idle, status]);

  useEffect(() => {
    if (!previewFullscreen) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPreviewFullscreen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [previewFullscreen]);

  useEffect(() => {
    if (!pageId || !backendToken) return;
    if (html) return;
    getPage(auth, pageId).then(page => {
      setHtml(ensureHtmlDocument(page.html));
    });
  }, [auth, backendToken, html, meetingId, pageId]);

  useEffect(() => {
    if (!backendToken) return;
    listMeetings(auth).then(result => setMeetings(result.meetings || []));
  }, [auth, backendToken]);

  const handleSelectMeeting = async (id: string) => {
    setMeetingId(id);
    setPageId(null);
    setHtml("");
    const pages = await listMeetingPages(auth, id);
    if (pages.pages && pages.pages.length) {
      const latest = pages.pages[0];
      const page = await getPage(auth, latest.page_id);
      setHtml(ensureHtmlDocument(page.html));
      setPageId(latest.page_id);
    }
  };

  useEffect(() => {
    const meetingParam = searchParams.get("meeting");
    const pageParam = searchParams.get("page");
    const styleParam = searchParams.get("style");
    const langParam = searchParams.get("lang");
    const pagesParam = searchParams.get("pages");
    const fullscreenParam = searchParams.get("fullscreen");
    if (meetingParam) setMeetingId(meetingParam);
    if (pageParam) setPageId(pageParam);
    if (styleParam) setStyle(styleParam);
    if (langParam === "zh" || langParam === "en") setOutputLanguage(langParam);
    if (pagesParam) {
      const parsed = Number(pagesParam);
      if (!Number.isNaN(parsed)) setPageLimit(parsed);
    }
    if (fullscreenParam === "1") setPreviewFullscreen(true);
    if (!meetingParam) {
      const stored = window.localStorage.getItem("meeting_state");
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed.meetingId) setMeetingId(parsed.meetingId);
          if (parsed.pageId) setPageId(parsed.pageId);
          if (parsed.style) setStyle(parsed.style);
          if (parsed.outputLanguage) setOutputLanguage(parsed.outputLanguage);
          if (parsed.pageLimit) setPageLimit(parsed.pageLimit);
          if (parsed.fullscreen) setPreviewFullscreen(true);
        } catch {
          // ignore
        }
      }
    }
  }, [searchParams]);

  useEffect(() => {
    if (!meetingId) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("meeting", meetingId);
    if (pageId) params.set("page", pageId);
    if (style) params.set("style", style);
    if (outputLanguage) params.set("lang", outputLanguage);
    if (pageLimit) params.set("pages", String(pageLimit));
    if (previewFullscreen) {
      params.set("fullscreen", "1");
    } else {
      params.delete("fullscreen");
    }
    const next = params.toString();
    if (next !== searchParams.toString()) {
      router.replace(`/meetings?${next}`);
    }
    window.localStorage.setItem(
      "meeting_state",
      JSON.stringify({
        meetingId,
        pageId,
        style,
        outputLanguage,
        pageLimit,
        fullscreen: previewFullscreen
      })
    );
  }, [meetingId, pageId, previewFullscreen, router, searchParams, style, outputLanguage, pageLimit]);

  const handleUpload = async () => {
    if (!file || !backendToken) return;
    setError(null);
    setStatus(language === "zh" ? "?????..." : "Uploading audio...");
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await createMeeting(auth, form);
      setMeetingId(result.meeting_id);
      setStatus(
        language === "zh"
          ? "??????????????????"
          : "Audio stored. Add transcript or start generation."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setStatus(language === "zh" ? "?????" : "Upload failed.");
    }
  };

  const handleCreateFromTranscript = async () => {
    if (!backendToken || !transcript.trim()) return;
    setError(null);
    setStatus(language === "zh" ? "?????..." : "Creating meeting...");
    const form = new FormData();
    form.append("transcript", transcript);
    try {
      const result = await createMeeting(auth, form);
      setMeetingId(result.meeting_id);
      setStatus(language === "zh" ? "??????" : "Meeting created.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create meeting failed.");
      setStatus(language === "zh" ? "?????" : "Create failed.");
    }
  };

  const handleTranscribeAudio = async () => {
    if (!file || !backendToken || !meetingId) return;
    setError(null);
    setIsTranscribing(true);
    setStatus(copy.transcribing);
    try {
      const result = await transcribeMeetingAudio(auth, meetingId, file, outputLanguage);
      setTranscript(result.transcript);
      setStatus(copy.transcriptReady);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transcription failed.");
      setStatus(language === "zh" ? "?????" : "Transcription failed.");
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleGenerate = async () => {
    if (!backendToken) return;
    setError(null);
    let activeMeetingId = meetingId;
    if (!activeMeetingId && transcript.trim()) {
      const form = new FormData();
      form.append("transcript", transcript);
      const result = await createMeeting(auth, form);
      activeMeetingId = result.meeting_id;
      setMeetingId(activeMeetingId);
    }
    if (!activeMeetingId) return;
    if (transcript.trim()) {
      await updateMeetingTranscript(auth, activeMeetingId, transcript);
    }
    setStatus(language === "zh" ? "?????..." : "Processing meeting...");
    setProgress({ stage: "Parsing", percent: 5, message: "Preparing transcript" });
    try {
      const response = await streamMeetingPage(
        auth,
        activeMeetingId,
        style,
        outputLanguage,
        pageLimit
      );
      let buffer = "";
      await consumeSse(response.body!, message => {
        if (message.event === "progress") {
          const payload = message.data ?? {};
          const stage = (payload.stage ?? "Parsing") as MeetingStage;
          const localized =
            language === "zh"
              ? {
                  Parsing: "???...",
                  "Decision Structuring": "????...",
                  "HTML Rendering": "HTML ???...",
                  Finalizing: "???...",
                  Idle: copy.stages[0]
                }[stage as MeetingStage]
              : {
                  Parsing: "Parsing...",
                  "Decision Structuring": "Structuring decisions...",
                  "HTML Rendering": "Rendering HTML...",
                  Finalizing: "Finalizing...",
                  Idle: copy.stages[0]
                }[stage as MeetingStage];
          setProgress({
            stage,
            percent: payload.percent ?? 0,
            message: payload.message ?? ""
          });
          setStatus(localized ?? payload.message ?? "");
        }
        if (message.event === "html") {
          buffer += message.data?.chunk ?? "";
          setHtml(buffer);
        }
        if (message.event === "error") {
          setError(message.data?.message ?? "Generation failed.");
        }
      });

      const normalized = ensureHtmlDocument(buffer);
      const result = await finalizeMeetingPage(
        auth,
        activeMeetingId,
        normalized,
        style,
        outputLanguage,
        pageLimit
      );
      setPageId(result.page_id);
      setHtml(normalized);
      setStatus(language === "zh" ? "????????" : "Meeting decision page ready.");
      setProgress({ stage: "Finalizing", percent: 100, message: "Done" });
      const meetingList = await listMeetings(auth);
      setMeetings(meetingList.meetings || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
      setStatus(language === "zh" ? "?????" : "Generation failed.");
    }
  };
const handleStyleSwitch = async (nextStyle: string) => {
    setStyle(nextStyle);
    if (!meetingId || !backendToken || !html) return;
    setError(null);
    setStatus(language === "zh" ? "重新渲染樣式..." : "Re-rendering style...");
    try {
      const response = await renderMeetingPage(
        auth,
        meetingId,
        nextStyle,
        outputLanguage,
        pageLimit
      );
      let buffer = "";
      await consumeSse(response.body!, message => {
        if (message.event === "progress") {
          const payload = message.data ?? {};
          setProgress({
            stage: payload.stage ?? "Rendering",
            percent: payload.percent ?? 0,
            message: payload.message ?? ""
          });
        }
        if (message.event === "html") {
          buffer += message.data?.chunk ?? "";
          setHtml(buffer);
        }
      });
      const normalized = ensureHtmlDocument(buffer);
      setHtml(normalized);
      if (pageId) {
        await updatePage(auth, pageId, normalized);
      }
      setStatus(language === "zh" ? "樣式已更新。" : "Style updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-render failed.");
      setStatus(language === "zh" ? "渲染失敗。" : "Re-render failed.");
    }
  };

  const handleSaveEdits = async () => {
    if (!pageId || !backendToken) return;
    await updatePage(auth, pageId, html);
    setStatus(language === "zh" ? "已保存。" : "Saved.");
  };

  const downloadHtml = () => {
    if (!html) return;
    const normalized = ensureHtmlDocument(html);
    const blob = new Blob([normalized], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `meeting-page-${meetingId ?? "draft"}.html`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const downloadPdf = async () => {
    if (!pageId || !backendToken) return;
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/pages/${pageId}/pdf`,
      {
        headers: backendToken ? { Authorization: `Bearer ${backendToken}` } : undefined
      }
    );
    if (!response.ok) return;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `meeting-page-${pageId}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="page meeting-page">
      <section className="hero hero-compact">
        <div>
          <div className="eyebrow">Meeting Mode</div>
          <h1 className="hero-title">{copy.title}</h1>
          <p className="hero-subtitle">{copy.subtitle}</p>
        </div>
      </section>

      <div className="review-shell">
        <aside className={`review-side ${leftOpen ? "open" : "collapsed"}`}>
          <div className="side-header">
            <span>{copy.uploadTitle}</span>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setLeftOpen(value => !value)}
            >
              {leftOpen ? (language === "zh" ? "收合" : "Collapse") : (language === "zh" ? "展開" : "Expand")}
            </button>
          </div>
          <div className="panel workspace-input">
          <h2>{copy.uploadTitle}</h2>
          <label className="field">
            {copy.uploadLabel}
            <input
              type="file"
              onChange={event =>
                setFile(event.target.files ? event.target.files[0] : null)
              }
            />
          </label>
          <button type="button" className="button button-primary" onClick={handleUpload}>
            {copy.uploadAction}
          </button>
          <button
            type="button"
            className="button button-ghost"
            onClick={handleTranscribeAudio}
            disabled={!file || !meetingId || isTranscribing}
          >
            {copy.transcribe}
          </button>

          <div className="divider">{copy.pasteLabel}</div>
          <textarea
            className="workspace-textarea"
            placeholder={copy.pastePlaceholder}
            value={transcript}
            onChange={event => setTranscript(event.target.value)}
          />
          <button
            type="button"
            className="button button-ghost"
            onClick={handleCreateFromTranscript}
            disabled={!transcript.trim()}
          >
            {copy.createFromTranscript}
          </button>

          <div className="style-toggle">
            {styleOptions.map(option => (
              <button
                key={option.value}
                type="button"
                className="button button-ghost"
                data-active={style === option.value}
                onClick={() => handleStyleSwitch(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="field-row">
            <label className="field">
              {copy.outputLang}
              <select
                value={outputLanguage}
                onChange={event => setOutputLanguage(event.target.value as "zh" | "en")}
              >
                <option value="en">English</option>
                <option value="zh">中文</option>
              </select>
            </label>
            <label className="field">
              {copy.pageLimit}
              <select
                value={pageLimit}
                onChange={event => setPageLimit(Number(event.target.value))}
              >
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
              </select>
            </label>
          </div>

          <button
            type="button"
            className="button button-primary"
            onClick={handleGenerate}
            disabled={!meetingId}
          >
            {copy.generate}
          </button>

          <div className="status">{status}</div>
          <div className="progress-track">
            <div className="progress-bar" style={{ width: `${progress.percent}%` }} />
          </div>
          <div className="progress-meta">
            <span>{displayStage}</span>
            <span>{progress.percent}%</span>
          </div>
          {error ? <div className="status status-error">{error}</div> : null}
        </div>
        </aside>

        <section className="panel workspace-output review-main">
          <div className="panel-header">
            <div>
              <div className="panel-title">{copy.previewTitle}</div>
              <div className="panel-subtitle">{copy.previewSubtitle}</div>
            </div>
            <div className="panel-actions">
              <button className="button button-ghost" onClick={downloadHtml}>
                {copy.downloadHtml}
              </button>
              <button
                className="button button-ghost"
                disabled={!pageId}
                onClick={downloadPdf}
              >
                {copy.downloadPdf}
              </button>
              <button
                className="button button-ghost"
                onClick={() => setPreviewFullscreen(value => !value)}
              >
                {previewFullscreen ? copy.exitFullscreen : copy.fullscreen}
              </button>
              <button className="button button-ghost" onClick={handleSaveEdits}>
                {copy.save}
              </button>
            </div>
          </div>
          <div
            className={`decision-preview decision-preview--${style} ${
              previewFullscreen ? "is-fullscreen" : ""
            }`}
          >
            {html ? (
              <iframe
                className="decision-frame"
                title="Meeting preview"
                srcDoc={ensureHtmlDocument(html)}
              />
            ) : (
              <div className="empty-state">{copy.empty}</div>
            )}
          </div>
        </section>

        <aside className={`review-side right ${rightOpen ? "open" : "collapsed"}`}>
          <div className="side-header">
            <span>{language === "zh" ? "會議清單" : "Meetings"}</span>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setRightOpen(value => !value)}
            >
              {rightOpen ? (language === "zh" ? "收合" : "Collapse") : (language === "zh" ? "展開" : "Expand")}
            </button>
          </div>
          <div className="panel workspace-input">
            <div className="saved-pages__title">
              {language === "zh" ? "會議清單" : "Meetings"}
            </div>
            <ul>
              {meetings.map(item => (
                <li key={item.meeting_id} className="document-row">
                  <span>{item.title || item.source_filename || item.meeting_id}</span>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => handleSelectMeeting(item.meeting_id)}
                  >
                    {language === "zh" ? "預覽" : "Preview"}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </main>
  );
}
