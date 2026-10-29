import json

from tavily_mux.domain.endpoints import CreditProfile


def estimate_credits(profile: CreditProfile, body: bytes) -> int:
    if profile is CreditProfile.NONE:
        return 0
    if profile is CreditProfile.UNKNOWN:
        return 1
    payload = json_object(body)
    if profile is CreditProfile.SEARCH:
        return 2 if payload.get("search_depth") == "advanced" else 1
    if profile is CreditProfile.EXTRACT:
        return 2 if payload.get("extract_depth") == "advanced" else 1
    if profile is CreditProfile.MAP:
        return 2 if payload.get("instructions") else 1
    if profile is CreditProfile.CRAWL:
        extraction = 2 if payload.get("extract_depth") == "advanced" else 1
        mapping = 2 if payload.get("instructions") else 1
        return mapping + extraction
    if profile is CreditProfile.RESEARCH:
        return 15 if payload.get("model") == "pro" else 4
    return 1


def json_object(body: bytes) -> dict[str, object]:
    if not body:
        return {}
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
