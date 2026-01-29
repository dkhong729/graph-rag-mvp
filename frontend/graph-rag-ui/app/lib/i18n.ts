export type Language = "zh" | "en";

type LabelKey =
  | "openWorkspace"
  | "signIn"
  | "homeHeadline"
  | "homeSubtitle"
  | "contact"
  | "navHome"
  | "navWorkspace"
  | "navMeetings"
  | "navDialog"
  | "navLogin"
  | "navSignOut"
  | "navAccount"
  | "themeDark"
  | "themeLight";

const labels: Record<LabelKey, { zh: string; en: string }> = {
  openWorkspace: { en: "Open Workspace", zh: "進入工作區" },
  signIn: { en: "Sign in", zh: "登入" },
  homeHeadline: {
    en: "Turn messy documents into decision-ready pages.",
    zh: "把混亂文件轉成可以直接審閱的決策頁面。"
  },
  homeSubtitle: {
    en: "A single flow for leaders and teams to review irreversible decisions.",
    zh: "一條清楚流程，讓團隊看見不可逆的關鍵決策。"
  },
  contact: { en: "Contact", zh: "聯絡方式" },
  navHome: { en: "Home", zh: "首頁" },
  navWorkspace: { en: "Workspace", zh: "工作區" },
  navMeetings: { en: "Meeting Mode", zh: "會議模式" },
  navDialog: { en: "Decision Dialog", zh: "決策對話" },
  navLogin: { en: "Login", zh: "登入" },
  navSignOut: { en: "Sign out", zh: "登出" },
  navAccount: { en: "Account", zh: "帳號" },
  themeDark: { en: "Dark", zh: "深色" },
  themeLight: { en: "Light", zh: "淺色" }
};

export const getLabel = (key: LabelKey, language: Language) =>
  labels[key]?.[language] ?? labels[key]?.en ?? key;
