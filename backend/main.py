from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import redis.asyncio as redis
from celery.result import AsyncResult
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import get_session, init_db
from models import DataRecord
from schemas import TaskStatusResponse, UploadResponse, TaskCancelResponse
from worker import process_csv
from celery_app import celery_app

app = FastAPI(title="Bulk Data Processor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="only .csv or .xlsx is supported")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid4().hex}_{file.filename}"

    with destination.open("wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            buffer.write(chunk)

    task = process_csv.delay(str(destination))
    return UploadResponse(task_id=task.id)


@app.get("/status/{task_id}", response_model=TaskStatusResponse)
async def status(task_id: str) -> TaskStatusResponse:
    result = AsyncResult(task_id, app=celery_app)
    state = result.state

    if state == "PENDING":
        return TaskStatusResponse(task_id=task_id, state=state, message="queued")

    if state == "PROGRESS":
        meta = result.info or {}
        return TaskStatusResponse(
            task_id=task_id,
            state=state,
            current=meta.get("current"),
            total=meta.get("total"),
            message=meta.get("message"),
        )

    if state == "SUCCESS":
        meta = result.result or {}
        return TaskStatusResponse(
            task_id=task_id,
            state=state,
            current=meta.get("current"),
            total=meta.get("total"),
            message=meta.get("message"),
        )

    if state == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id,
            state=state,
            message=str(result.result),
        )

    meta = result.info or {}
    return TaskStatusResponse(
        task_id=task_id,
        state=state,
        current=meta.get("current"),
        total=meta.get("total"),
        message=meta.get("message"),
    )


@app.post("/tasks/{task_id}/cancel", response_model=TaskCancelResponse)
def cancel_task(task_id: str) -> TaskCancelResponse:
    """Send a revoke signal to the celery task."""
    celery_app.control.revoke(task_id, terminate=True)
    return TaskCancelResponse(task_id=task_id, message="task cancel signal sent")


@app.websocket("/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    await websocket.accept()
    # Create a new Redis connection for subscription
    r = redis.from_url(settings.celery_broker_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"task_progress:{task_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                # Redis message data is bytes, decode it
                data = message["data"].decode("utf-8")
                await websocket.send_text(data)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe()
        await r.close()


@app.get("/export")
def export_data(task_id: str | None = None, db: Session = Depends(get_session)):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    def iter_csv(data_records):
        output = io.StringIO()
        writer = csv.writer(output)
        # Write header
        writer.writerow(["id", "task_id", "row_number", "payload"])
        output.seek(0)
        yield output.read()
        output.truncate(0)
        output.seek(0)

        for record in data_records:
            writer.writerow(
                [record.id, record.task_id, record.row_number, record.payload]
            )
            output.seek(0)
            yield output.read()
            output.truncate(0)
            output.seek(0)

    query = db.query(DataRecord)
    if task_id:
        query = query.filter(DataRecord.task_id == task_id)

    records = query.order_by(DataRecord.id).all()

    filename = f"export_{task_id}.csv" if task_id else "export_all.csv"
    response = StreamingResponse(iter_csv(records), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
