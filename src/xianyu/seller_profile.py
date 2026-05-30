import os
from typing import Awaitable, Callable

from src.services.seller_profile_cache import SellerProfileCache


SellerProfileScraper = Callable[[object, str], Awaitable[dict]]
SellerProfileLoader = Callable[[object], Awaitable[dict]]


def _as_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_seller_profile_cache_ttl(task_config: dict) -> int:
    configured = task_config.get("seller_profile_cache_ttl")
    default = _as_int(os.getenv("SELLER_PROFILE_CACHE_TTL"), 1800)
    return max(0, _as_int(configured, default))


def build_seller_profile_loader(
    context,
    task_config: dict,
    profile_scraper: SellerProfileScraper,
) -> SellerProfileLoader:
    cache = SellerProfileCache(
        ttl_seconds=resolve_seller_profile_cache_ttl(task_config)
    )

    async def load_seller_profile(user_id) -> dict:
        return await cache.get_or_load(
            str(user_id),
            lambda seller_key: profile_scraper(context, seller_key),
        )

    return load_seller_profile
