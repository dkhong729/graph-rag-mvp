"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";
import type { Language } from "../lib/i18n";

type LanguageContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  toggleLanguage: () => void;
};

const LanguageContext = createContext<LanguageContextValue | undefined>(
  undefined
);
const LANGUAGE_KEY = "graph-rag-language";

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>("en");

  useEffect(() => {
    if (typeof document === "undefined") return;
    const stored = window.localStorage.getItem(LANGUAGE_KEY);
    if (stored === "zh" || stored === "en") {
      setLanguage(stored);
      document.documentElement.lang = stored;
      return;
    }
    document.documentElement.lang = language;
    window.localStorage.setItem(LANGUAGE_KEY, language);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.lang = language;
    window.localStorage.setItem(LANGUAGE_KEY, language);
  }, [language]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage,
      toggleLanguage: () =>
        setLanguage(current => (current === "en" ? "zh" : "en"))
    }),
    [language]
  );

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }
  return context;
}
