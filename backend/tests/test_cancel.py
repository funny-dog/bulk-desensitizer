from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_cancel_task():
    task_id = "test-task-id"

    # 我们需要在 main.py 中引入 celery_app 才能 patch 它
    # 或者直接 patch celery.app.control.Control.revoke ?
    # 最稳妥的是 patch main.py 中使用的对象。
    # 假设我们在 main.py 中会调用 celery_app.control.revoke

    with patch("main.celery_app.control.revoke") as mock_revoke:
        response = client.post(f"/tasks/{task_id}/cancel")

        assert response.status_code == 200
        assert response.json() == {
            "message": "task cancel signal sent",
            "task_id": task_id,
        }

        mock_revoke.assert_called_once_with(task_id, terminate=True)
