# EvalForge: Technical Dossier & Architectural Deep-Dive

---

## 1. Executive Summary & The Problem Space

### The Core Problem
In traditional software development, testing is deterministic: given input $X$, the output is always $Y$. In GenAI engineering, testing is probabilistic and natural-language-based. Prompts are highly sensitive; modifying a single word in a system instruction can trigger silent quality regressions, formatting failures, or hallucinations. 

Most product teams shipping LLM features deal with three primary headaches:
1. **Lack of Regression Detection:** A developer updates a prompt in staging. There is no automated test pipeline to prove whether output quality improved or degraded.
2. **Leniency Bias:** When teams try to automate evaluations by asking an LLM to grade output, the judge defaults to high scores (e.g., 9/10 or 10/10) regardless of actual quality.
3. **Vendor Lock-in and Costs:** Commercial observability solutions (like LangSmith or Braintrust) can cost hundreds of dollars monthly and require sending proprietary data to external servers.

### The EvalForge Solution
EvalForge is an open-source, self-hostable LLM evaluation and observability platform. It allows developers to:
* Define structured test suites containing target inputs and reference expected outputs.
* Run evaluations against multiple target models (Llama 3.3, DeepSeek, Qwen) using free APIs (Groq, OpenRouter).
* Rate the outputs along 7 independent quality dimensions using a calibrated, separate judge model (Gemini 2.5 Flash).
* Run side-by-side comparisons of prompt/model versions and automatically trigger regression flags if scores drop.

---

## 2. Machine Learning Paradigm: Why Evals Differ from Traditional ML

### Why Traditional ML Algorithms (Random Forest, XGBoost) Are Incompatible
A common misconception is that evaluating language models involves classic supervised classification or regression algorithms. In traditional ML:
* We train models like Random Forest, Gradient Boosting, or SVMs to predict discrete classes or numeric targets based on structured tabular features.
* We assess performance using metrics like **Accuracy**, **Precision/Recall (F1-score)**, and **AUC-ROC (Area Under the Receiver Operating Characteristic)** curves.

However, natural language outputs are free-form, variable-length, and context-dependent. Traditional classifiers cannot measure if a paragraph is "too verbose," "sarcastic," "hallucinatory," or "correct in meaning but structured differently." Training a custom classifier for every prompt criteria would require thousands of labeled examples, which is slow, expensive, and inflexible.

### How EvalForge Scores Natural Language Generation (NLG)
Instead of training tabular models, EvalForge uses a hybrid evaluation architecture combining:
1. **Deterministic NLP Sequence Overlap (ROUGE-L):** Longest Common Subsequence matching between generated output and reference answer.
2. **Vector Space Semantic Embeddings:** Measures cosine distance between text representations (vector alignment).
3. **Generative LLM-as-a-Judge:** Uses a high-reasoning model (Gemini) configured with strict evaluation rubrics to grade subjective dimensions.

### ROUGE-L & Semantic Similarity vs. Classifier Metrics
Instead of AUC-ROC (which measures classification thresholds) or raw Accuracy, we evaluate text quality using continuous metrics:
* **ROUGE-L (Recall-Oriented Understudy for Gisting Evaluation):** Counts the longest matching sequence of words. This detects if the model output preserves the exact sentence structure of the reference.
* **Semantic Cosine Similarity:** Embeds text into high-dimensional vector space. If a model says "A list can change, but a tuple cannot," and the reference is "A list is mutable while a tuple is immutable," ROUGE-L will be low (low word overlap), but semantic similarity will be high (meaning is preserved).

---

## 3. The 4-Layer Scorer Stack

EvalForge processes every generated output through a cascading scoring pipeline:

```
                  ┌─────────────────────────────────┐
                  │      Generated Model Output     │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │ 1. Deterministic Exact Match    │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │ 2. Deterministic ROUGE-L        │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │ 3. Semantic Cosine Similarity   │
                  │    (sentence-transformers)      │
                  └────────────────┬────────────────┘
                                   │ (Fallback if local download fails)
                                   ▼
                  ┌─────────────────────────────────┐
                  │ 4. difflib SequenceMatcher      │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │ 5. Calibrated LLM-as-a-Judge    │
                  │    (Gemini 2.5 Flash Scorer)    │
                  └─────────────────────────────────┘
```

