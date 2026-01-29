"use client";

import Link from "next/link";
import { useLanguage } from "./providers/LanguageProvider";
import { getLabel } from "./lib/i18n";

export default function HomePage() {
  const { language } = useLanguage();
  const copy =
    language === "zh"
      ? {
          previewTitle: "決策頁預覽",
          coreQuestion: "核心問題",
          assumptions: "關鍵假設",
          boundaries: "決策邊界",
          workflowTitle: "清楚的工作流程",
          step1Title: "1. 上傳或貼上",
          step1Text: "支援 PDF、DOCX、TXT 或文字。",
          step2Title: "2. 生成決策頁",
          step2Text: "即時顯示解析、結構化與渲染進度。",
          step3Title: "3. 審閱與下載",
          step3Text: "可編輯、保存並下載 HTML / PDF。",
          subtitleTail: "沒有實驗性設定，只有可下載的決策頁面。"
        }
      : {
          previewTitle: "Decision Page Preview",
          coreQuestion: "Core question",
          assumptions: "Assumptions",
          boundaries: "Decision boundaries",
          workflowTitle: "One clear workflow",
          step1Title: "1. Upload or paste",
          step1Text: "Bring PDFs, DOCX, TXT, or raw notes.",
          step2Title: "2. Generate decision page",
          step2Text: "Streaming shows parsing, structuring, and rendering.",
          step3Title: "3. Review & download",
          step3Text: "Edit, save, and export in HTML or PDF.",
          subtitleTail: "No playgrounds, no settings — just clean, editable outputs."
        };

  return (
    <main className="page home-page">
      <section className="hero hero-home">
        <div>
          <div className="eyebrow">Decision Translator</div>
          <h1 className="hero-title">{getLabel("homeHeadline", language)}</h1>
          <p className="hero-subtitle">
            {getLabel("homeSubtitle", language)} {copy.subtitleTail}
          </p>
          <div className="hero-actions">
            <Link href="/workspace" className="button button-primary">
              {getLabel("openWorkspace", language)}
            </Link>
            <Link href="/login" className="button button-ghost">
              {getLabel("signIn", language)}
            </Link>
          </div>
        </div>
        <div className="panel hero-card">
          <div className="hero-card__title">{copy.previewTitle}</div>
          <div className="hero-card__preview">
            <div className="preview-header">Industrial IPC Deployment</div>
            <div className="preview-block">
              <strong>{copy.coreQuestion}</strong>
              <p>Will this deployment risk irreversible downtime?</p>
            </div>
            <div className="preview-block">
              <strong>{copy.assumptions}</strong>
              <ul>
                <li>24/7 operation</li>
                <li>Limited onsite support</li>
              </ul>
            </div>
            <div className="preview-block">
              <strong>{copy.boundaries}</strong>
              <p className="preview-alert">
                Thermal misdesign leads to irreversible production loss.
              </p>
            </div>
          </div>
          <div className="hero-card__contact">
            <span>{getLabel("contact", language)}</span>
            <a href="mailto:yoshikuni2046@gmail.com">yoshikuni2046@gmail.com</a>
          </div>
        </div>
      </section>

      <section className="home-section panel">
        <div className="home-section__title">{copy.workflowTitle}</div>
        <div className="home-steps">
          <div>
            <div className="step-title">{copy.step1Title}</div>
            <p>{copy.step1Text}</p>
          </div>
          <div>
            <div className="step-title">{copy.step2Title}</div>
            <p>{copy.step2Text}</p>
          </div>
          <div>
            <div className="step-title">{copy.step3Title}</div>
            <p>{copy.step3Text}</p>
          </div>
        </div>
      </section>
    </main>
  );
}
