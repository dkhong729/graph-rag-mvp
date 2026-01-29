import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "../api/auth/[...nextauth]/route";

export default async function ProtectedLayout({
  children
}: {
  children: ReactNode;
}) {
  const session = await getServerSession(authOptions);
  if (!session) {
    redirect("/login");
  }
  return <>{children}</>;
}
