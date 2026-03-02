# MedRisk AI 🩺✨
### *AI-Powered Preventive Healthcare from PDF → JSON → Prediction*

MedRisk AI is a full-stack, AI-powered preventive healthcare platform built to **analyze, understand, and act** on complex blood test reports.

This project was created for a **Data Science Practical Exam**, demonstrating a complete end-to-end **Hybrid AI Pipeline** — from unstructured PDF ingestion to a custom-trained ML model, all inside a modern web application.

---

## 🚀 Core Features

### 🔐 Secure User Authentication
- Full user sign-up & login using **Firebase Authentication**.

### 📁 Persistent Report History
- All uploaded reports & predictions saved to **Cloud Firestore**, mapped to each user.

### 🧠 “General Purpose” AI PDF Reader
- Utilizes **Google Gemini 2.5 Flash** to parse any lab report PDF.
- Extracts biomarkers into standardized JSON.

### 🧬 Custom-Trained ML Model
- A **scikit-learn Decision Tree** (`disease_model.pkl`) predicts possible health risks:
  - Anemia  
  - Hypothyroidism  
  - Autoimmune Disorder  

### 📊 Simple, Actionable Results
- Human-readable, clean dashboard summaries.

### 🗺️ Find Local Care
- Hardcoded list of specialists + an embedded Google Map centered on **Gwalior, MP**.

### 📉 Data Science Dashboard
- A separate **Streamlit** app (`visualize_model.py`) showing:
  - Decision tree  
  - Feature importances  
  - Sample predictions  

---

## 🤖 The Hybrid AI Pipeline — How It Works

MedRisk AI uses a **two-model Hybrid AI approach**:

---

### **Phase 1: AI Reader (Gemini 2.5 Flash)**  
1. User uploads a PDF.  
2. Text extracted via PyMuPDF.  
3. Sent to Gemini AI for interpretation.  
4. Returns structured JSON like:

```json
{
  "Hemoglobin": 10.2,
  "TSH": 5.6,
  "MPV": 10.7
}
Phase 2: AI Predictor (Scikit-learn)
JSON biomarkers are fed into a DecisionTreeClassifier.

Outputs a single health risk label.

Phase 3: Final Output
Displayed on a clean, plain-English frontend dashboard.

💻 Technology Stack
Category	Technology
Frontend	React, TypeScript, Vite, Tailwind CSS, Shadcn/UI
Backend	FastAPI, Python 3.11+, Uvicorn
Database & Auth	Firebase Authentication, Cloud Firestore
AI Reader (Model 1)	Google Gemini 2.5 Flash
AI Predictor (Model 2)	Scikit-learn DecisionTreeClassifier
Data Science Tools	Pandas, Joblib, Matplotlib
DS Dashboard	Streamlit
PDF Parsing	PyMuPDF (fitz)

🛠️ Setup & Installation
This monorepo contains:

medrisk-backend/ — FastAPI backend + ML

medrisk-frontend/ — React UI

Run both simultaneously.

1. Backend Setup (FastAPI + AI)
bash
Copy code
cd medrisk-backend
pip install -r requirements.txt
Get Your Google AI Studio API Key
Create a key at:
https://aistudio.google.com/app/apikey

Then open main.py → insert your key:

python
Copy code
apiKey = "PASTE_YOUR_AI_STUDIO_KEY_HERE"
Train the Model
bash
Copy code
python train_model.py
Run Backend
bash
Copy code
python main.py
Backend runs at:

cpp
Copy code
http://127.0.0.1:8000
2. Frontend Setup (React + Firebase)
bash
Copy code
cd medrisk-frontend
npm install
Firebase Setup
Create a Firebase project.

Enable Email/Password auth.

Create Firestore (production mode).

Add rules:

bash
Copy code
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /artifacts/{appId}/users/{userId}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
Get firebaseConfig from Project Settings → Web App.

Paste into src/firebase.ts:

ts
Copy code
export const MANUAL_FIREBASE_CONFIG = {
  apiKey: "...",
  authDomain: "...",
  projectId: "...",
  storageBucket: "...",
  messagingSenderId: "...",
  appId: "..."
};
Run Frontend
bash
Copy code
npm run dev
Frontend runs at:

arduino
Copy code
http://localhost:5173