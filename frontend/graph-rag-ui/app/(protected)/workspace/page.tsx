"use client";

import { useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  createDocument,
  deleteDocuments,
  deletePage,
  finalizeDocumentPage,
  getPage, 
  getDocumentIntelligence,
  listDocuments,
  listDocumentPages,
  renderDocumentPage,
  streamDocumentPage,
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

type WorkspaceStage =
  | "Idle"
  | "Parsing"
  | "Decision Structuring"
  | "HTML Rendering"
  | "Finalizing";

type ProgressState = {
  stage: WorkspaceStage;
  percent: number;
  message: string;
};

export default function WorkspacePage() {
  const { data: session } = useSession();
  const backendToken = (session as any)?.backendToken as string | undefined;
  const googleAccessToken = (session as any)?.googleAccessToken as string | undefined;
  const auth = useMemo(() => ({ token: backendToken }), [backendToken]);
  const { language } = useLanguage();
  const router = useRouter();
  const searchParams = useSearchParams();
  const copy =
    language === "zh"
      ? {
          title: "生成可審閱的決策頁面",
          subtitle: "上傳文件或貼文字，轉成可保存、可下載的決策頁。",
          sourceTitle: "輸入來源",
          sourceHint: "支援 PDF / DOCX / TXT 或貼上文字。",
          titleLabel: "標題（選填）",
          uploadLabel: "上傳檔案",
          pasteLabel: "或貼上文字",
          pastePlaceholder: "貼上會議紀錄、決策備忘或任何需要整理的文字...",
          generate: "生成可用決策頁",
          previewTitle: "決策頁預覽",
          previewSubtitle: "模型產生時即時更新內容。",
          downloadHtml: "下載 HTML",
          downloadPdf: "下載 PDF",
          delete: "刪除",
          fullscreen: "全螢幕",
          exitFullscreen: "退出全螢幕",
          empty: "決策頁會顯示在這裡。",
          savedPages: "已保存頁面",
          stages: ["解析", "決策結構化", "HTML 渲染", "收尾"],
          statusIdle: "等待輸入。",
          docManage: "文件管理",
          preview: "預覽",
          deleteSelected: "刪除選取文件",
          confirmTitle: "確認刪除",
          confirmDesc: (count: number) => `將刪除 ${count} 份文件與相關頁面，確定嗎？`,
          confirmDelete: "確認刪除",
          cancel: "取消",
          outputLang: "輸出語言",
          pageLimit: "頁數上限",
          downloadIntelligence: "下載 Intelligence JSON",
          viewDiff: "查看版本差異",
          diffTitle: "Document Intelligence 差異",
          driveTitle: "Google Drive",
          driveFetch: "載入雲端檔案",
          driveImport: "匯入",
          driveEmpty: "目前沒有可匯入的檔案。",
          driveLoading: "載入中...",
          driveConnect: "請使用 Google 登入以匯入 Drive 檔案。"
        }
      : {
          title: "Generate decision-ready pages",
          subtitle:
            "Upload a document or paste text. We translate it into a clean decision page you can save and download.",
          sourceTitle: "Source Input",
          sourceHint: "PDF / DOCX / TXT or paste raw notes.",
          titleLabel: "Title (optional)",
          uploadLabel: "Upload file",
          pasteLabel: "or paste text",
          pastePlaceholder:
            "Paste meeting notes, planning docs, or any decision-heavy text...",
          generate: "Generate decision page",
          previewTitle: "Decision Page Preview",
          previewSubtitle: "Streaming output updates as the model renders.",
          downloadHtml: "Download HTML",
          downloadPdf: "Download PDF",
          delete: "Delete",
          fullscreen: "Fullscreen",
          exitFullscreen: "Exit fullscreen",
          empty: "Your decision page will appear here.",
          savedPages: "Saved Pages",
          stages: ["Parsing", "Decision Structuring", "HTML Rendering", "Finalizing"],
          statusIdle: "Awaiting input.",
          docManage: "Document Management",
          preview: "Preview",
          deleteSelected: "Delete selected",
          confirmTitle: "Confirm deletion",
          confirmDesc: (count: number) =>
            `You are about to delete ${count} documents and their pages.`,
          confirmDelete: "Delete",
          cancel: "Cancel",
          outputLang: "Output language",
          pageLimit: "Page limit",
          downloadIntelligence: "Download Intelligence JSON",
          viewDiff: "View version diff",
          diffTitle: "Document Intelligence Diff",
          driveTitle: "Google Drive",
          driveFetch: "Load Drive files",
          driveImport: "Import",
          driveEmpty: "No Drive files available.",
          driveLoading: "Loading...",
          driveConnect: "Sign in with Google to import Drive files."
        };
  const stageMap: Record<WorkspaceStage, string> = {
    Idle: copy.stages[0],
    Parsing: copy.stages[0],
    "Decision Structuring": copy.stages[1],
    "HTML Rendering": copy.stages[2],
    Finalizing: copy.stages[3]
  };

  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [style, setStyle] = useState("technical");
  const [outputLanguage, setOutputLanguage] = useState<"zh" | "en">("en");
  const [pageLimit, setPageLimit] = useState(2);
  const [status, setStatus] = useState(copy.statusIdle);
  const [progress, setProgress] = useState<ProgressState>({
    stage: "Idle",
    percent: 0,
    message: ""
  });
  const [html, setHtml] = useState("");
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [pageId, setPageId] = useState<string | null>(null);
  const [savedPages, setSavedPages] = useState<any[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewFullscreen, setPreviewFullscreen] = useState(false);
  const [intelligenceModal, setIntelligenceModal] = useState(false);
  const [intelligenceData, setIntelligenceData] = useState<any>(null);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [driveFiles, setDriveFiles] = useState<any[]>([]);
  const [driveLoading, setDriveLoading] = useState(false);
  const [driveError, setDriveError] = useState<string | null>(null);

  const displayStage = stageMap[progress.stage] ?? progress.stage;

  useEffect(() => {
    if (status === "Awaiting input." || status === "等待輸入。") {
      setStatus(copy.statusIdle);
    }
  }, [copy.statusIdle, status]);

  useEffect(() => {
    if (!backendToken) return;
    listDocuments(auth).then(result => setDocuments(result.documents || []));
  }, [auth, backendToken]);

  useEffect(() => {
    const docParam = searchParams.get("document");
    const pageParam = searchParams.get("page");
    const styleParam = searchParams.get("style");
    const langParam = searchParams.get("lang");
    const pagesParam = searchParams.get("pages");
    const fullscreenParam = searchParams.get("fullscreen");
    if (docParam) setDocumentId(docParam);
    if (pageParam) setPageId(pageParam);
    if (styleParam) setStyle(styleParam);
    if (langParam === "zh" || langParam === "en") setOutputLanguage(langParam);
    if (pagesParam) {
      const parsed = Number(pagesParam);
      if (!Number.isNaN(parsed)) setPageLimit(parsed);
    }
    if (fullscreenParam === "1") setPreviewFullscreen(true);
    if (!docParam) {
      const stored = window.localStorage.getItem("workspace_state");
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed.documentId) setDocumentId(parsed.documentId);
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
    if (!documentId) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("document", documentId);
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
      router.replace(`/workspace?${next}`);
    }
    window.localStorage.setItem(
      "workspace_state",
      JSON.stringify({
        documentId,
        pageId,
        style,
        outputLanguage,
        pageLimit,
        fullscreen: previewFullscreen
      })
    );
  }, [documentId, pageId, previewFullscreen, router, searchParams, style, outputLanguage, pageLimit]);

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
  }, [auth, backendToken, html, pageId]);

  const loadDriveFiles = async () => {
    if (!googleAccessToken) {
      setDriveError("Google Drive not connected.");
      return;
    }
    setDriveError(null);
    setDriveLoading(true);
    try {
      const response = await fetch(
        "https://www.googleapis.com/drive/v3/files?fields=files(id,name,mimeType,modifiedTime,size)",
        {
          headers: {
            Authorization: `Bearer ${googleAccessToken}`
          }
        }
      );
      if (!response.ok) {
        throw new Error("Drive request failed.");
      }
      const data = await response.json();
      setDriveFiles(data.files || []);
    } catch (err) {
      setDriveError(err instanceof Error ? err.message : "Drive request failed.");
    } finally {
      setDriveLoading(false);
    }
  };

  const handleImportDriveFile = async (item: any) => {
    if (!googleAccessToken || !backendToken) return;
    setDriveError(null);
    setStatus(language === "zh" ? "匯入中..." : "Importing...");
    try {
      const isGoogleDoc =
        typeof item.mimeType === "string" &&
        item.mimeType.startsWith("application/vnd.google-apps");
      const downloadUrl = isGoogleDoc
        ? `https://www.googleapis.com/drive/v3/files/${item.id}/export?mimeType=application/pdf`
        : `https://www.googleapis.com/drive/v3/files/${item.id}?alt=media`;
      const response = await fetch(downloadUrl, {
        headers: {
          Authorization: `Bearer ${googleAccessToken}`
        }
      });
      if (!response.ok) {
        throw new Error("Drive download failed.");
      }
      const blob = await response.blob();
      const filename = isGoogleDoc ? `${item.name}.pdf` : item.name;
      const form = new FormData();
      form.append(
        "file",
        new File([blob], filename, { type: blob.type || "application/pdf" })
      );
      form.append("title", item.name);
      const result = await createDocument(auth, form);
      setDocumentId(result.document_id);
      const docs = await listDocuments(auth);
      setDocuments(docs.documents || []);
      setStatus(language === "zh" ? "匯入完成。" : "Import complete.");
    } catch (err) {
      setDriveError(err instanceof Error ? err.message : "Drive import failed.");
      setStatus(language === "zh" ? "匯入失敗。" : "Import failed.");
    }
  };

  const handleGenerate = async () => {
    if (!backendToken) return;
    setError(null);
    setStatus(language === "zh" ? "正在上傳來源..." : "Uploading source...");
    setHtml("");
    setPageId(null);
    setProgress({ stage: "Parsing", percent: 0, message: "Reading input" });

    const form = new FormData();
    if (file) {
      form.append("file", file);
    } else {
      form.append("text", text);
    }
    if (title) {
      form.append("title", title);
    }

    try {
      const { document_id } = await createDocument(auth, form);
      setDocumentId(document_id);

      const response = await streamDocumentPage(auth, document_id, style, outputLanguage, pageLimit);
      let buffer = "";

      await consumeSse(response.body!, message => {
        if (message.event === "progress") {
          const payload = message.data ?? {};
          const stage = (payload.stage ?? "Parsing") as WorkspaceStage;
          const localized =
            language === "zh"
              ? {
                  Parsing: "解析中...",
                  "Decision Structuring": "決策結構化中...",
                  "HTML Rendering": "HTML 渲染中...",
                  Finalizing: "收尾中...",
                  Idle: copy.stages[0]
                }[stage]
              : {
                  Parsing: "Parsing...",
                  "Decision Structuring": "Structuring decisions...",
                  "HTML Rendering": "Rendering HTML...",
                  Finalizing: "Finalizing...",
                  Idle: copy.stages[0]
                }[stage];
          setProgress({
            stage,
            percent: payload.percent ?? 0,
            message: payload.message ?? ""
          });
          if (localized) {
            setStatus(localized);
          }
        }
        if (message.event === "html") {
          buffer += message.data?.chunk ?? "";
          setHtml(buffer);
        }
        if (message.event === "error") {
          setError(message.data?.message ?? "Generation failed.");
        }
      });

      setStatus(language === "zh" ? "正在收尾..." : "Finalizing...");
      setProgress({ stage: "Finalizing", percent: 95, message: "Saving page" });
      const normalized = ensureHtmlDocument(buffer);
      const result = await finalizeDocumentPage(
        auth,
        document_id,
        normalized,
        style,
        outputLanguage,
        pageLimit
      );
      setPageId(result.page_id);
      const pages = await listDocumentPages(auth, document_id);
      setSavedPages(pages.pages || []);
      setHtml(normalized);
      setStatus(language === "zh" ? "決策頁完成。" : "Decision page ready.");
      setProgress({ stage: "Finalizing", percent: 100, message: "Done" });
      const docs = await listDocuments(auth);
      setDocuments(docs.documents || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
      setStatus(language === "zh" ? "生成失敗。" : "Generation failed.");
    }
  };

  const handleStyleSwitch = async (nextStyle: string) => {
    setStyle(nextStyle);
    if (!documentId || !backendToken || !html) return;
    setStatus(language === "zh" ? "重新渲染樣式..." : "Re-rendering style...");
    setError(null);
    try {
      const response = await renderDocumentPage(
        auth,
        documentId,
        nextStyle,
        outputLanguage,
        pageLimit
      );
      let buffer = "";
      await consumeSse(response.body!, message => {
        if (message.event === "progress") {
          const payload = message.data ?? {};
          setProgress({
            stage: (payload.stage ?? "HTML Rendering") as WorkspaceStage,
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

  const handleLoadPage = async (targetPageId: string) => {
    if (!backendToken) return;
    const page = await getPage(auth, targetPageId);
    const normalized = ensureHtmlDocument(page.html);
    setHtml(normalized);
    setPageId(targetPageId);
  };

  const handleSelectDocument = async (docId: string) => {
    setDocumentId(docId);
    setPageId(null);
    setHtml("");
    const pages = await listDocumentPages(auth, docId);
    setSavedPages(pages.pages || []);
    if (pages.pages && pages.pages.length) {
      const latest = pages.pages[0];
      const page = await getPage(auth, latest.page_id);
      setHtml(ensureHtmlDocument(page.html));
      setPageId(latest.page_id);
    }
  };

  const handleDeletePage = async () => {
    if (!pageId || !backendToken) return;
    await deletePage(auth, pageId);
    setHtml("");
    setPageId(null);
    if (documentId) {
      const pages = await listDocumentPages(auth, documentId);
      setSavedPages(pages.pages || []);
    }
  };

  const toggleDocumentSelection = (docId: string) => {
    setSelectedDocs(prev => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  const handleBulkDelete = async () => {
    if (!backendToken || selectedDocs.size === 0) return;
    await deleteDocuments(auth, Array.from(selectedDocs));
    setSelectedDocs(new Set());
    setShowDeleteModal(false);
    const docs = await listDocuments(auth);
    setDocuments(docs.documents || []);
    window.localStorage.setItem("documents_updated", String(Date.now()));
    if (documentId && selectedDocs.has(documentId)) {
      setDocumentId(null);
      setPageId(null);
      setHtml("");
      setSavedPages([]);
    }
  };

  const handleDownloadIntelligence = async () => {
    if (!documentId || !backendToken) return;
    const data = await getDocumentIntelligence(auth, documentId);
    const blob = new Blob([JSON.stringify(data.current, null, 2)], {
      type: "application/json"
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `document-intelligence-${documentId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleViewDiff = async () => {
    if (!documentId || !backendToken) return;
    const data = await getDocumentIntelligence(auth, documentId);
    setIntelligenceData(data);
    setIntelligenceModal(true);
  };

  const downloadHtml = () => {
    if (!html) return;
    const normalized = ensureHtmlDocument(html);
    const blob = new Blob([normalized], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `decision-page-${documentId ?? "draft"}.html`;
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
    link.download = `decision-page-${pageId}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="page workspace-page">
      <section className="hero hero-compact">
        <div>
          <div className="eyebrow">Workspace</div>
          <h1 className="hero-title">{copy.title}</h1>
          <p className="hero-subtitle">{copy.subtitle}</p>
        </div>
      </section>

      <div
        className={`review-shell ${
          leftOpen ? "left-open" : "left-collapsed"
        } ${rightOpen ? "right-open" : "right-collapsed"}`}
      >
        <aside className={`review-side ${leftOpen ? "open" : "collapsed"}`}>
          <div className="side-header">
            <span>{copy.sourceTitle}</span>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setLeftOpen(value => !value)}
            >
              {leftOpen ? (language === "zh" ? "收合" : "Collapse") : (language === "zh" ? "展開" : "Expand")}
            </button>
          </div>
          <div className="panel workspace-input">
          <h2>{copy.sourceTitle}</h2>
          <p className="muted">{copy.sourceHint}</p>
          <label className="field">
            {copy.titleLabel}
            <input
              type="text"
              value={title}
              onChange={event => setTitle(event.target.value)}
            />
          </label>
          <label className="field">
            {copy.uploadLabel}
            <input
              type="file"
              onChange={event =>
                setFile(event.target.files ? event.target.files[0] : null)
              }
            />
          </label>
          <div className="drive-panel">
            <div className="saved-pages__title">{copy.driveTitle}</div>
            {googleAccessToken ? (
              <>
                <button
                  type="button"
                  className="button button-ghost"
                  onClick={loadDriveFiles}
                  disabled={driveLoading}
                >
                  {driveLoading ? copy.driveLoading : copy.driveFetch}
                </button>
                {driveError ? <div className="status status-error">{driveError}</div> : null}
                <ul>
                  {driveFiles.length ? (
                    driveFiles.map(item => (
                      <li key={item.id} className="document-row">
                        <span>{item.name}</span>
                        <button
                          type="button"
                          className="button button-ghost"
                          onClick={() => handleImportDriveFile(item)}
                        >
                          {copy.driveImport}
                        </button>
                      </li>
                    ))
                  ) : (
                    <li className="muted">{copy.driveEmpty}</li>
                  )}
                </ul>
              </>
            ) : (
              <div className="status">{copy.driveConnect}</div>
            )}
          </div>
          <div className="divider">{copy.pasteLabel}</div>
          <textarea
            className="workspace-textarea"
            placeholder={copy.pastePlaceholder}
            value={text}
            onChange={event => setText(event.target.value)}
          />

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
            disabled={!file && !text}
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
          <div className="stage-track">
            {copy.stages.map(stage => (
              <div
                key={stage}
                className={`stage-pill ${displayStage === stage ? "active" : ""}`}
              >
                {stage}
              </div>
            ))}
          </div>
          {error ? <div className="status status-error">{error}</div> : null}

          {savedPages.length ? (
            <div className="saved-pages">
              <div className="saved-pages__title">{copy.savedPages}</div>
              <ul>
                {savedPages.map(page => (
                  <li key={page.page_id}>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => handleLoadPage(page.page_id)}
                    >
                      {page.page_id} · {page.style}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
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
              <button
                className="button button-ghost"
                disabled={!pageId}
                onClick={handleDeletePage}
              >
                {copy.delete}
              </button>
            </div>
          </div>
          <div
            className={`decision-preview decision-preview--${style} ${
              previewFullscreen ? "is-fullscreen" : ""
            }`}
          >
            {previewFullscreen ? (
              <button
                type="button"
                className="button button-ghost fullscreen-exit"
                onClick={() => setPreviewFullscreen(false)}
              >
                {copy.exitFullscreen}
              </button>
            ) : null}
            {html ? (
              <iframe
                className="decision-frame"
                title="Decision preview"
                srcDoc={ensureHtmlDocument(html)}
              />
            ) : (
              <div className="empty-state">{copy.empty}</div>
            )}
          </div>
        </section>

        <aside className={`review-side right ${rightOpen ? "open" : "collapsed"}`}>
          <div className="side-header">
            <span>{copy.docManage}</span>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setRightOpen(value => !value)}
            >
              {rightOpen ? (language === "zh" ? "收合" : "Collapse") : (language === "zh" ? "展開" : "Expand")}
            </button>
          </div>
          <div className="panel workspace-input">
            <div className="saved-pages__title">{copy.docManage}</div>
            <ul>
              {documents.map(doc => (
                <li key={doc.document_id} className="document-row">
                  <label className="document-select">
                    <input
                      type="checkbox"
                      checked={selectedDocs.has(doc.document_id)}
                      onChange={() => toggleDocumentSelection(doc.document_id)}
                    />
                    <span>{doc.title || doc.source_filename || doc.document_id}</span>
                  </label>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => handleSelectDocument(doc.document_id)}
                  >
                    {copy.preview}
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="button button-ghost"
              disabled={selectedDocs.size === 0}
              onClick={() => setShowDeleteModal(true)}
            >
              {copy.deleteSelected}
            </button>
            <button
              type="button"
              className="button button-ghost"
              disabled={!documentId}
              onClick={handleDownloadIntelligence}
            >
              {copy.downloadIntelligence}
            </button>
            <button
              type="button"
              className="button button-ghost"
              disabled={!documentId}
              onClick={handleViewDiff}
            >
              {copy.viewDiff}
            </button>
          </div>
        </aside>
      </div>
      {showDeleteModal ? (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>{copy.confirmTitle}</h3>
            <p>{copy.confirmDesc(selectedDocs.size)}</p>
            <div className="modal-actions">
              <button
                type="button"
                className="button button-primary"
                onClick={handleBulkDelete}
              >
                {copy.confirmDelete}
              </button>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => setShowDeleteModal(false)}
              >
                {copy.cancel}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {intelligenceModal ? (
        <div className="modal-backdrop">
          <div className="modal modal-wide">
            <h3>{copy.diffTitle}</h3>
            <div className="diff-grid">
              <div>
                <div className="saved-pages__title">Current</div>
                <pre>{JSON.stringify(intelligenceData?.current ?? {}, null, 2)}</pre>
              </div>
              <div>
                <div className="saved-pages__title">Previous</div>
                <pre>{JSON.stringify(intelligenceData?.previous ?? {}, null, 2)}</pre>
              </div>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="button button-ghost"
                onClick={() => setIntelligenceModal(false)}
              >
                {copy.cancel}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
