---
title: EvalForge
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# ⚡ EvalForge — LLM Evaluation & Observability Platform

A full-stack, self-contained developer platform designed to systematically measure whether LLM outputs are getting better or worse. Built to solve the #1 production AI problem: **detecting quality regressions and prompt drift before shipping to users.**


---

## 🚀 Architecture & Technical Stack

EvalForge is designed as a single, unified web application. The backend serves the static frontend assets directly, removing the need for a separate node dev server.

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Browser)                      │
│   Dashboard │ Test Suites │ Run Evaluation │ Results │ Compare │
└─────────────────────┬───────────────────────────────────────┘
                      │ REST API
┌─────────────────────▼───────────────────────────────────────┐
│                   BACKEND (FastAPI)                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Evaluation Runner (Background Threads)                │  │
│  │  ├── Result Cache (SHA-256 Prompt Hashing)             │  │
│  │  ├── Calibrated Judge (Gemini 2.5 Flash)               │  │
│  │  ├── Text Metrics (Pure Python ROUGE-L)                │  │
│  │  └── Similarity Fallback (difflib SequenceMatcher)     │  │
│  └────────────────────────────────────────────────────────┘  │
│                    SQLite Database                          │
└─────────────────────────────────────────────────────────────┘
```

* **Frontend:** Vanilla HTML5, CSS3 (Glassmorphism design, responsive layouts), and Javascript. Visualizations powered by Chart.js (Radar and Bar charts).
* **Backend:** FastAPI (Async API endpoints) + SQLAlchemy ORM.
* **Database:** SQLite (Stored locally as `evalforge.db`).
* **Providers & Models:**
  * **Groq SDK:** Llama 3.3 70B and Llama 3.1 8B (fast LPU-based evaluation).
  * **OpenRouter API:** Dynamic Auto-Free Router (automatically routes to active free models like Qwen or DeepSeek).
  * **Google AI Studio (Gemini SDK):** Gemini 2.5 Flash used exclusively as the **LLM Judge**.

---

## 🌟 Key Engineering Highlights

### 1. Calibrated LLM-as-a-Judge Prompting
To eliminate "leniency bias" (where LLM judges score all adequate outputs as 9/10), the evaluation prompt enforces a three-part skeptical alignment:
* **Devil's Advocate:** The model must state the strongest argument against the actual output before scoring.
* **Reasoning-Before-Score JSON:** The JSON response forces the reasoning text block to be outputted *before* the numerical scores, utilizing the model's auto-regressive attention mechanism as a Chain-of-Thought (CoT) buffer.
* **Anchored Rubrics:** Strict rubrics mapping numerical ranges (1-3, 4-5, 6-7, 8, 9-10) to concrete quality benchmarks.

### 2. Double-Quote Resilient Parser
If the LLM judge outputs unescaped double quotes inside reasoning text fields (which crashes standard `json.loads`), the backend falls back to a custom greedy regular expression parsing engine to extract the dimensions and text values cleanly.

### 3. Background Processing & Caching
Evaluations run on separate background threads to prevent HTTP timeouts. Runs are tracked using a result cache keyed by `sha256(model_id + system_prompt + input_prompt)` to avoid duplicate model inference costs.

---

## 🛠️ Getting Started

### Prerequisites
* Python 3.12+

### 1. Installation
Install the required packages:
```bash
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file in the root directory (using `.env.example` as a template):
```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 3. Start the Server
Run the single combined backend service:
```bash
python -m backend.main
```
The application will immediately be active at **[http://localhost:8000](http://localhost:8000)**.

---

## 📂 Project Structure

```
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md              # You are here
├── backend/
│   ├── main.py            - FastAPI server, routing, static mounting
│   ├── database.py        - SQLite & engine initialization
│   ├── models.py          - SQLAlchemy DB tables
│   ├── schemas.py         - Pydantic request/response validation
│   ├── providers/
│   │   ├── base.py        - Abstract model provider & rate limiter
│   │   ├── groq_provider.py - Groq client integration
│   │   ├── openrouter_provider.py - OpenRouter integration
│   │   └── gemini_provider.py - Calibrated Gemini LLM Judge
│   └── evaluation/
│       ├── runner.py      - Async runner, caching, error handlers
│       ├── comparator.py  - Run comparison, regression alerts
│       ├── cache.py       - SHA-256 cache helpers
│       ├── metrics.py     - ROUGE-L algorithm implementation
│       └── similarity.py  - Text similarity fallback handler
└── frontend/
    ├── index.html         - SPA DOM shell
    ├── css/
    │   └── styles.css     - UI design tokens, animations
    └── js/
        └── app.js         - Frontend controller, state routing
```
