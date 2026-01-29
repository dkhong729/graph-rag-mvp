import NextAuth, { type NextAuthOptions } from "next-auth";
import type { Account, Profile, Session, User } from "next-auth";
import type { JWT } from "next-auth/jwt";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  session: {
    maxAge: 60 * 60 * 8
  },
  cookies: {
    sessionToken: {
      name: "decision-auth.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/"
      }
    }
  },
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(
        credentials: Record<"email" | "password", string> | undefined
      ) {
        if (!credentials?.email || !credentials.password) return null;
        const response = await fetch(`${apiBaseUrl}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password
          })
        });
        if (!response.ok) return null;
        const result = await response.json();
        return {
          id: result.user.user_id,
          name: result.user.display_name,
          email: credentials.email,
          backendToken: result.token
        };
      }
    }),
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
      authorization: {
        params: {
          scope:
            "openid email profile https://www.googleapis.com/auth/drive.readonly",
          access_type: "offline",
          prompt: "consent"
        }
      }
    })
  ],
  callbacks: {
    async signIn({
      user,
      account,
      profile
    }: {
      user: User;
      account: Account | null;
      profile?: Profile;
    }) {
      if (account?.provider === "google") {
        const email = user.email ?? profile?.email;
        if (!email) return false;
        const response = await fetch(`${apiBaseUrl}/api/auth/oauth`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            display_name: user.name ?? email
          })
        });
        if (!response.ok) return false;
        const result = await response.json();
        (user as any).backendToken = result.token;
        (user as any).id = result.user.user_id;
        (user as any).provider = "google";
      }
      return true;
    },
    async jwt({
      token,
      user,
      account
    }: {
      token: JWT;
      user?: User;
      account?: Account | null;
    }) {
      if (user) {
        token.backendToken = (user as any).backendToken;
        token.id = (user as any).id ?? token.sub;
        token.provider = (user as any).provider ?? token.provider ?? "credentials";
      }
      if (account?.provider === "google") {
        token.googleAccessToken = account.access_token;
        token.googleRefreshToken = account.refresh_token;
      }
      return token;
    },
    async session({ session, token }: { session: Session; token: JWT }) {
      (session as any).backendToken = token.backendToken;
      (session.user as any).id = token.id;
      (session.user as any).provider = token.provider ?? "credentials";
      (session as any).googleAccessToken = (token as any).googleAccessToken;
      (session as any).googleRefreshToken = (token as any).googleRefreshToken;
      return session;
    }
  },
  pages: {
    signIn: "/login"
  }
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
