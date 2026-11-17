"""Read model IDs from OpenAI-compatible providers without changing settings."""
import re
from urllib.parse import urlsplit, urlunsplit

import httpx


class ModelListError(ValueError):
    """A safe, user-facing model discovery error."""


def _model_urls(base_url: str) -> list[str]:
    url = urlsplit(base_url.strip())
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
        raise ModelListError('请填写有效的 HTTP(S) API Base URL。')
    path = url.path.rstrip('/')
    for suffix in ('/chat/completions', '/responses', '/models'):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    paths = [path + '/models']
    if not re.search(r'/v\d+(?:beta\d*)?$', path):
        paths.append(path + '/v1/models')
    return [urlunsplit((url.scheme, url.netloc, p, url.query, '')) for p in paths]


def _parse_models(payload: object) -> list[str]:
    # Standard {data: [{id: ...}]} plus common gateway list wrappers.
    items = payload
    for _ in range(2):
        if isinstance(items, dict):
            items = items.get('data', items.get('models'))
    if not isinstance(items, list):
        raise ModelListError('接口返回的模型列表格式无法识别，可以手动填写模型名称。')
    models = set()
    for item in items:
        value = (item.get('id') or item.get('name')) if isinstance(item, dict) else item
        if isinstance(value, str) and value.strip():
            models.add(value.strip())
    if items and not models:
        raise ModelListError('接口未返回可识别的模型 ID，可以手动填写模型名称。')
    return sorted(models, key=lambda name: (name.casefold(), name))


def list_provider_models(base_url: str, api_key: str, proxy_url: str = '') -> list[str]:
    urls = _model_urls(base_url)
    headers = {'Accept': 'application/json'}
    if api_key.strip():
        headers['Authorization'] = f'Bearer {api_key.strip()}'
    options = {'timeout': httpx.Timeout(20.0), 'follow_redirects': False}
    if proxy_url.strip():
        options['proxy'] = proxy_url.strip()
    try:
        with httpx.Client(**options) as client:
            for index, url in enumerate(urls):
                response = client.get(url, headers=headers)
                missing_endpoint = response.status_code in (404, 405) or (
                    response.is_success and 'text/html' in response.headers.get('content-type', '')
                )
                if missing_endpoint:
                    if index + 1 < len(urls):
                        continue
                    raise ModelListError('此接口未提供模型列表，可以手动填写模型名称。')
                if response.status_code in (401, 403):
                    raise ModelListError('模型列表鉴权失败，请检查 API Key 或账号的模型列表权限。')
                if response.status_code == 429:
                    raise ModelListError('模型列表请求过于频繁，请稍后重试。')
                if not response.is_success:
                    raise ModelListError(f'读取模型列表失败（HTTP {response.status_code}），可以手动填写模型名称。')
                return _parse_models(response.json())
    except ModelListError:
        raise
    except httpx.TimeoutException:
        raise ModelListError('读取模型列表超时，请检查网络或代理，也可手动填写模型名称。') from None
    except httpx.HTTPError:
        raise ModelListError('无法连接模型列表接口，请检查接口地址、网络或代理。') from None
    except (ValueError, httpx.InvalidURL):
        # Never echo provider bodies or exception URLs, which may contain keys.
        raise ModelListError('接口地址、代理配置或模型列表响应无效，可以手动填写模型名称。') from None
    return []
