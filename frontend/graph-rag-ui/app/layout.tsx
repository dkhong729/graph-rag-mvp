import "./styles/globals.css";
import TopNav from "./components/TopNav";
import { ThemeProvider } from "./providers/ThemeProvider";
import { LanguageProvider } from "./providers/LanguageProvider";
import SessionProvider from "./providers/SessionProvider";
import { getServerSession } from "next-auth";
import { authOptions } from "./api/auth/[...nextauth]/route";

export default async function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);
  return (
    <html lang="en">
      <body>
        <ThemeProvider>
          <LanguageProvider>
            <SessionProvider session={session}>
              <TopNav />
              {children}
            </SessionProvider>
          </LanguageProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
