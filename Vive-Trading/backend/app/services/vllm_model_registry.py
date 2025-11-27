import logging
from typing import List, Optional
from threading import Lock

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = OpenAI(
    base_url=settings.VLLM_BASE_URL,
    api_key=settings.VLLM_API_KEY,
)

_models_cache: List[str] = []
_cache_lock = Lock()


def _ensure_default_in_cache(cache: List[str]) -> List[str]:
    if settings.VLLM_DEFAULT_MODEL and settings.VLLM_DEFAULT_MODEL not in cache:
        cache = cache + [settings.VLLM_DEFAULT_MODEL]
    return cache


def refresh_available_models() -> List[str]:
    """
    vLLM(OpenAI 호환) 서버에서 지원하는 모델 목록을 새로고침합니다.
    """
    global _models_cache
    try:
        response = _client.models.list()
        fetched = [model.id for model in getattr(response, "data", []) if getattr(model, "id", None)]
        if fetched:
            with _cache_lock:
                _models_cache = _ensure_default_in_cache(fetched)
        else:
            logger.warning("⚠️ vLLM 서버에서 모델 목록을 비어있는 상태로 반환했습니다. 기본 모델만 사용합니다.")
            with _cache_lock:
                _models_cache = _ensure_default_in_cache(_models_cache or [])
    except Exception as exc:
        logger.warning("⚠️ vLLM 모델 목록을 조회하지 못했습니다: %s", exc)
        with _cache_lock:
            _models_cache = _ensure_default_in_cache(_models_cache or [])
    return list(_models_cache)


def get_available_models(force_refresh: bool = False) -> List[str]:
    """
    캐시된 모델 목록을 반환합니다. 필요 시 강제 새로고침을 수행합니다.
    """
    with _cache_lock:
        cache_empty = len(_models_cache) == 0

    if force_refresh or cache_empty:
        return refresh_available_models()

    return list(_models_cache)


def get_preferred_model_name(requested: Optional[str] = None) -> str:
    """
    요청된 모델명이 사용 가능하면 그대로 반환하고,
    그렇지 않으면 기본값 혹은 첫 번째 지원 모델을 반환합니다.
    """
    available = get_available_models()

    if requested and requested in available:
        return requested

    if requested and requested not in available:
        logger.warning("⚠️ 요청된 모델 '%s'을(를) 사용할 수 없습니다. 기본 모델로 대체합니다.", requested)

    if settings.VLLM_DEFAULT_MODEL in available:
        return settings.VLLM_DEFAULT_MODEL

    if available:
        logger.warning("⚠️ 기본 모델이 목록에 없어서 첫 번째 모델 '%s'을(를) 사용합니다.", available[0])
        return available[0]

    logger.warning("⚠️ 사용 가능한 모델 목록이 비어 있습니다. 설정된 기본 모델 '%s'을(를) 사용합니다.", settings.VLLM_DEFAULT_MODEL)
    return settings.VLLM_DEFAULT_MODEL
