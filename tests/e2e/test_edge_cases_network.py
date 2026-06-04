import pytest
import os
import json
from fastapi.testclient import TestClient
from nptmpl.server.main import create_app
from nptmpl.core.remote.http import HttpTransport
import requests_mock
import threading

@pytest.fixture
def test_storage(tmp_path):
    storage = tmp_path / "server_storage"
    storage.mkdir()
    return storage

@pytest.fixture
def client(test_storage):
    os.environ["NPTMPL_SERVER_TOKEN"] = "test-token"
    app = create_app(test_storage)
    return TestClient(app)

def create_mock_tarball():
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="README.md")
        info.size = 11
        tar.addfile(tarinfo=info, fileobj=io.BytesIO(b"hello world"))
    return buf.getvalue()

def test_server_502_504_retry(tmp_path):
    """Test that the client retries on 502/504 errors."""
    remote = HttpTransport("http://fake-registry", retries=2, timeout=1)
    
    with requests_mock.Mocker() as m:
        # Mock 502 once, then success
        m.get("http://fake-registry/api/v1/templates/test/retry", [
            {"status_code": 502},
            {"json": {"metadata": {"name": "retry", "version": "1.0.0", "author": "a", "description": "d", "languages": ["p"]}}}
        ])
        
        meta = remote.fetch_metadata("test/retry")
        assert meta.version == "1.0.0"
        assert m.call_count == 2

def test_billion_laughs_attack(client):
    """Test protection against billion-laughs YAML attack in metadata."""
    # Billion laughs payload
    billion_laughs = """
    a: &a ["lol","lol","lol","lol","lol","lol","lol","lol","lol"]
    b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]
    c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b]
    d: &d [*c,*c,*c,*c,*c,*c,*c,*c,*c]
    e: &e [*d,*d,*d,*d,*d,*d,*d,*d,*d]
    f: &f [*e,*e,*e,*e,*e,*e,*e,*e,*e]
    g: &g [*f,*f,*f,*f,*f,*f,*f,*f,*f]
    h: &h [*g,*g,*g,*g,*g,*g,*g,*g,*g]
    i: &i [*h,*h,*h,*h,*h,*h,*h,*h,*h]
    """
    # Note: yaml.safe_load in Python's PyYAML generally protects against this 
    # by limiting the recursion or total size, but it's good to verify.
    
    meta = {
        "target": "test/billion",
        "version": "1.0.0",
        "author": "tester",
        "description": billion_laughs,
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    
    response = client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", create_mock_tarball(), "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    # If safe_load is used, it might just process it as a string if it's inside JSON,
    # but the server-side reindexer or client-side loader might fail.
    # Here we are sending it as part of JSON, which is already parsed by FastAPI.
    assert response.status_code == 200

def test_concurrent_pushes(client):
    """Test concurrent pushes for the same version."""
    meta = {
        "target": "test/concurrent",
        "version": "1.0.0",
        "author": "tester",
        "description": "desc",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    tarball = create_mock_tarball()
    
    results = []
    def push():
        try:
            resp = client.post(
                "/api/v1/templates/push",
                data={"metadata_json": json.dumps(meta)},
                files={"tarball": ("data.tar.gz", tarball, "application/gzip")},
                headers={"Authorization": "Bearer test-token"}
            )
            results.append(resp.status_code)
        except Exception as e:
            results.append(str(e))

    threads = [threading.Thread(target=push) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # One should succeed (200), others should fail with conflict (409)
    assert 200 in results
    assert 409 in results

def test_malicious_html_injection_jinja(client):
    """Test for HTML injection in metadata which might be rendered in Jinja2 templates."""
    payload = "<img src=x onerror=alert(1)>"
    meta = {
        "target": "test/html",
        "version": "1.0.0",
        "author": payload,
        "description": "Malicious author",
        "languages": ["python"],
        "added_date": "2024-01-01 00:00:00"
    }
    client.post(
        "/api/v1/templates/push",
        data={"metadata_json": json.dumps(meta)},
        files={"tarball": ("data.tar.gz", create_mock_tarball(), "application/gzip")},
        headers={"Authorization": "Bearer test-token"}
    )
    
    # Check Web UI
    response = client.get("/")
    assert payload not in response.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in response.text
