import io, json, os, re, secrets, time, zipfile, base64
from typing import Optional
from urllib.parse import urlencode
import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader
from docx import Document

APP_DIR = os.path.dirname(__file__)
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-only-change-this-secret-before-deployment")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
BACKEND_ORIGIN = os.getenv("BACKEND_ORIGIN", "http://localhost:8000")
MAX_UPLOAD = int(os.getenv("MAX_UPLOAD_MB", "8")) * 1024 * 1024

app = FastAPI(title="AI Project Builder API", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=False, max_age=60*60*8)
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN], allow_credentials=True, allow_methods=["GET","POST","OPTIONS"], allow_headers=["Content-Type"])

# In-memory store for a local runnable starter. Use persistent storage in production.
PROJECTS = {}
GITHUB_TOKENS = {}  # session_id -> access token; do not log tokens
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

EXCLUDED_PARTS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", ".pytest_cache"}
EXCLUDED_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "credentials.json"}
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*['\"]?[^\\s'\"]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
]

def clean_path(path: str) -> str:
    path = str(path).replace("\\", "/").strip()
    if not path or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValueError("Invalid absolute or empty path")
    parts = path.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError("Invalid path segment")
    if any(p in EXCLUDED_PARTS for p in parts) or parts[-1] in EXCLUDED_NAMES:
        raise ValueError("Sensitive or generated path is excluded")
    if len(path) > 240 or any(not SAFE_NAME.match(p) for p in parts):
        raise ValueError("Unsupported path characters")
    return path

def safe_files(files):
    out = {}
    for path, content in files.items():
        try: p = clean_path(path)
        except ValueError: continue
        if not isinstance(content, str): continue
        if len(content.encode("utf-8")) > 500_000: continue
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            # Avoid silently shipping likely credentials; skip and let user regenerate/edit.
            continue
        out[p] = content
    if not out:
        raise ValueError("No safe files remain after validation")
    return out

def session_id(request: Request):
    sid = request.session.get("sid")
    if not sid:
        sid = secrets.token_urlsafe(24)
        request.session["sid"] = sid
    return sid

def get_project(request: Request, project_id: str):
    p = PROJECTS.get(project_id)
    if not p or p["owner"] != session_id(request):
        raise HTTPException(404, "Project not found in this session")
    return p

def starter_files(topic: str, language: str):
    safe_topic = topic.replace("<", "&lt;").replace(">", "&gt;")[:500]
    return {
      "README.md": f"# Generated Project\n\n## Topic\n{safe_topic}\n\n## Run\n\nThis is a starter scaffold generated because no AI API key is configured. Add your implementation and follow the setup steps below.\n",
      ".gitignore": " .env\n__pycache__/\n.venv/\nnode_modules/\ndist/\n",
      ".env.example": "# Add required environment variables here; never commit a real .env file.\n",
      "requirements.txt": "# Python dependencies for your project\n",
      "src/main.py": f'"""Starter scaffold for: {safe_topic}"""\n\n\ndef main():\n    print("Project scaffold ready. Implement: {safe_topic}")\n\n\nif __name__ == "__main__":\n    main()\n'
    }

async def generate_with_ai(topic: str, language: str, framework: str):
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        return starter_files(topic, language), "starter"
    base = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("AI_MODEL", "gpt-4o-mini")
    system = """You are a senior software engineer. Generate a coherent, runnable, beginner-friendly project codebase.
Return ONLY valid JSON in this schema: {"files":[{"path":"relative/path","content":"full file text"}]}.
Include README.md, .gitignore, .env.example, dependency files, tests where practical. Never include real secrets, .env, binary files, node_modules, build output, or credentials. Use relative safe paths. Keep code consistent and document setup. Limit to 25 files and each file to 30KB. Do not use markdown fences."""
    user = f"Project topic and requirements:\n{topic[:12000]}\n\nPreferred language: {language}\nPreferred framework: {framework}\nGenerate the complete useful MVP codebase."
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"},
            json={"model":model,"temperature":0.2,"messages":[{"role":"system","content":system},{"role":"user","content":user}]})
    if response.status_code >= 400:
        raise HTTPException(502, f"AI provider error ({response.status_code}). Check AI provider configuration.")
    try:
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        raw = parsed["files"]
        if not isinstance(raw, list) or len(raw) > 25: raise ValueError()
        mapping = {item["path"]: item["content"] for item in raw if isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("content"), str)}
        if not mapping: raise ValueError()
        return safe_files(mapping), "ai"
    except Exception:
        raise HTTPException(502, "AI response was not valid project-file JSON. Try again or simplify the requirements.")

