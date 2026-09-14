# ⚡ AeroCast-Now AI Pro: How to Start All Services

This guide provides complete, step-by-step instructions to launch the entire **AeroCast-Now AI Pro** system, including the **FastAPI REST backend**, the **React 19 + 3D WebGL frontend**, and the optional **Streamlit Meteorological Pro Dashboard**.

---

## 🧭 Architecture & Port Mapping

| Service | Port | Local URL | Description |
| :--- | :--- | :--- | :--- |
| **FastAPI REST Backend** | `8000` | [http://localhost:8000](http://localhost:8000) | Core AI/ML nowcasting engine, ResAtt-ConvLSTM2D model, 2σ lightning jump detector, SCIT tracker, live Blitzortung feed, district nowcasts. |
| **Swagger / OpenAPI Docs** | `8000` | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API exploration and live testing UI. |
| **React 3D Web Frontend** | `5173` | [http://localhost:5173](http://localhost:5173) | Primary user interface: 3D WebGL Lightning Globe, DWR Radar & INSAT Satellite Viewport, Command Screen, District Search, Alert Feeds. |
| **Streamlit Dashboard** *(Optional)* | `8501` | [http://localhost:8501](http://localhost:8501) | Scientific meteorological workstation for in-depth sounding and dBZ slice analysis. |

---

## 🚀 Option 1: One-Click Startup (Recommended)

Scripts are provided in the project root to start and stop all components cleanly.

### Start Backend + Frontend:
```bash
./start_all.sh
```

### Start Backend + Frontend + Streamlit Dashboard:
```bash
./start_all.sh --streamlit
```

### Stop All Services:
```bash
./stop_all.sh
```

> **Note:** Logs will be written to `backend.log`, `frontend.log`, and `streamlit.log` in the project root.

---

## 🛠️ Option 2: Step-by-Step Manual Startup (Individual Terminals)

If you prefer running services in separate terminal windows for live logging and debugging:

### Terminal 1: FastAPI REST API Backend
```bash
# 1. Navigate to project root
cd /home/arun-roshan-gj/SIH

# 2. Activate Python virtual environment
source venv/bin/activate

# 3. Enter backend directory and start Uvicorn
cd backend
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```
* Once running, confirm at [http://localhost:8000/api/health](http://localhost:8000/api/health) or explore endpoints at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### Terminal 2: React 3D Web Frontend
```bash
# 1. Navigate to frontend directory
cd /home/arun-roshan-gj/SIH/frontend

# 2. Install dependencies (only required on first run)
npm install

# 3. Launch Vite development server
npm run dev
```
* Access the main web interface at [http://localhost:5173](http://localhost:5173).
* The Vite server automatically proxies `/api/*` calls to the FastAPI backend running on port 8000.

---

### Terminal 3 (Optional): Streamlit Pro Dashboard
```bash
# 1. Navigate to project root
cd /home/arun-roshan-gj/SIH

# 2. Activate Python virtual environment
source venv/bin/activate

# 3. Enter backend directory and launch Streamlit
cd backend
streamlit run app.py
```
* Access the meteorological workbench at [http://localhost:8501](http://localhost:8501).

---

## 🏃 Running in Background (Daemon Mode)

If you are running in a headless server or remote SSH session and want the processes to persist:

```bash
cd /home/arun-roshan-gj/SIH

# Start backend in background
source venv/bin/activate
nohup python -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

# Start frontend in background
cd frontend
nohup npm run dev -- --host 0.0.0.0 --port 5173 > frontend.log 2>&1 &
```

To stop them:
```bash
./stop_all.sh
```

---

## 🐳 Option 3: Docker Deployment

To run the backend inside a containerized environment:

```bash
cd /home/arun-roshan-gj/SIH/backend
docker build -t aerocast-backend:latest .
docker run -d -p 8000:8000 --name aerocast-api aerocast-backend:latest
```

---

## 🧪 Verification & Health Checks

Verify your setup with these quick commands:

### 1. Check API Health
```bash
curl -s http://localhost:8000/api/health | jq
```
Expected output:
```json
{
  "status": "operational",
  "model_loaded": true,
  "model_params": 191524,
  "api_version": "2.0.0",
  "services": {
    "nowcasting_engine": "online",
    "observation_service": "online",
    "convlstm_model": "loaded"
  }
}
```

### 2. Check Live Convective Radar Grid
```bash
curl -s "http://localhost:8000/api/radar-grid?station=DELHI" | jq '.station, .grid_size'
```

### 3. Check Frontend Proxy
```bash
curl -I http://localhost:5173/api/health
```
Should return `HTTP/1.1 200 OK`.

### 4. Run Automated Test Suite
```bash
source venv/bin/activate
cd backend
python -m unittest test_nowcasting.py test_pipeline.py
```

---

## ❓ Troubleshooting

### Port Already in Use (Port 8000 or 5173)
If you see `[Errno 98] Address already in use`, run:
```bash
./stop_all.sh
```
Or kill processes occupying those ports manually:
```bash
fuser -k 8000/tcp
fuser -k 5173/tcp
```

### Missing CUDA Drivers / GPU
- **Normal & Expected**: The system automatically detects if NVIDIA CUDA is unavailable and falls back to optimized CPU vector operations (AVX2/FMA). The ConvLSTM2D inference runs smoothly on CPU for standard 32x32 nowcast fields.

### District Nowcast Lookup Fails
- Ensure the gazetteer database at `backend/data/` or offline cache is readable.
- You can query any district via `GET /api/v1/districts/search?q=Bengaluru`.
