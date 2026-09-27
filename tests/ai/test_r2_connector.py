from ai.storage_connectors.r2_connector import R2Connector


def test_r2_connector_url_and_supported_files(monkeypatch):
    monkeypatch.setattr("ai.storage_connectors.r2_connector.boto3.client", lambda *args, **kwargs: object())
    connector = R2Connector("bucket", public_base_url="https://cdn.example.com/root")

    assert connector.object_url("docs/a.pdf") == "https://cdn.example.com/root/docs/a.pdf"
    assert connector.is_supported("case.PDF")
    assert not connector.is_supported("image.png")
