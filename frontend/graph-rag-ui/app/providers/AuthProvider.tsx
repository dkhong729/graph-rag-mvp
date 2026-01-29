"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

export type UserIdentity = {
  userId: string;
  displayName?: string;
  token?: string;
};

type AuthContextValue = {
  user: UserIdentity | null;
  status: "anonymous" | "authenticated";
  setUser: (user: UserIdentity | null) => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserIdentity | null>(() => {
    if (typeof window === "undefined") return null;
    const stored = window.localStorage.getItem("decision-auth");
    return stored ? (JSON.parse(stored) as UserIdentity) : null;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (user) {
      window.localStorage.setItem("decision-auth", JSON.stringify(user));
    } else {
      window.localStorage.removeItem("decision-auth");
    }
  }, [user]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status: user ? "authenticated" : "anonymous",
      setUser
    }),
    [user]
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
