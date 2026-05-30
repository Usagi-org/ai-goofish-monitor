import asyncio

from src.xianyu.seller_profile import (
    build_seller_profile_loader,
    resolve_seller_profile_cache_ttl,
)
from src.xianyu.seller_profile_scraper import scrape_user_profile


def test_scraper_keeps_public_seller_profile_entrypoint():
    from src import scraper

    assert scraper.scrape_user_profile is scrape_user_profile


def test_resolve_seller_profile_cache_ttl_prefers_task_config(monkeypatch):
    monkeypatch.setenv("SELLER_PROFILE_CACHE_TTL", "120")

    assert resolve_seller_profile_cache_ttl({"seller_profile_cache_ttl": "30"}) == 30


def test_resolve_seller_profile_cache_ttl_uses_env_default(monkeypatch):
    monkeypatch.setenv("SELLER_PROFILE_CACHE_TTL", "120")

    assert resolve_seller_profile_cache_ttl({}) == 120


def test_resolve_seller_profile_cache_ttl_invalid_values_fall_back(monkeypatch):
    monkeypatch.setenv("SELLER_PROFILE_CACHE_TTL", "invalid")

    assert (
        resolve_seller_profile_cache_ttl({"seller_profile_cache_ttl": "also-invalid"})
        == 1800
    )


def test_resolve_seller_profile_cache_ttl_clamps_negative_values(monkeypatch):
    monkeypatch.setenv("SELLER_PROFILE_CACHE_TTL", "120")

    assert resolve_seller_profile_cache_ttl({"seller_profile_cache_ttl": -5}) == 0


def test_build_seller_profile_loader_coerces_user_id_and_caches(monkeypatch):
    monkeypatch.setenv("SELLER_PROFILE_CACHE_TTL", "60")
    calls = []
    context = object()

    async def profile_scraper(scraper_context, seller_key: str):
        calls.append((scraper_context, seller_key))
        return {"卖家ID": seller_key, "items": []}

    async def run():
        loader = build_seller_profile_loader(context, {}, profile_scraper)
        first = await loader(12345)
        first["items"].append("mutated")
        second = await loader("12345")
        return first, second

    first, second = asyncio.run(run())

    assert calls == [(context, "12345")]
    assert first == {"卖家ID": "12345", "items": ["mutated"]}
    assert second == {"卖家ID": "12345", "items": []}
