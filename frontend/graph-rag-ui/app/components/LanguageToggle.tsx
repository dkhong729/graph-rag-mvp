"use client";

import { useLanguage } from "../providers/LanguageProvider";

export default function LanguageToggle() {
  const { language, setLanguage } = useLanguage();

  return (
    <div className="language-toggle" role="group" aria-label="Language toggle">
      <button
        type="button"
        className="language-toggle__button"
        data-active={language === "en" ? "true" : "false"}
        onClick={() => setLanguage("en")}
      >
        EN
      </button>
      <button
        type="button"
        className="language-toggle__button"
        data-active={language === "zh" ? "true" : "false"}
        onClick={() => setLanguage("zh")}
      >
        中文
      </button>
    </div>
  );
}
