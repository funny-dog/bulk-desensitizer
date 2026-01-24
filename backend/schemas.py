from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    state: str
    current: int | None = None
    total: int | None = None
    message: str | None = None
    output_file: str | None = None


class TaskCancelResponse(BaseModel):
    task_id: str
    message: str
