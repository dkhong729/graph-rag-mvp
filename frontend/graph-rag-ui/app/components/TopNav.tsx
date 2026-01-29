"use client";

import Link from "next/link";
import { signOut, useSession } from "next-auth/react";
import { useState } from "react";
import { useTheme } from "../providers/ThemeProvider";
import LanguageToggle from "./LanguageToggle";
import { useLanguage } from "../providers/LanguageProvider";
import { getLabel } from "../lib/i18n";

export default function TopNav() {
  const { data: session, status } = useSession();
  const { theme, toggleTheme } = useTheme();
  const { language } = useLanguage();
  const user = session?.user as { name?: string; email?: string } | undefined;
  const provider = (session?.user as any)?.provider as string | undefined;
  const avatar = (session?.user as any)?.image as string | undefined;
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="top-nav">
      <Link href="/" className="top-nav__brand">
        Decision IRG
      </Link>
      <div className="top-nav__links">
        <Link href="/">{getLabel("navHome", language)}</Link>
        <Link href="/workspace">{getLabel("navWorkspace", language)}</Link>
        <Link href="/meetings">{getLabel("navMeetings", language)}</Link>
        <Link href="/dialog">{getLabel("navDialog", language)}</Link>
      </div>
      <div className="top-nav__actions">
        <LanguageToggle />
        <button
          type="button"
          className="button button-ghost"
          onClick={toggleTheme}
        >
          {theme === "dark"
            ? getLabel("themeDark", language)
            : getLabel("themeLight", language)}
        </button>
        {status === "authenticated" ? (
          <>
            <div className="auth-menu">
              <button
                type="button"
                className="auth-pill"
                onClick={() => setMenuOpen(value => !value)}
              >
                {user?.name ?? user?.email ?? getLabel("navAccount", language)}
              </button>
              {menuOpen ? (
                <div className="auth-dropdown">
                  <div className="auth-profile">
                    {avatar ? <img src={avatar} alt="avatar" /> : null}
                    <div>
                      <div className="auth-name">
                        {user?.name ?? getLabel("navAccount", language)}
                      </div>
                      <div className="auth-email">{user?.email}</div>
                      <div className="auth-provider">
                        {language === "zh" ? "帳號來源" : "Source"}: {provider ?? "local"}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => signOut({ callbackUrl: "/login" })}
                  >
                    {getLabel("navSignOut", language)}
                  </button>
                </div>
              ) : null}
            </div>
          </>
        ) : (
          <Link href="/login" className="auth-pill">
            {getLabel("navLogin", language)}
          </Link>
        )}
      </div>
    </nav>
  );
}
