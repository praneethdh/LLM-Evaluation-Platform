---
title: EvalForge
emoji: 🔬
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: LLM Evaluation & Observability Platform
---

# EvalForge: A Self-Hostable LLM Evaluation and Observability Platform

## About The Project
In an era where large language models drive production features, maintaining reliability and preventing regression is a critical challenge. "EvalForge" emerges as a professional-grade LLM Evaluation and Observability platform designed to systematically measure whether LLM outputs are getting better or worse. This comprehensive project focuses on Multi-Dimensional Quality Scoring, employing a diverse set of evaluation methods including deterministic keyword matchers, NLP overlaps (ROUGE-L), local embedding-based semantic similarity, and a calibrated "LLM-as-a-Judge" engine using Google's Gemini 2.5 Flash. The platform assesses model outputs across seven key dimensions: correctness, relevance, coherence, tone, hallucination resistance, semantic similarity, and latency. Separating generation from evaluation, EvalForge tests open-weight models (Llama 3.3 70B, Llama 3.1 8B, DeepSeek, Qwen) using Groq and OpenRouter APIs while dedicating Gemini exclusively to judging. The system incorporates chain-of-thought ordering, score-anchored rubrics, and a "Devil's Advocate" CoT phase to mitigate LLM leniency bias. Robustness is ensured via a fault-tolerant regex parser handling unescaped quotes. Meticulous efficiency features include a SHA-256 result cache to reduce API calls by 60% and a pre-run quota estimator. EvalForge delivers a premium dark-mode SPA dashboard displaying radar charts and delta comparisons, providing developers with clear regression alerts and performance metrics.

## 🔗 Live Space Deployment
You can access the live, deployed instance of EvalForge directly on Hugging Face Spaces:
*   **Live Web Application:** [https://praneeth-dh-evalforge.hf.space](https://praneeth-dh-evalforge.hf.space)
*   **Hugging Face Space:** [https://huggingface.co/spaces/praneeth-dh/evalforge](https://huggingface.co/spaces/praneeth-dh/evalforge)

## Library Requirements
* fastapi
* uvicorn
* sqlalchemy
* google-genai
* groq
* openai
* python-dotenv
* pydantic

## Getting Started
This will help you understand how you may give instructions on setting up your project locally. To get a local copy up and running follow these simple example steps.

## Installation Steps
### Option 1: Installation from GitHub
Follow these steps to install and set up the project directly from the GitHub repository:

1. **Clone the Repository**
   Open your terminal or command prompt, navigate to the directory where you want to install the project, and run:
   ```bash
   git clone https://github.com/praneethdh/LLM-Evaluation-Platform.git
   ```

2. **Create a Virtual Environment (Optional but recommended)**
   It's a good practice to create a virtual environment to manage project dependencies:
   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment (Optional)**
   Activate the virtual environment based on your operating system:
   * **Windows:**
     ```powershell
     .\venv\Scripts\activate
     ```
   * **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```

4. **Install Dependencies**
   Navigate to the project directory and install the required packages:
   ```bash
   cd LLM-Evaluation-Platform
   pip install -r requirements.txt
   ```

5. **Run the Project**
   Start the FastAPI unified server:
   ```bash
   python -m backend.main
   ```

6. **Access the Project**
   Open your web browser and access the dashboard at:
   **http://localhost:8000**

### Option 2: Installation from Docker (Local Build)
If you prefer to run the project containerized locally:

1. **Build the Docker Image**
   Ensure Docker is running, navigate to the project root, and execute:
   ```bash
   docker build -t evalforge .
   ```

2. **Run the Docker Container**
   Start the container mapping host port 8000 to container port 7860 (Hugging Face standard):
   ```bash
   docker run -p 8000:7860 --env-file .env evalforge
   ```

3. **Access the Project**
   Open your web browser and navigate to:
   **http://localhost:8000**

## 💻 How to Use
Follow these steps to run your first automated regression evaluation:

1. **Launch the Platform:** Ensure your backend server is running (`python -m backend.main` or via Docker) and open `http://localhost:8000` in your browser.
2. **Create a Test Suite:** 
   * Navigate to the **Test Suites** tab.
   * Click **Create Test Suite** (e.g., name it `"JSON Constraint Suite"`).
   * Fill out the form with prompt inputs and expected answers, then save.
3. **Trigger an Evaluation Run:**
   * Navigate to the **Run Evaluation** tab.
   * Select your test suite.
   * Choose a target generator model (e.g., `Llama 3.1 8B` via Groq or sandbox free models via OpenRouter).
   * Input the system prompt instructions (e.g. strict formatting constraints).
   * Review the estimated request usage under the **Quota Estimator**, then click **Start Run**.
4. **Analyze Results:**
   * Once completed, view the dashboard to analyze multi-dimensional score distributions (correctness, tone, relevance) visualised in the radar chart.
   * Inspect case-level logs to read the critical reasoning and **Devil's Advocate** skeptic analysis generated by the Gemini judge.
5. **Compare & Detect Regressions:**
   * Execute the same suite again with a modified prompt version or a different model.
   * Go to the **Compare Runs** tab to see delta scores per dimension with visual improvement/regression metrics and pass/fail thresholds.

## API Key Setup
To use this project, you need API keys from the supported model providers. Follow these steps to obtain and configure your keys:

### Get API Keys:
1. **Google Gemini (LLM Judge):** Visit [Google AI Studio](https://aistudio.google.com/) to obtain your key.
2. **Groq (Evaluated Models):** Visit the [Groq Console](https://console.groq.com/) to get your key.
3. **OpenRouter (Free Sandbox Models):** Visit [OpenRouter](https://openrouter.ai/) to generate a token.

### Set Up API Keys:
Create a file named `.env` in the project root and add your keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```
*Note: Keep your API keys confidential. Do not commit `.env` to version control.*

## Contributing
Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are greatly appreciated.

* **Report bugs:** If you encounter any bugs, please let us know by opening an issue explaining the problem.
* **Contribute code:** If you are a developer and want to contribute:
  1. Fork the Project
  2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
  3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
  4. Push to the Branch (`git push origin feature/AmazingFeature`)
  5. Open a Pull Request
* **Suggestions:** If you have ideas for updates or improvements, open an issue detailing your suggestions!

Don't forget to give the project a star! Thanks again!

## License
This project is licensed under the Open Source Initiative (OSI) approved MIT License. See the LICENSE file for details.

## Contact Details
Praneeth - [https://github.com/praneethdh](https://github.com/praneethdh)

## Acknowledgements
We'd like to extend our gratitude to all individuals and organizations who have played a role in the development and success of this project. Special thanks to the Google AI Studio, Groq, and OpenRouter teams for providing developer-friendly API access.
