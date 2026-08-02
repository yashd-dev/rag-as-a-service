import json
import os
import time
from pathlib import Path

import httpx

POLL_SECONDS = int(os.getenv("UNSTRUCTURED_POLL_SECONDS", "10"))
DEFAULT_API_URL = "https://platform-api.transform.unstructured.io/api/v1"
PARTITION_STRATEGY = os.getenv("UNSTRUCTURED_PARTITION_STRATEGY", "fast")


def require_config() -> None:
    if not os.getenv("UNSTRUCTURED_API_KEY"):
        raise RuntimeError("UNSTRUCTURED_API_KEY is not set")


def api_url(path: str) -> str:
    base = (
        os.getenv("UNSTRUCTURED_API_URL")
        or os.getenv("UNSTRUCTURED_API_UR")
        or DEFAULT_API_URL
    ).rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def headers() -> dict[str, str]:
    require_config()
    return {
        "accept": "application/json",
        "unstructured-api-key": os.environ["UNSTRUCTURED_API_KEY"],
    }


def raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Unstructured API {response.status_code}: {response.text}"
        ) from exc


def request_data() -> str:
    if PARTITION_STRATEGY == "vlm":
        node = {
            "name": "Partitioner",
            "type": "partition",
            "subtype": "vlm",
            "settings": {"is_dynamic": False, "allow_fast": True},
        }
    else:
        node = {
            "name": "Partitioner",
            "type": "partition",
            "subtype": "unstructured_api",
            "settings": {"strategy": PARTITION_STRATEGY},
        }
    return json.dumps({"job_nodes": [node]})


def create_parse_job(paths: list[Path]) -> str:
    files = []
    handles = []
    try:
        for path in paths:
            handle = path.open("rb")
            handles.append(handle)
            files.append(("input_files", (path.name, handle, "application/pdf")))

        response = httpx.post(
            api_url("jobs/"),
            headers=headers(),
            data={"request_data": request_data()},
            files=files,
            timeout=None,
        )
        raise_for_status(response)
        return response.json()["id"]
    finally:
        for handle in handles:
            handle.close()


def status_value(status) -> str:
    return getattr(status, "value", status)


def wait_for_job(job_id: str):
    while True:
        response = httpx.get(api_url(f"jobs/{job_id}"), headers=headers(), timeout=60)
        raise_for_status(response)
        job = response.json()
        status = status_value(job["status"])
        print(f"{job_id}: {status}", flush=True)
        if status == "COMPLETED":
            return job
        if status in {"FAILED", "STOPPED"}:
            raise RuntimeError(f"Unstructured job {job_id} ended with {status}")
        time.sleep(POLL_SECONDS)


def download_output(job_id: str, file_id: str):
    response = httpx.get(
        api_url(f"jobs/{job_id}/download"),
        headers=headers(),
        params={"file_id": file_id},
        timeout=None,
    )
    raise_for_status(response)
    return response.json()


def elements_to_text(elements) -> str:
    if not isinstance(elements, list):
        return json.dumps(elements, indent=2)
    return "\n\n".join(
        str(element.get("text", "")).strip()
        for element in elements
        if isinstance(element, dict) and element.get("text")
    )
