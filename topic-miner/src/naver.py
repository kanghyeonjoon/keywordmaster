"""네이버 검색 API 래퍼 — 지식iN·카페의 실제 질문(원석) 수집."""
import os
import json
import re
import requests

TIMEOUT = 15


def _headers() -> dict:
    cid = os.environ.get("NAVER_CLIENT_ID", "")
    sec = os.environ.get("NAVER_CLIENT_SECRET", "")
    if not cid or not sec:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없습니다.")
    return {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&").strip()


def _search(endpoint: str, seed: str, display: int) -> list[str]:
    r = requests.get(
        f"https://openapi.naver.com/v1/search/{endpoint}.json",
        params={"query": seed, "display": display, "sort": "sim"},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return [_strip_tags(i.get("title", "")) for i in r.json().get("items", [])]


def search_questions(seed: str, per_source: int = 8) -> list[str]:
    """지식iN(우선) + 카페 제목을 합쳐 실제 질문·고민 목록을 반환."""
    questions: list[str] = []
    try:
        questions += _search("kin", seed, per_source)          # 지식iN — 핵심 소스
    except requests.RequestException:
        pass
    try:
        questions += _search("cafearticle", seed, per_source)  # 카페 — 날것의 고민글
    except requests.RequestException:
        pass
    seen, out = set(), []
    for q in questions:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def load_fixture(seed: str) -> list[str]:
    """dry-run용 샘플 질문."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "fixtures", "naver_sample.json"), encoding="utf-8") as f:
        base = json.load(f)
    return [q.replace("{seed}", seed) for q in base]
