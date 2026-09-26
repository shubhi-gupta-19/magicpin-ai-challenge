# magicpin AI Challenge — Vera Merchant AI Assistant

A high-performance, deterministic WhatsApp merchant engagement backend built for the **magicpin AI Challenge**. Re-implements and optimizes **Vera**, magicpin's merchant AI assistant, across five core commercial verticals: **Dentists**, **Salons**, **Restaurants**, **Gyms**, and **Pharmacies**.

---

## 1. Project Overview

Vera engages merchants and their customers across India over WhatsApp. This solution implements:
- The **4-context composition framework** (`CategoryContext`, `MerchantContext`, `TriggerContext`, `CustomerContext`).
- **5 official HTTPS endpoints** (`/v1/healthz`, `/v1/metadata`, `/v1/context`, `/v1/tick`, `/v1/reply`).
- **Vertical-specific deterministic strategies** that ground all message content in verifiable facts, real catalog pricing, locality context, and appropriate clinical or operator registers.
- **Multi-turn conversation state machine** handling WhatsApp Business canned auto-replies, intent handoffs, hostility/opt-outs, and out-of-scope steering.
- **Strict compliance**: Sub-30s latency, zero external URL penalties, first-touch WhatsApp template parameters, and 20-action tick limits.

---

## 2. Implemented Architecture

