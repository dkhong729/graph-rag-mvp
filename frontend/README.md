# Decision Translator MVP

This product turns messy documents or meeting records into decision‑ready pages
that are editable, reusable, and downloadable (HTML + PDF). The system is built
as a single, linear workflow with login, CRUD, and persistent outputs.

## Features
- Document → Decision page (HTML/PDF) with streaming output
- Meeting audio → Decision meeting page (layered facts / stances / values)
- Decision dialog grounded in stored contexts/personas
- Full CRUD for generated pages
- Multi‑style HTML rendering (technical / business / executive)

## Architecture
- Frontend: Next.js (App Router) + React
- Backend: FastAPI + LangChain v1.0 (LCEL)
- Database: PostgreSQL
- LLM: DeepSeek (via OpenAI‑compatible API)

## Quickstart

1) Configure environment
```
cp .env.example .env
```
Fill in `DEEPSEEK_API_KEY` and `FILE_ENCRYPTION_KEY`.

2) Start PostgreSQL (or use docker-compose)

3) Backend
```
cd backend
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

4) Frontend
```
cd frontend/graph-rag-ui
npm install
npm run dev
```

## Core Endpoints
- `POST /api/documents` upload file or text
- `POST /api/documents/{id}/generate` stream HTML
- `POST /api/documents/{id}/finalize` store HTML + contexts
- `GET /api/pages/{id}/pdf` download PDF
- `POST /api/meetings` upload audio
- `POST /api/meetings/{id}/generate` stream HTML
- `POST /api/rag/ask` decision dialog

## Notes
- All files are encrypted at rest (Fernet key required).
- No test_mode or playground flows exist.
- LLM is constrained to use provided context only.