def extract_upload(filename: str, content: bytes):
    ext = os.path.splitext(filename.lower())[1]
    try:
        if ext == ".txt": return content.decode("utf-8", errors="replace")
        if ext == ".pdf":
            reader = PdfReader(io.BytesIO(content))
            return "\n".join((page.extract_text() or "") for page in reader.pages)[:12000]
        if ext == ".docx":
            doc = Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)[:12000]
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(io.BytesIO(content))
                return pytesseract.image_to_string(img)[:12000]
            except Exception:
                raise HTTPException(400, "Image OCR is unavailable. Install Tesseract and Pillow, or paste the specification text.")
    except HTTPException: raise
    except Exception:
        raise HTTPException(400, "Could not extract text from the uploaded document.")
    raise HTTPException(415, "Unsupported file type. Upload PDF, DOCX, TXT, PNG, JPG, or WEBP.")

class GenerateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=12000)
    language: str = Field(default="Python", max_length=80)
    framework: str = Field(default="FastAPI", max_length=80)

class PublishRequest(BaseModel):
    project_id: str
    repository: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=350)
    visibility: str = "private"
    branch: str = Field(default="main", min_length=1, max_length=100)
    create_new: bool = False
    confirm: bool = False
    overwrite: bool = False

@app.get("/api/health")
def health():
    return {"status":"ok","ai_configured":bool(os.getenv("AI_API_KEY")),"github_configured":bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))}

@app.post("/api/projects/analyze")
async def analyze(request: Request, topic: str = Form(default=""), file: Optional[UploadFile] = File(default=None)):
    text = topic.strip()
    if file:
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD: raise HTTPException(413, "Upload exceeds configured size limit")
        extracted = extract_upload(file.filename or "upload.txt", data)
        text = (text + "\n\n" + extracted).strip()
    if len(text) < 3: raise HTTPException(400, "Enter a topic or upload a specification file")
    return {"topic":text[:12000], "characters":len(text), "summary":text[:500], "requirements_detected": [line.strip("- •") for line in text.splitlines() if line.strip()][:12]}

@app.post("/api/projects/generate")
async def generate(req: GenerateRequest, request: Request):
    sid = session_id(request)
    files, mode = await generate_with_ai(req.topic, req.language, req.framework)
    pid = secrets.token_urlsafe(12)
    PROJECTS[pid] = {"owner":sid,"topic":req.topic,"language":req.language,"framework":req.framework,"files":files,"mode":mode,"created":int(time.time())}
    return {"project_id":pid,"mode":mode,"file_count":len(files),"files":[{"path":p,"size":len(c.encode("utf-8"))} for p,c in sorted(files.items())],"message":"Project generated" if mode=="ai" else "Starter scaffold created; configure AI_API_KEY for full AI generation."}

@app.get("/api/projects/{project_id}/files")
def project_files(project_id: str, request: Request):
    p = get_project(request, project_id)
    return {"project_id":project_id,"files":[{"path":name,"content":content,"size":len(content.encode("utf-8"))} for name,content in sorted(p["files"].items())],"mode":p["mode"]}

@app.get("/api/projects/{project_id}/download")
def download(project_id: str, request: Request):
    p = get_project(request, project_id)
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in p["files"].items():
            try: safe = clean_path(name)
            except ValueError: continue
            z.writestr(safe, content)
    memory.seek(0)
    return StreamingResponse(memory, media_type="application/zip", headers={"Content-Disposition":f'attachment; filename="ai-project-{project_id}.zip"'})

@app.get("/api/github/login")
def github_login(request: Request):
    client_id = os.getenv("GITHUB_CLIENT_ID", "")
    if not client_id: raise HTTPException(503, "GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in backend/.env.")
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    params = {"client_id":client_id,"redirect_uri":os.getenv("GITHUB_REDIRECT_URI",f"{BACKEND_ORIGIN}/api/github/callback"),"scope":"repo","state":state}
    return RedirectResponse("https://github.com/login/oauth/authorize?"+urlencode(params))

@app.get("/api/github/callback")
async def github_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error: return RedirectResponse(FRONTEND_ORIGIN + "/?github_error=authorization_denied")
    expected = request.session.pop("oauth_state", None)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(400, "Invalid OAuth state")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post("https://github.com/login/oauth/access_token",
          headers={"Accept":"application/json"},
          json={"client_id":os.getenv("GITHUB_CLIENT_ID"),"client_secret":os.getenv("GITHUB_CLIENT_SECRET"),"code":code,"redirect_uri":os.getenv("GITHUB_REDIRECT_URI",f"{BACKEND_ORIGIN}/api/github/callback")})
    data = r.json()
    token = data.get("access_token")
    if not token: return RedirectResponse(FRONTEND_ORIGIN + "/?github_error=token_exchange_failed")
    GITHUB_TOKENS[session_id(request)] = token
    return RedirectResponse(FRONTEND_ORIGIN + "/?github_connected=1")

