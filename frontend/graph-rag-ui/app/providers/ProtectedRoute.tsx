"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useAuth } from "./AuthProvider";

export default function ProtectedRoute({
  children
}: {
  children: ReactNode;
}) {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="protected-shell">
        <div className="protected-banner">
          This workspace is available after login.{" "}
          <Link href="/login">Sign in</Link> to continue.
        </div>
      </div>
    );
  }

  return <div className="protected-shell">{children}</div>;
}
