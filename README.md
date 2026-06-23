# Supply Chain Disruption Prediction System (India)
React 19 FastAPI Three.js Hugging Face Spaces

An advanced, "next level" multi-model AI system designed to predict and mitigate supply chain disruptions across the Indian logistics network, featuring a high-performance 3D animated frontend.

🔗 Live Application Link
🚀 Hugging Face Spaces Demo: [Launch Full-Stack 3D Application (Click Here)](https://huggingface.co/spaces)
(The application is fully hosted using Docker, bringing together the React 19 frontend and FastAPI backend).

🚀 Architecture
This project has been upgraded from a Streamlit application to a modern Full-Stack AI Application:

* **Frontend:** Built with React 19, Three.js (via React Three Fiber), and GSAP. It provides a sleek, interactive 3D visualization of the supply chain network across 15 major Indian cities.
* **Backend:** A robust FastAPI service that handles model inference, weather data fetching, and risk assessment.
* **AI Models:**
  * **Isolation Forest:** Anomaly detection for weather patterns.
  * **LSTM (Deep Learning):** Captures temporal dependencies in disruption sequences.
  * **XGBoost:** The final classifier for precise risk scoring.

🌟 Key Features
* **3D Interactive Globe/Map:** Stylized 3D visualization of logistics nodes with animated route arcs.
* **GSAP Powered Animations:** Fluid UI transitions and "next level" visual feedback.
* **Real-time Weather Intelligence:** Integrates live 7-day weather forecasts via Open-Meteo API.
* **Explainable AI:** Detailed breakdown of "Risk Causes" for every shipment prediction.
* **Modern UI:** Glassmorphism-inspired design using Tailwind CSS.

🛠️ Getting Started

### Prerequisites
* Python 3.12+
* Node.js 18+
* npm

### 1. Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
python server.py
```
The API will be available at `http://localhost:8000`.

### 2. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```
The application will be available at `http://localhost:5173`.

📂 Project Structure
```
├── frontend/             # React + Three.js + GSAP Frontend
│   ├── src/components/   # 3D Scene and UI Panels
│   ├── src/services/     # API Client
│   └── src/types/        # TypeScript Definitions
├── datasets/             # Historical shipment, news, and supplier data
├── models/               # Saved .pkl and .h5 model files & encoders
├── server.py             # FastAPI Backend
├── app.py                # Legacy Streamlit Interface (Reference)
├── requirements.txt      # Project dependencies
└── README.md             # You are here
```

📈 System Objectives
* **Proactive Visibility:** Move from reactive to predictive logistics.
* **Risk Mitigation:** Identify high-risk shipments before they leave the origin.
* **Optimized Planning:** Adjust buffer stocks and delivery promises based on data-driven confidence scores.

📄 License
Distributed under the MIT License.