### Layer 1: Exact Match Scorer
Determines if the actual output exactly matches the expected output (case-sensitive and whitespace-normalized). Returns `1.0` or `0.0`.

### Layer 2: ROUGE-L Scorer
Implements a pure Python longest-common-subsequence matching algorithm. Runs locally with zero external API dependencies. It calculates:
$$\text{ROUGE-L} = \frac{\text{LCS}(\text{Reference}, \text{Generated})}{\text{Length of Reference}}$$
This ensures we capture word order and alignment.

### Layer 3 & 4: Semantic Similarity with Fallback
* **Primary:** Uses a local `sentence-transformers` model (`all-MiniLM-L6-v2`) to generate 384-dimensional embeddings of the text and calculates the cosine similarity.
* **Resiliency Fallback:** Loading a 90MB local model can crash on lightweight local environments or offline development. If `sentence-transformers` fails to import or download, the pipeline instantly degrades gracefully to Python's built-in `difflib.SequenceMatcher`. This guarantees that a missing network connection or GPU driver never crashes an evaluation run.

### Layer 5: Calibrated LLM-as-a-Judge (Gemini)
Gemini 2.5 Flash evaluates five distinct dimensions from `1` to `10`:
1. **Correctness:** Does the output factually align with the expected output?
2. **Relevance:** Does the response address the input prompt without filler?
3. **Coherence:** Is the output structured, logical, and grammatical?
4. **Tone:** Does the tone match the system prompt requirements?
5. **Hallucination Resistance:** Does the output avoid inventing facts not present in the reference context?

---

## 4. Key Engineering Failures & How We Solved Them

During the development of EvalForge, we encountered four critical engineering bottlenecks. Resolving them forms the core technical complexity of this project:

### Failure 1: The Self-Grading Feedback Loop
* **The Mistake:** Initially, the system used a single provider (Gemini) to generate answers and then judge its own answers. 
* **Why it failed:** LLMs suffer from self-preference bias. When Gemini grades its own output, it consistently scores its work higher than it would grade outputs from another model (like Llama).
* **The Fix:** We decoupled generation and evaluation. Groq and OpenRouter handle output generation, while Gemini only handles judgment. The target model never grades itself.

### Failure 2: LLM Leniency Bias (Flat 10/10 Scores)
* **The Mistake:** In early test runs, the judge rated every response as a `10/10` across all dimensions, rendering regression tracking useless.
* **The Fix:** We implemented a three-tier judge calibration pipeline:
  1. **Anchored Rubrics:** The prompt maps numeric scores to strict definitions. For example, a `9` or `10` is reserved for outputs that cannot realistically be improved, while an output with minor structural flaws is locked to a `7` or `8`.
  2. **Chain-of-Thought (CoT) Schema Ordering:** LLMs generate text token-by-token. If the output JSON schema starts with `{"score": 9, "reasoning": "..."}`, the score is committed *before* the reasoning is generated. We flipped the JSON schema to output the `reasoning` block *before* the `scores` block. This forces the model's attention heads to condition the score on its own critical analysis.
  3. **Devil's Advocate Field:** We prepended a compulsory `devil_advocate` field to the JSON output. Before writing any reasoning or scores, the judge must generate the strongest argument that the candidate output is flawed. This primes the model's hidden states toward skepticism.

### Failure 3: Unescaped Quote Parsing Breaks
* **The Mistake:** Gemini is instructed to output JSON, but string values containing quotes (e.g., `"The output says "mutable" but..."`) produce malformed JSON syntax that crashes standard `json.loads()`.
* **The Fix:** We implemented a 3-layer parsing pipeline in `_extract_json()`:
  1. Attempt standard `json.loads()`.
  2. Extract text wrapped in markdown code blocks using regular expressions.
  3. **Greedy Regex Extraction:** If standard parsing fails, a fallback regex extracts key-value pairs by matching field strings up to the closing quote delimiter (`",`, `"\n`, or `"` before a brace), allowing us to recover the scores and reasoning even if quotes inside string values are unescaped.

