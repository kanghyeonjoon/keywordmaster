"""네이버 검색 API 래퍼 — 지식iN·카페의 실제 질문(원석) 수집."""
import os
import json
import re
import requests

TIMEOUT = 15


def _headers() -> dict:
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    sec = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
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


def search_trends(seeds: list[str], weeks: int = 13) -> dict[str, list[int]]:
    """데이터랩 검색어트렌드 — 씨앗별 주간 상대비율(0~100) 시계열.

    한 콜에 최대 5개 그룹이므로 업종당 1콜. 앱에 '데이터랩(검색어트렌드)' API가
    추가되지 않았거나 한도 초과면 빈 dict를 반환하고 조용히 넘어간다.
    상대비율이므로 '검색량 개수'로 표기하지 않는다 (PRD 규칙).
    """
    import datetime as dt

    end = dt.date.today()
    start = end - dt.timedelta(weeks=weeks)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "week",
        "keywordGroups": [{"groupName": s, "keywords": [s]} for s in seeds[:5]],
    }
    try:
        r = requests.post(
            "https://openapi.naver.com/v1/datalab/search",
            headers={**_headers(), "Content-Type": "application/json"},
            json=body,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
    except (requests.RequestException, RuntimeError):
        return {}

    out: dict[str, list[int]] = {}
    for group in r.json().get("results", []):
        ratios = [round(p.get("ratio", 0)) for p in group.get("data", [])]
        out[group.get("title", "")] = ratios[-weeks:]
    return out


def load_trend_fixture(seeds: list[str]) -> dict[str, list[int]]:
    """dry-run용 샘플 추세 — 씨앗마다 다른 모양의 13주 곡선."""
    out = {}
    for i, s in enumerate(seeds):
        base = (abs(hash(s)) % 40) + 10
        out[s] = [min(100, base + (w * (i + 2)) % 60) for w in range(13)]
    return out