async def github_request(request: Request, method: str, path: str, **kwargs):
    token = GITHUB_TOKENS.get(session_id(request))
    if not token: raise HTTPException(401, "Connect GitHub first")
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.request(method, "https://api.github.com"+path,
          headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},
          **kwargs)
    if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
        raise HTTPException(429, "GitHub API rate limit reached. Wait and try again.")
    if r.status_code >= 400:
        detail = "GitHub API request failed"
        try: detail = r.json().get("message", detail)
        except Exception: pass
        raise HTTPException(r.status_code if r.status_code < 500 else 502, detail)
    return r.json() if r.content else {}

@app.get("/api/github/repositories")
async def repositories(request: Request):
    data = await github_request(request, "GET", "/user/repos", params={"per_page":100,"sort":"updated","affiliation":"owner,collaborator"})
    return {"repositories":[{"full_name":x["full_name"],"name":x["name"],"private":x["private"],"default_branch":x.get("default_branch") or "main","html_url":x["html_url"]} for x in data]}

@app.post("/api/github/publish")
async def publish(req: PublishRequest, request: Request):
    if not req.confirm: raise HTTPException(400, "Explicit confirmation is required before publishing")
    if req.visibility not in ("public","private"): raise HTTPException(400, "Visibility must be public or private")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", req.repository) or req.repository in (".",".."):
        raise HTTPException(400, "Invalid repository name")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", req.branch) or ".." in req.branch:
        raise HTTPException(400, "Invalid branch name")
    p = get_project(request, req.project_id)
    files = safe_files(p["files"])
    token = GITHUB_TOKENS.get(session_id(request))
    if not token: raise HTTPException(401, "Connect GitHub first")
    if req.create_new:
        repo = await github_request(request, "POST", "/user/repos", json={"name":req.repository,"description":req.description,"private":req.visibility=="private","auto_init":True})
        owner_repo = repo["full_name"]
        branch = req.branch
    else:
        # Resolve owner from authenticated user and target repository name or owner/name.
        me = await github_request(request, "GET", "/user")
        owner_repo = req.repository if "/" in req.repository else f'{me["login"]}/{req.repository}'
        repo = await github_request(request, "GET", f"/repos/{owner_repo}")
        branch = req.branch
    # Branch ref -> base tree; create initial commit if repository has no commit yet.
    try:
        ref = await github_request(request, "GET", f"/repos/{owner_repo}/git/ref/heads/{branch}")
        base_commit = await github_request(request, "GET", f'/repos/{owner_repo}/git/commits/{ref["object"]["sha"]}')
        base_tree = base_commit["tree"]["sha"]
        parent_sha = ref["object"]["sha"]
    except HTTPException as e:
        if e.status_code not in (404, 409): raise
        if not req.create_new: raise HTTPException(404, f"Branch '{branch}' not found. Choose an existing branch or create the repository first.")
        # Newly created repository may use main/master; initialize by writing a root commit with no parent.
        base_tree = None
        parent_sha = None
    tree_items = []
    for path, content in files.items():
        tree_items.append({"path":path,"mode":"100644","type":"blob","content":content})
    tree_payload = {"tree":tree_items}
    if base_tree: tree_payload["base_tree"] = base_tree
    tree = await github_request(request, "POST", f"/repos/{owner_repo}/git/trees", json=tree_payload)
    commit_payload = {"message":"Add generated project from AI Project Builder","tree":tree["sha"]}
    if parent_sha: commit_payload["parents"] = [parent_sha]
    commit = await github_request(request, "POST", f"/repos/{owner_repo}/git/commits", json=commit_payload)
    await github_request(request, "PATCH", f"/repos/{owner_repo}/git/refs/heads/{branch}", json={"sha":commit["sha"],"force":False}) if parent_sha else await github_request(request, "POST", f"/repos/{owner_repo}/git/refs", json={"ref":f"refs/heads/{branch}","sha":commit["sha"]})
    return {"success":True,"repository_url":repo.get("html_url",f'https://github.com/{owner_repo}'),"commit_url":commit.get("html_url"),"branch":branch,"files_published":len(files)}

@app.get("/")
def root():
    return {"message":"AI Project Builder API","docs":"/docs"}
