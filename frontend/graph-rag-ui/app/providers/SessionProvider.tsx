"use client";

import { SessionProvider as NextSessionProvider } from "next-auth/react";
import type { ReactNode } from "react";
import type { Session } from "next-auth";

export default function SessionProvider({
  children,
  session
}: {
  children: ReactNode;
  session: Session | null;
}) {
  return <NextSessionProvider session={session}>{children}</NextSessionProvider>;
}
