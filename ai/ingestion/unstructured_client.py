import json
import time
from pathlib import Path

import httpx


class UnstructuredClient:
    def __init__(self, api_key: str, base_url: str, poll_seconds: int = 10):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.poll_seconds = poll_seconds

    def url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def headers(self) -> dict[str, str]:
        return {"accept": "application/json", "unstructured-api-key": self.api_key}

    def request_data(self, strategy: str) -> str:
        if strategy == "vlm":
            node = {"name": "Partitioner", "type": "partition", "subtype": "vlm", "settings": {"is_dynamic": False, "allow_fast": True}}
        else:
            node = {"name": "Partitioner", "type": "partition", "subtype": "unstructured_api", "settings": {"strategy": strategy}}
        return json.dumps({"job_nodes": [node]})

    def create_parse_job(self, paths: list[Path], strategy: str = "fast") -> str:
        handles = []
        files = []
        try:
            for path in paths:
                handle = path.open("rb")
                handles.append(handle)
                files.append(("input_files", (path.name, handle, "application/pdf")))
            response = httpx.post(self.url("jobs/"), headers=self.headers(), data={"request_data": self.request_data(strategy)}, files=files, timeout=None)
            response.raise_for_status()
            return response.json()["id"]
        finally:
            for handle in handles:
                handle.close()

    def wait_for_job(self, job_id: str) -> dict:
        while True:
            response = httpx.get(self.url(f"jobs/{job_id}"), headers=self.headers(), timeout=60)
            response.raise_for_status()
            job = response.json()
            status = getattr(job.get("status"), "value", job.get("status"))
            if status == "COMPLETED":
                return job
            if status in {"FAILED", "STOPPED"}:
                raise RuntimeError(f"Unstructured job {job_id} ended with {status}")
            time.sleep(self.poll_seconds)

    def download_output(self, job_id: str, file_id: str) -> list[dict]:
        response = httpx.get(self.url(f"jobs/{job_id}/download"), headers=self.headers(), params={"file_id": file_id}, timeout=None)
        response.raise_for_status()
        return response.json()

    def elements_to_text(self, elements: list[dict]) -> str:
        if not isinstance(elements, list):
            return json.dumps(elements, indent=2)
        return "\n\n".join(str(item.get("text", "")).strip() for item in elements if isinstance(item, dict) and item.get("text"))