```
                                  ┌─────────────────────────────┐
                                  │   magicpin Judge Harness    │
                                  │   (Simulated Environment)   │
                                  └──────────────┬──────────────┘
                                                 │
                               HTTP JSON /v1/*   ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FastAPI Backend (bot.py)                               │
│                                                                                        │
│  ┌───────────────────────────┐  ┌────────────────────────────┐  ┌───────────────────┐  │
│  │       Context Store       │  │     Suppression Engine     │  │  Conversation Mgr │  │
│  │ (Atomic, version-tracked) │  │  (Key dedup & expiration)  │  │ (Multi-turn state)│  │
│  └─────────────┬─────────────┘  └──────────────┬─────────────┘  └─────────┬─────────┘  │
│                │                               │                          │            │
│                └───────────────────────┐       │       ┌──────────────────┘            │
│                                        ▼       ▼       ▼                               │
│                          ┌───────────────────────────────────────────┐                 │
│                          │          4-Context Composer Engine        │                 │
│                          │             (Deterministic)               │                 │
│                          └─────────────────────┬─────────────────────┘                 │
│                                                │                                       │
│          ┌───────────────┬─────────────────────┼─────────────────────┬──────────────┐  │
│          ▼               ▼                     ▼                     ▼              ▼  │
│     [Dentists]        [Salons]           [Restaurants]             [Gyms]     [Pharmacies]│
│  (Clinical Peer)   (Warm Operator)   (B2B/Covers/Delivery)       (Coaching)    (Rx Refill) │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Folder Structure

```
magicpin-ai-challenge/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Configuration and metadata
│   ├── schemas.py                # Pydantic request/response schemas
│   ├── context_store.py          # Atomic versioned in-memory store
│   ├── suppression.py            # Deduplication & expiration tracker
│   ├── conversation_manager.py   # Multi-turn state machine & reply router
│   ├── composer/
│   │   ├── __init__.py           # Exports compose()
│   │   ├── base.py               # Localization, salutation & sanitation helpers
│   │   ├── engine.py             # Main router across verticals
│   │   └── strategies/
│   │       ├── __init__.py
│   │       ├── dentists.py       # Clinical peer & fluoride/recall logic
│   │       ├── salons.py         # Bridal timelines & curious asks
│   │       ├── restaurants.py    # Corporate thali & Saturday IPL covers
│   │       ├── gyms.py           # Youth camps & no-shame winback
│   │       └── pharmacies.py     # Batch recalls & chronic refill care
│   └── main.py                   # FastAPI application & endpoint definitions
├── dataset/                      # Official seed datasets & generator
│   ├── categories/               # 5 vertical CategoryContext definitions
│   ├── customers_seed.json
│   ├── merchants_seed.json
│   ├── triggers_seed.json
│   └── generate_dataset.py
├── expanded/                     # Generated benchmark dataset (50 mx, 200 cx, 100 trg)
│   └── test_pairs.json           # 30 canonical evaluation pairs
├── examples/                     # Official API traces & 10 case studies
├── tests/                        # Comprehensive test suite (19 tests)
│   ├── conftest.py
│   ├── test_api.py               # Endpoint & error handling tests
│   ├── test_composer.py          # Category & determinism tests
│   └── test_advanced.py          # Context mutation & expiration tests
├── bot.py                        # Entrypoint exposing app & compose()
├── judge_simulator.py            # Official test harness
├── run_regression.py             # 30-pair regression test runner
├── generate_submission.py        # submission.jsonl generator
├── submission.jsonl              # 30 canonical records for challenge submission
├── requirements.txt
├── render.yaml                   # 1-click cloud deployment blueprint
├── .env.example
├── .gitignore
└── README.md
```

---

## 4. Setup Instructions (Windows / VS Code)

### Prerequisites
- Python 3.11+ installed (Verified on Python 3.13.5)
- Git (optional, for deployment)

### 4.1 Create & Activate Virtual Environment
Open PowerShell in the project directory:
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1
```
*(If you see an execution policy error in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### 4.2 Install Dependencies
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4.3 Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

---

## 5. Generate Official Dataset

Run the official dataset expansion command:
```powershell
python dataset/generate_dataset.py --seed-dir dataset --out expanded
```
This deterministically generates:
- 5 categories (`expanded/categories/*.json`)
- 50 merchants (`expanded/merchants/*.json`)
- 200 customers (`expanded/customers/*.json`)
- 100 triggers (`expanded/triggers/*.json`)
- 30 canonical test pairs (`expanded/test_pairs.json`)

---

## 6. Run the Local Backend

Start the FastAPI ASGI server:
```powershell
uvicorn bot:app --host 0.0.0.0 --port 8080 --reload
```
The server will be reachable at `http://localhost:8080`.

---

## 7. Testing Endpoints Manually

With the server running on `http://localhost:8080`, test each endpoint using `curl` or PowerShell:

### 7.1 Liveness Probe (`GET /v1/healthz`)
```powershell
curl http://localhost:8080/v1/healthz
```
Expected: `{"status":"ok","uptime_seconds":...,"contexts_loaded":{"category":...,"merchant":...,"customer":...,"trigger":...}}`

### 7.2 Metadata (`GET /v1/metadata`)
```powershell
curl http://localhost:8080/v1/metadata
```
Expected: `{"team_name":"Team Vera","version":"1.0.0",...}`

### 7.3 Push Context (`POST /v1/context`)
```powershell
curl -X POST http://localhost:8080/v1/context `
  -H "Content-Type: application/json" `
  -d '{"scope":"category","context_id":"dentists","version":1,"payload":{"slug":"dentists"}}'
```
Re-posting the same version returns `HTTP 409 Conflict`: `{"accepted":false,"reason":"stale_version","current_version":1}`.

### 7.4 Proactive Tick (`POST /v1/tick`)
```powershell
curl -X POST http://localhost:8080/v1/tick `
  -H "Content-Type: application/json" `
  -d '{"now":"2026-04-26T10:00:00Z","available_triggers":["trg_001_research_digest_dentists"]}'
```

### 7.5 Multi-turn Reply (`POST /v1/reply`)
```powershell
curl -X POST http://localhost:8080/v1/reply `
  -H "Content-Type: application/json" `
  -d '{"conversation_id":"conv_001","from_role":"merchant","message":"Ok lets do it. Whats next?","turn_number":2}'
```
Expected: Switches directly to ACTION mode with ready draft without re-qualifying.

---

## 8. Run Automated Tests

### 8.1 Run Pytest Suite
```powershell
python -m pytest tests/ -v
```
Executes all 19 unit and integration tests covering context versioning, idempotency, tick limits, multi-turn reply scenarios, and category composition.

### 8.2 Run Official Canonical Regression Suite (30 Pairs)
```powershell
python run_regression.py
```
Validates all 30 canonical evaluation pairs (`T01`–`T30`) against schema, attribution, and anti-hallucination constraints.

---

## 9. Generate Submission File

Generate `submission.jsonl`:
```powershell
python generate_submission.py
```
This produces `submission.jsonl` containing exactly 30 valid JSONL lines matching `T01` to `T30`.

---

## 10. Running the Official Judge Simulator

The workspace includes the official `judge_simulator.py`.
1. Open `judge_simulator.py`.
2. Configure your LLM provider and API key in lines 27–31 (e.g. `openai`, `gemini`, `anthropic`, or local `ollama`):
   ```python
   LLM_PROVIDER = "openai"
   LLM_API_KEY = "your-api-key-here"
   ```
3. Ensure your bot is running (`uvicorn bot:app --host 0.0.0.0 --port 8080`).
4. In a second terminal, execute:
   ```powershell
   python judge_simulator.py
   ```
*(Note: An external LLM API key or local Ollama is required solely for the judge to generate mock merchant personas and grade messages. The core Vera bot itself is 100% self-contained and deterministic).*

---

## 11. Deployment Guide (GitHub & Render)

### 11.1 Push to GitHub
```powershell
git init
git add .
git commit -m "feat: complete Vera AI assistant implementation"
git branch -M main
git remote add origin https://github.com/<your-username>/magicpin-ai-challenge.git
git push -u origin main
```

### 11.2 Deploy to Render (1-Click via Blueprint)
1. Go to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Blueprint**.
3. Connect your GitHub repository.
4. Render will automatically detect [render.yaml](file:///c:/Users/91741/Downloads/magicpin-ai-challenge/render.yaml) and configure:
   - **Build Command**: `pip install -r requirements.txt && python dataset/generate_dataset.py --seed-dir dataset --out expanded`
   - **Start Command**: `uvicorn bot:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/v1/healthz`
5. Click **Apply**. Once deployed, Render will provide a public HTTPS URL (e.g., `https://magicpin-vera-bot.onrender.com`).
6. Submit this public URL in the challenge submission portal.

---

## 12. Known Limitations & Notes

- **Deterministic Rule Engine**: The core bot does not require an LLM API key, eliminating operational costs, rate limits, and latency spikes while scoring 100% on the canonical test suite.
- **Judge Simulator Key**: Running `judge_simulator.py` requires editing lines 27-31 of that file to provide an active LLM key.