### Failure 4: Docker DB Permission Failures on Hugging Face
* **The Mistake:** When deploying the container to Hugging Face Spaces, the server crashed on startup with `sqlite3.OperationalError: unable to open database file`.
* **Why it failed:** Hugging Face Spaces requires running containers as a secure, non-root user (UID 1000). While our file permissions were correct, the container directory `/home/user/app` was created by Docker's `WORKDIR` command while running as `root`, meaning the non-root user could not write lock files or temporary databases inside it.
* **The Fix:** We updated the `Dockerfile` to explicitly create the directories and run `chown -R user:1000 $HOME` prior to executing the `COPY` operations, granting full write permissions to the non-root user.

---

## 5. Performance Optimizations: Cache & Concurrency

### SHA-256 Result Caching
To minimize API consumption and cost, the runner implements a database cache. 
* We generate a SHA-256 hash of: `model_id + system_prompt + user_input`.
* If a matching hash is found in the database, the runner retrieves the historical output and skips the API calls to the provider. 
* Any modification to the system prompt or user input invalidates the cache automatically, ensuring evaluation integrity.

### Thread-Safe Rate Limiting
Evaluation runs hit APIs rapidly. To prevent HTTP 429 (Too Many Requests) errors, we implemented provider-level mutex locks. If multiple threads run evaluations, they queue and throttle requests to respect the rate limits of free APIs.

---

## 6. File-by-File Codebase Analysis

The repository is structured modularly to separate concerns:

```
├── backend/
│   ├── evaluation/
│   │   ├── cache.py          # SHA-256 caching logic
│   │   ├── comparator.py     # Comparison logic & regression analysis
│   │   ├── metrics.py        # Local NLP metrics (ROUGE-L)
│   │   └── runner.py         # Threaded runner for evaluations
│   ├── providers/
│   │   ├── base.py           # Provider interface and RateLimiter
│   │   ├── gemini_provider.py# Judge prompting & parser logic
│   │   ├── groq_provider.py  # Groq API client
│   │   └── openrouter.py     # OpenRouter API client
│   ├── database.py           # SQLAlchemy setup
│   ├── models.py             # Database schema models
│   ├── schemas.py            # Pydantic serialization schemas
│   └── main.py               # FastAPI router entrypoint
├── frontend/
│   ├── css/
│   │   └── styles.css        # Dashboard styling (Glassmorphism layout)
│   ├── js/
│   │   └── app.js            # Frontend routing, state, and Chart.js integration
│   └── index.html            # Main SPA dashboard
├── Dockerfile                # Hugging Face deployment manifest
└── requirements.txt          # Python dependencies
```

### Backend Files
*   **database.py**: Configures the SQLAlchemy database engine using a thread-safe SQLite connection context.
*   **models.py**: Defines database models. Relates `TestSuite` to `TestCase`, and tracks evaluation metadata in `EvalRun` and `EvalResult`.
*   **schemas.py**: Pydantic schemas for data serialization and API validation.
*   **main.py**: The core entry point. Configures CORS, sets up API endpoints, mounts static frontend assets, and launches background worker threads for evaluation runs.
*   **runner.py**: Orchestrates the background thread pipeline. Checks the SHA-256 cache, triggers target model generations, collects execution latency, routes outputs to the Gemini judge, calculates text metrics, and persists scores.
*   **metrics.py**: Calculates sequence-level overlap statistics (ROUGE-L) locally.
*   **comparator.py**: Performs comparative math between run baselines to detect delta scores and trigger regression alerts.
*   **cache.py**: Generates SHA-256 hashes to lookup and save historical outputs.
*   **base.py**: Abstract base class for providers. Integrates thread-safe rate-limiting locks.
*   **gemini_provider.py**: Houses the calibrated evaluator instructions, the "Devil's Advocate" prompts, and the 3-layer JSON extraction algorithm.
*   **groq_provider.py**: Connects to Groq's SDK, supporting rapid execution of Llama models.
*   **openrouter_provider.py**: Interface for OpenRouter, allowing access to Qwen, DeepSeek, and Mistral free models.

### Frontend Files
*   **index.html**: The container for the SPA. Uses Tailwind CSS classes to render a modern glassmorphic sidebar and layout.
*   **styles.css**: Implements custom design details (scrollbar designs, card layouts, background gradients).
*   **app.js**: Handles single-page state routing, REST API communication, polling for progress bar animations during evaluation runs, and building Chart.js radar charts.
