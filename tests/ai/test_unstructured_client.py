import json

from ai.ingestion.unstructured_client import UnstructuredClient


def test_unstructured_request_data_fast_and_vlm():
    client = UnstructuredClient("key", "https://example.com/api")

    fast = json.loads(client.request_data("fast"))
    vlm = json.loads(client.request_data("vlm"))

    assert fast["job_nodes"][0]["subtype"] == "unstructured_api"
    assert vlm["job_nodes"][0]["subtype"] == "vlm"


def test_elements_to_text_joins_text_only():
    client = UnstructuredClient("key", "https://example.com/api")

    assert client.elements_to_text([{"text": "One"}, {"x": 1}, {"text": "Two"}]) == "One\n\nTwo"
