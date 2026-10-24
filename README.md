# AI Project Builder

A React + Vite frontend and FastAPI backend for generating project code from a topic/specification, previewing files, downloading a ZIP, and publishing files to GitHub after OAuth authorization.

## Features
- Topic/specification input and TXT, PDF, DOCX, and image uploads (image OCR is optional and requires Tesseract).
- Server-side AI generation through an OpenAI-compatible Chat Completions API.
- File tree and source preview.
- Safe ZIP download (sensitive files and build/cache directories excluded).
- GitHub OAuth login, repository listing/creation, and commit-based publishing.
- Per-session project ownership, upload size/type checks, path validation, and publish confirmation.

## Requirements
- Python 3.10+
- Node.js 20+
- An AI provider API key and compatible endpoint (optional for demo mode; generation returns a clearly labelled starter project if no AI key is configured).
- GitHub OAuth App credentials for GitHub publishing.

## Setup

### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```
Edit `backend/.env`:
- `SESSION_SECRET`: replace with a long random secret.
- `AI_API_KEY`: your provider API key.
- `AI_BASE_URL`: OpenAI-compatible API base URL, e.g. `https://api.openai.com/v1`.
- `AI_MODEL`: a model supported by your provider.
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`: OAuth App settings. The callback URL must exactly match the configured URL, e.g. `http://localhost:8000/api/github/callback`.
- `FRONTEND_ORIGIN=http://localhost:5173`

For GitHub OAuth, configure the OAuth App homepage URL as `http://localhost:5173` and authorization callback URL as the backend callback above. The app requests the `repo` scope because publishing to private repositories requires it. For public-only publishing, adjust the scope to `public_repo` in `app/main.py`.

### 2. Frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

## Important configuration notes
- OAuth callback and session cookie work best when frontend and backend share the same hostname (`localhost` in this setup). Do not mix `localhost` and `127.0.0.1`.
- Set a strong `SESSION_SECRET`; use HTTPS and secure cookies in production.
- This starter stores projects in process memory, so restarting the backend clears generated projects and sessions. Use a database/object store for production.
- AI generation depends on the configured provider. The app uses strict JSON output instructions and validates returned paths. Provider-specific structured output may require adapting `generate_with_ai`.
- Image OCR requires the optional system package Tesseract plus `pytesseract`; PDF/DOCX parsing is handled by Python libraries.
- GitHub OAuth is real, but cannot work until OAuth credentials and callback settings are configured. The app never asks users for GitHub passwords or PATs.
- GitHub publishing confirms before sending the request and uses Git Trees/Commits API to upload files. Existing branch history is preserved. A conflicting existing path is updated by committing a new tree; users must confirm overwrite.
- This is a runnable starter, not a hardened multi-tenant production service. Add persistent storage, rate limiting, CSRF protection appropriate to your deployment, audit logging, and secret scanning before public deployment.

## API endpoints
- `POST /api/projects/analyze`
- `POST /api/projects/generate`
- `GET /api/projects/{project_id}/files`
- `GET /api/projects/{project_id}/download`
- `GET /api/github/login`
- `GET /api/github/callback`
- `GET /api/github/repositories`
- `POST /api/github/publish`
- `GET /api/health`

## Test
```bash
cd backend
pytest
```
