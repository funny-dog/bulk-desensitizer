from __future__ import annotations

import csv
import json
from pathlib import Path

import redis
from celery import Task
from openpyxl import load_workbook

from celery_app import celery_app
from config import settings
from database import SessionLocal, init_db
from models import DataRecord

# Initialize Redis client for Pub/Sub
redis_client = redis.from_url(settings.celery_broker_url)


def _iter_csv_rows(path: Path):
    with path.open("r", newline="") as handle:
        reader = csv.reader(handle)
        yield from reader


def _iter_xlsx_rows(path: Path):
    workbook = load_workbook(filename=path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        for row in sheet.iter_rows(values_only=True):
            yield row
    finally:
        workbook.close()


def _count_rows(path: Path, file_type: str) -> int:
    if file_type == "csv":
        return sum(1 for _ in _iter_csv_rows(path))
    if file_type == "xlsx":
        return sum(1 for _ in _iter_xlsx_rows(path))
    raise ValueError(f"unsupported file type: {file_type}")


def _iter_rows(path: Path, file_type: str):
    if file_type == "csv":
        return _iter_csv_rows(path)
    if file_type == "xlsx":
        return _iter_xlsx_rows(path)
    raise ValueError(f"unsupported file type: {file_type}")


def _row_payload(row) -> str:
    return ",".join("" if cell is None else str(cell) for cell in row)


@celery_app.task(bind=True)
def process_csv(self: Task, file_path: str) -> dict:
    init_db()
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError(f"unsupported file type: {suffix}")
    file_type = "xlsx" if suffix == ".xlsx" else "csv"

    total = _count_rows(path, file_type)

    if total == 0:
        return {"current": 0, "total": 0, "message": "no rows"}

    session = SessionLocal()
    try:
        for index, row in enumerate(_iter_rows(path, file_type), start=1):
            record = DataRecord(
                task_id=self.request.id,
                row_number=index,
                payload=_row_payload(row),
            )
            session.add(record)

            if index % 100 == 0:
                session.commit()

            if index == total or index % 10 == 0:
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": index,
                        "total": total,
                        "message": f"Processing row {index}/{total}",
                    },
                )
                # Publish progress to Redis
                redis_client.publish(
                    f"task_progress:{self.request.id}",
                    json.dumps(
                        {
                            "current": index,
                            "total": total,
                            "message": f"Processing row {index}/{total}",
                        }
                    ),
                )

        session.commit()
    finally:
        session.close()

    # Publish completion message
    redis_client.publish(
        f"task_progress:{self.request.id}",
        json.dumps({"current": total, "total": total, "message": "completed"}),
    )

    return {"current": total, "total": total, "message": "completed"}
