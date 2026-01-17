# Bulk Data Processor POC

A full-stack demo showcasing a high-performance async architecture for bulk CSV/XLSX processing.

## Tech Stack
- Backend: Python 3.11, FastAPI, Celery, Redis, SQLAlchemy (PostgreSQL)
- Frontend: Vue 3 (Vite)
- Infrastructure: Docker & Docker Compose

## Quick Start
```bash
docker compose up --build
```

Then open:
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

## How It Works
1. Upload a CSV or XLSX via `POST /upload`
2. FastAPI saves the file and triggers a Celery task (non-blocking)
3. Celery parses rows, stores dummy records to Postgres, and reports progress
4. Frontend polls `GET /status/{task_id}` every 2 seconds and updates the progress bar

## API
- `POST /upload` (multipart form-data, field: `file`)
- `GET /status/{task_id}`

## Sample Data
A sample Excel file is provided at `sample_data.xlsx`.
The backend supports both CSV and XLSX, so the Excel file can be uploaded directly.

## Services (docker-compose)
- `db`: PostgreSQL 15
- `redis`: Redis 7
- `backend`: FastAPI app
- `worker`: Celery worker
- `frontend`: Vite dev server

## Local Development (optional)
Backend:
```bash
cd backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

Worker:
```bash
cd backend
uv run celery -A worker.celery_app worker --loglevel=info
```

Frontend:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```
