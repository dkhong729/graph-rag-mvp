"use client";

import { useEffect, useState } from "react";
import { signIn, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  registerUser,
  requestEmailVerification,
  requestPasswordReset,
  resetPassword,
  verifyEmailToken
} from "@/app/lib/apiClient";
import { useLanguage } from "../providers/LanguageProvider";

export default function LoginPage() {
  const router = useRouter();
  const { status: authStatus } = useSession();
  const { language } = useLanguage();
  const copy =
    language === "zh"
      ? {
          eyebrow: "帳號登入",
          title: "Decision Workspace 登入",
          subtitle: "登入後可存取決策頁與歷史紀錄。",
          signIn: "登入",
          register: "註冊",
          displayName: "顯示名稱",
          username: "使用者名稱",
          email: "Email",
          password: "密碼",
          passwordConfirm: "再次輸入密碼",
          createAccount: "建立帳號",
          signInGoogle: "使用 Google 登入",
          verifyTitle: "信箱驗證",
          verifyCode: "驗證碼",
          verifyAction: "完成驗證",
          resendCode: "重新取得驗證碼",
          forgotPassword: "忘記密碼？",
          resetTitle: "重設密碼",
          resetRequest: "取得重設碼",
          resetCode: "重設碼",
          resetNewPassword: "新密碼",
          resetConfirm: "確認新密碼",
          resetSubmit: "重設密碼",
          backToLogin: "返回登入"
        }
      : {
          eyebrow: "Account Access",
          title: "Decision Workspace Login",
          subtitle: "Sign in to access your decision pages and workspace history.",
          signIn: "Sign In",
          register: "Register",
          displayName: "Display Name",
          username: "Username",
          email: "Email",
          password: "Password",
          passwordConfirm: "Confirm password",
          createAccount: "Create Account",
          signInGoogle: "Sign in with Google",
          verifyTitle: "Email verification",
          verifyCode: "Verification code",
          verifyAction: "Verify email",
          resendCode: "Resend code",
          forgotPassword: "Forgot password?",
          resetTitle: "Reset password",
          resetRequest: "Request reset code",
          resetCode: "Reset code",
          resetNewPassword: "New password",
          resetConfirm: "Confirm new password",
          resetSubmit: "Reset password",
          backToLogin: "Back to login"
        };

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [formStatus, setFormStatus] = useState<string | null>(null);

  const [showVerify, setShowVerify] = useState(false);
  const [verifyToken, setVerifyToken] = useState("");
  const [verifyHint, setVerifyHint] = useState<string | null>(null);

  const [showReset, setShowReset] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [resetPasswordValue, setResetPasswordValue] = useState("");
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState("");
  const [resetStatus, setResetStatus] = useState<string | null>(null);

  useEffect(() => {
    if (authStatus === "authenticated") {
      router.replace("/workspace");
    }
  }, [router, authStatus]);

  const handleSubmit = async () => {
    if (!email || !password) return;
    setFormStatus(mode === "register" ? "Creating account..." : "Authenticating...");
    try {
      if (mode === "register") {
        if (passwordConfirm && passwordConfirm !== password) {
          setFormStatus(language === "zh" ? "兩次密碼不一致" : "Passwords do not match.");
          return;
        }
        const result = await registerUser(
          email,
          password,
          passwordConfirm,
          displayName,
          username
        );
        if (result.verification_required) {
          setShowVerify(true);
          if (result.verification_token) {
            setVerifyHint(result.verification_token);
          }
          setFormStatus(language === "zh" ? "請完成信箱驗證" : "Please verify your email.");
          return;
        }
      }
      const result = await signIn("credentials", {
        redirect: false,
        email,
        password
      });
      if (result?.ok) {
        setFormStatus(null);
        router.push("/workspace");
      } else {
        setFormStatus("Authentication failed.");
      }
    } catch (err) {
      setFormStatus(err instanceof Error ? err.message : "Authentication failed.");
    }
  };

  const handleVerify = async () => {
    if (!verifyToken) return;
    setFormStatus(language === "zh" ? "驗證中..." : "Verifying...");
    try {
      await verifyEmailToken(verifyToken);
      setShowVerify(false);
      setFormStatus(language === "zh" ? "驗證完成，請登入。" : "Verified. Please sign in.");
    } catch (err) {
      setFormStatus(err instanceof Error ? err.message : "Verification failed.");
    }
  };

  const handleResend = async () => {
    if (!email) return;
    setFormStatus(language === "zh" ? "重新寄送中..." : "Requesting code...");
    try {
      const result = await requestEmailVerification(email);
      if (result.verification_token) {
        setVerifyHint(result.verification_token);
      }
      setFormStatus(language === "zh" ? "已寄出驗證碼" : "Verification code sent.");
    } catch (err) {
      setFormStatus(err instanceof Error ? err.message : "Request failed.");
    }
  };

  const handleResetRequest = async () => {
    if (!resetEmail) return;
    setResetStatus(language === "zh" ? "處理中..." : "Requesting...");
    try {
      const result = await requestPasswordReset(resetEmail);
      if (result.reset_token) {
        setResetToken(result.reset_token);
      }
      setResetStatus(language === "zh" ? "已寄出重設碼" : "Reset code sent.");
    } catch (err) {
      setResetStatus(err instanceof Error ? err.message : "Request failed.");
    }
  };

  const handleResetPassword = async () => {
    if (!resetToken || !resetPasswordValue) return;
    if (resetPasswordConfirm && resetPasswordConfirm !== resetPasswordValue) {
      setResetStatus(language === "zh" ? "兩次密碼不一致" : "Passwords do not match.");
      return;
    }
    setResetStatus(language === "zh" ? "重設中..." : "Resetting...");
    try {
      await resetPassword(resetToken, resetPasswordValue, resetPasswordConfirm);
      setResetStatus(language === "zh" ? "重設完成，請登入。" : "Reset complete. Please sign in.");
      setShowReset(false);
    } catch (err) {
      setResetStatus(err instanceof Error ? err.message : "Reset failed.");
    }
  };

  return (
    <main className="page">
      <section className="hero hero-compact">
        <div>
          <div className="eyebrow">{copy.eyebrow}</div>
          <h1 className="hero-title">{copy.title}</h1>
          <p className="hero-subtitle">{copy.subtitle}</p>
        </div>
      </section>

      <div className="panel">
        {showReset ? (
          <div className="login-form">
            <h3>{copy.resetTitle}</h3>
            <label className="context-selector__label">
              {copy.email}
              <input
                type="email"
                value={resetEmail}
                onChange={event => setResetEmail(event.target.value)}
              />
            </label>
            <button type="button" className="button button-ghost" onClick={handleResetRequest}>
              {copy.resetRequest}
            </button>
            <label className="context-selector__label">
              {copy.resetCode}
              <input
                type="text"
                value={resetToken}
                onChange={event => setResetToken(event.target.value)}
              />
            </label>
            <label className="context-selector__label">
              {copy.resetNewPassword}
              <input
                type="password"
                value={resetPasswordValue}
                onChange={event => setResetPasswordValue(event.target.value)}
              />
            </label>
            <label className="context-selector__label">
              {copy.resetConfirm}
              <input
                type="password"
                value={resetPasswordConfirm}
                onChange={event => setResetPasswordConfirm(event.target.value)}
              />
            </label>
            <button type="button" className="button button-primary" onClick={handleResetPassword}>
              {copy.resetSubmit}
            </button>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setShowReset(false)}
            >
              {copy.backToLogin}
            </button>
            {resetStatus ? <div className="status">{resetStatus}</div> : null}
          </div>
        ) : (
          <>
            <div className="login-toggle">
              <button
                type="button"
                className="button button-ghost"
                data-active={mode === "login" ? "true" : "false"}
                onClick={() => setMode("login")}
              >
                {copy.signIn}
              </button>
              <button
                type="button"
                className="button button-ghost"
                data-active={mode === "register" ? "true" : "false"}
                onClick={() => setMode("register")}
              >
                {copy.register}
              </button>
            </div>

            <div className="login-form">
              {mode === "register" ? (
                <>
                  <label className="context-selector__label">
                    {copy.displayName}
                    <input
                      type="text"
                      value={displayName}
                      onChange={event => setDisplayName(event.target.value)}
                    />
                  </label>
                  <label className="context-selector__label">
                    {copy.username}
                    <input
                      type="text"
                      value={username}
                      onChange={event => setUsername(event.target.value)}
                    />
                  </label>
                </>
              ) : null}
              <label className="context-selector__label">
                {copy.email}
                <input
                  type="email"
                  value={email}
                  onChange={event => setEmail(event.target.value)}
                />
              </label>
              <label className="context-selector__label">
                {copy.password}
                <input
                  type="password"
                  value={password}
                  onChange={event => setPassword(event.target.value)}
                />
              </label>
              {mode === "register" ? (
                <label className="context-selector__label">
                  {copy.passwordConfirm}
                  <input
                    type="password"
                    value={passwordConfirm}
                    onChange={event => setPasswordConfirm(event.target.value)}
                  />
                </label>
              ) : null}
              <button type="button" className="button button-primary" onClick={handleSubmit}>
                {mode === "register" ? copy.createAccount : copy.signIn}
              </button>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => {
                  window.location.href = "/api/auth/signin/google?callbackUrl=/workspace";
                }}
              >
                {copy.signInGoogle}
              </button>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => setShowReset(true)}
              >
                {copy.forgotPassword}
              </button>
              {formStatus ? <div className="status">{formStatus}</div> : null}
            </div>
          </>
        )}

        {showVerify ? (
          <div className="login-form">
            <h3>{copy.verifyTitle}</h3>
            {verifyHint ? (
              <div className="status status-info">
                {language === "zh" ? "驗證碼：" : "Code:"} {verifyHint}
              </div>
            ) : null}
            <label className="context-selector__label">
              {copy.verifyCode}
              <input
                type="text"
                value={verifyToken}
                onChange={event => setVerifyToken(event.target.value)}
              />
            </label>
            <button type="button" className="button button-primary" onClick={handleVerify}>
              {copy.verifyAction}
            </button>
            <button type="button" className="button button-ghost" onClick={handleResend}>
              {copy.resendCode}
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}
