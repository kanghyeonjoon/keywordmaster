"""YouTube Data API v3 래퍼 — 경쟁·수요·등급용 공개지표 수집."""
import os
import json
import datetime as dt
import requests

BASE = "https://www.googleapis.com/youtube/v3"
TIMEOUT = 20


def _key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY 환경변수가 없습니다.")
    return key


def search(seed: str, max_results: int = 8) -> list[dict]:
    """씨앗 키워드로 영상 검색 후 각 영상의 공개지표까지 붙여 반환.

    반환 항목: title, video_id, url, channel, published_at,
               view_count, subscriber_count, days_since_upload
    """
    r = requests.get(
        f"{BASE}/search",
        params={
            "key": _key(), "part": "snippet", "q": seed, "type": "video",
            "maxResults": max_results, "relevanceLanguage": "ko", "regionCode": "KR",
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    video_ids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
    channel_ids = list({i["snippet"]["channelId"] for i in items})
    if not video_ids:
        return []

    stats = requests.get(
        f"{BASE}/videos",
        params={"key": _key(), "part": "statistics,snippet", "id": ",".join(video_ids)},
        timeout=TIMEOUT,
    )
    stats.raise_for_status()
    by_id = {v["id"]: v for v in stats.json().get("items", [])}

    subs = requests.get(
        f"{BASE}/channels",
        params={"key": _key(), "part": "statistics", "id": ",".join(channel_ids)},
        timeout=TIMEOUT,
    )
    subs.raise_for_status()
    subs_by_channel = {
        c["id"]: int(c["statistics"].get("subscriberCount", 0) or 0)
        for c in subs.json().get("items", [])
    }

    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for item in items:
        vid = item.get("id", {}).get("videoId")
        v = by_id.get(vid)
        if not v:
            continue
        published = dt.datetime.fromisoformat(
            v["snippet"]["publishedAt"].replace("Z", "+00:00")
        )
        out.append({
            "title": v["snippet"]["title"],
            "video_id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "channel": v["snippet"]["channelTitle"],
            "published_at": v["snippet"]["publishedAt"],
            "view_count": int(v["statistics"].get("viewCount", 0) or 0),
            "subscriber_count": subs_by_channel.get(item["snippet"]["channelId"], 0),
            "days_since_upload": max((now - published).days, 1),
        })
    return out


def load_fixture(seed: str) -> list[dict]:
    """dry-run용 샘플 데이터. 씨앗별로 수치를 변형해 등급 분포를 재현한다."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "fixtures", "youtube_sample.json"), encoding="utf-8") as f:
        base = json.load(f)
    scale = (abs(hash(seed)) % 90 + 10) / 30.0  # 씨앗마다 0.3~3.3배 변형
    out = []
    for v in base:
        v = dict(v)
        v["title"] = v["title"].replace("{seed}", seed)
        v["view_count"] = int(v["view_count"] * scale)
        out.append(v)
    return out
