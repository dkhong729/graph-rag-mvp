# Document Intelligence & Review Platform (MVP)

Decision-first workspace that turns messy documents or meetings into structured, review‑ready HTML/PDF pages.  
Built for fast decision review, auditability, and reuse.

## Features
- Upload PDF/DOCX/TXT or paste text → Decision page (HTML streaming).
- Meeting mode with audio upload + transcript extraction + decision page.
- Decision RAG (ask questions grounded in document/meeting intelligence).
- Save & manage generated pages and documents.
- Google OAuth (optional) + Google Drive import.
- Email verification + password reset flows (token-based).
- PDF export (WeasyPrint library or CLI fallback).

## Tech Stack
- **Frontend:** Next.js (App Router), TypeScript, NextAuth
- **Backend:** FastAPI, Postgres, LangChain (LCEL)
- **LLM:** DeepSeek (chat), OpenAI (audio transcription optional)
- **PDF:** WeasyPrint (library or CLI fallback)

## Architecture (High-level)
```
User input → Extractor (Document/Meeting Intelligence) → DB cache
         → Renderer (HTML streaming) → Preview + Save
         → PDF export (WeasyPrint)
RAG queries → DB intelligence → LLM response
```

## Project Structure
```
/backend
  main.py
  db.py
  extractor.py
  pipelines.py
  transcribe.py
  docker-compose.yml
/frontend/graph-rag-ui
  app/
  app/lib/apiClient.ts
```

## Quick Start (Local)

### 1) Backend
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2) Frontend
```
cd frontend/graph-rag-ui
npm install
npm run dev
```

Frontend defaults to `http://localhost:3000`  
Backend defaults to `http://localhost:8000`

## Docker (Backend + Postgres)
```
cd backend
docker compose up --build
```
Backend will be exposed on `http://localhost:8306`.

## Environment Variables

### Backend (`backend/.env`)
```
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_AUDIO_MODEL=whisper-1

PGDATABASE=decision_pages
PGUSER=postgres
PGPASSWORD=postgres
PGHOST=localhost
PGPORT=5432

WEASYPRINT_DLL_PATH=C:\Program Files\GTK3-Runtime Win64\bin
WEASYPRINT_COMMAND=

EMAIL_VERIFICATION_EXPOSE_TOKEN=true
PASSWORD_RESET_EXPOSE_TOKEN=true
```

### Frontend (`frontend/graph-rag-ui/.env.local`)
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-secret

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

## Google Drive Import
Sign in with Google to grant Drive access.  
Drive file picker appears in **Workspace** sidebar.

## PDF Export (WeasyPrint)
On Windows, WeasyPrint requires GTK runtime. Options:
1) Install GTK3 Runtime and set `WEASYPRINT_DLL_PATH`.
2) Set `WEASYPRINT_COMMAND` to the CLI path to use fallback.

## Key API Endpoints
```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/verify
POST   /api/auth/verify/request
POST   /api/auth/password/request
POST   /api/auth/password/reset

POST   /api/documents
GET    /api/documents
GET    /api/documents/{id}
POST   /api/documents/{id}/generate
POST   /api/documents/{id}/render
POST   /api/documents/{id}/finalize
GET    /api/documents/{id}/intelligence
POST   /api/documents/delete

POST   /api/meetings
POST   /api/meetings/{id}/audio
POST   /api/meetings/{id}/transcript
POST   /api/meetings/{id}/generate
POST   /api/meetings/{id}/render
POST   /api/meetings/{id}/finalize

GET    /api/pages/{id}
GET    /api/pages/{id}/pdf
PUT    /api/pages/{id}
DELETE /api/pages/{id}

POST   /api/rag/ask
```

## Notes
- Extractor runs once per document/meeting and caches in DB.
- Renderer reuses cached intelligence for style/language changes.
- Email verification and password reset return tokens directly when
  `*_EXPOSE_TOKEN=true` (dev mode). In production, wire to email.

---
If you need deployment guidance or CI setup, open an issue or ping me.
