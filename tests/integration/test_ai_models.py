import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import settings
from src.infrastructure.config.env_manager import env_manager


@pytest.fixture
def models_client(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('OPENAI_BASE_URL=https://saved.test/v1\nOPENAI_API_KEY=saved-secret\n')
    monkeypatch.setattr(env_manager, 'env_file', env_file)
    app = FastAPI()
    app.include_router(settings.router)
    return TestClient(app), env_file


def mock_provider(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(
        transport=httpx.MockTransport(handler), **kw))


@pytest.mark.parametrize('payload', [
    {'data': [{'id': 'b'}, {'id': 'a'}, {'id': 'b'}, {'bad': 1}]},
    {'models': [{'id': 'b'}, {'name': 'a'}]},
    {'data': {'models': ['b', 'a']}},
    ['b', 'a', 'b', '', 123],
])
def test_reads_and_normalizes_models_without_changing_settings(models_client, monkeypatch, payload):
    client, env_file = models_client
    before = env_file.read_bytes()
    def handler(request):
        assert str(request.url) == 'https://saved.test/v1/models'
        assert request.headers['authorization'] == 'Bearer saved-secret'
        return httpx.Response(200, json=payload)
    mock_provider(monkeypatch, handler)
    response = client.post('/api/settings/ai/models', json={})
    assert response.status_code == 200
    assert response.json()['success'] is True
    assert response.json()['models'] == ['a', 'b']
    assert env_file.read_bytes() == before


@pytest.mark.parametrize('suffix', ['/v1/', '/v1/chat/completions', '/v1/responses', '/v1/models'])
def test_uses_unsaved_url_and_key(models_client, monkeypatch, suffix):
    client, _ = models_client
    def handler(request):
        assert str(request.url) == 'https://draft.test/v1/models'
        assert request.headers['authorization'] == 'Bearer draft-secret'
        return httpx.Response(200, json={'data': [{'id': 'draft-model'}]})
    mock_provider(monkeypatch, handler)
    response = client.post('/api/settings/ai/models', json={
        'OPENAI_BASE_URL': 'https://draft.test' + suffix, 'OPENAI_API_KEY': 'draft-secret',
    })
    assert response.json()['models'] == ['draft-model']


@pytest.mark.parametrize('status', [404, 405, 200])
def test_root_url_falls_back_to_v1_for_missing_endpoint(models_client, monkeypatch, status):
    client, _ = models_client
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if len(paths) == 1:
            return httpx.Response(status, text='<html>website</html>', headers={'content-type': 'text/html'})
        return httpx.Response(200, json={'data': ['model']})
    mock_provider(monkeypatch, handler)
    response = client.post('/api/settings/ai/models', json={'OPENAI_BASE_URL': 'https://provider.test'})
    assert response.json()['models'] == ['model']
    assert paths == ['/models', '/v1/models']


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_provider_error_is_safe_and_does_not_log_out_user(models_client, monkeypatch, status):
    client, _ = models_client
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text='provider echoed saved-secret')
    mock_provider(monkeypatch, handler)
    response = client.post('/api/settings/ai/models', json={})
    assert response.status_code == 200
    assert response.json()['success'] is False
    assert response.json()['models'] == []
    assert 'saved-secret' not in response.text
    assert len(calls) == 1


@pytest.mark.parametrize('payload,success', [({'data': []}, True), ({'error': 'bad'}, False)])
def test_empty_list_is_distinct_from_invalid_payload(models_client, monkeypatch, payload, success):
    client, _ = models_client
    mock_provider(monkeypatch, lambda _: httpx.Response(200, json=payload))
    response = client.post('/api/settings/ai/models', json={})
    assert response.json()['success'] is success
    assert response.json()['models'] == []


def test_timeout_and_invalid_url_allow_manual_entry(models_client, monkeypatch):
    client, _ = models_client
    def handler(request):
        raise httpx.ReadTimeout('saved-secret', request=request)
    mock_provider(monkeypatch, handler)
    for body in [{}, {'OPENAI_BASE_URL': 'file:///etc/passwd'}, {'OPENAI_BASE_URL': 'https://provider.test:bad'}]:
        response = client.post('/api/settings/ai/models', json=body)
        assert response.json()['success'] is False
        assert 'saved-secret' not in response.text


def test_changing_base_url_host_does_not_leak_saved_api_key(models_client, monkeypatch):
    client, _ = models_client
    captured_headers = []

    def handler(request):
        captured_headers.append((str(request.url), dict(request.headers)))
        return httpx.Response(200, json={'data': [{'id': 'm1'}]})

    mock_provider(monkeypatch, handler)

    other_resp = client.post('/api/settings/ai/models', json={'OPENAI_BASE_URL': 'https://other-provider.test/v1'})
    assert other_resp.status_code == 200
    assert other_resp.json()['success'] is True
    assert 'authorization' not in captured_headers[0][1]
    assert 'saved-secret' not in other_resp.text

    same_origin_resp = client.post('/api/settings/ai/models', json={'OPENAI_BASE_URL': 'https://saved.test'})
    assert same_origin_resp.status_code == 200
    assert same_origin_resp.json()['success'] is True
    assert captured_headers[1][1]['authorization'] == 'Bearer saved-secret'
