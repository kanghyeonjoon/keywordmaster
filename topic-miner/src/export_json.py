"""트렌드 대시보드용 데이터 발행.

금고(시트) 전체를 읽어 data/vault.json으로 저장한다.
- topics: 최근 14일 (대시보드 기본 화면)
- archive: 14일이 지난 것 중 가치가 남은 주제만 보관 (명당 또는 화제성 S/A)
daily.yml이 수집 직후 실행해 리포에 커밋 → GitHub Pages가 서빙 →
trends.html이 같은 출처(same-origin)에서 읽으므로 시트 공개가 필요 없다.
--dry-run: 시트 대신 dry_run_vault.csv 사용.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(HERE)
OUT_PATH = os.path.join(REPO_ROOT, "data", "vault.json")

INDUSTRY_LABEL = {
    "dental": "치과", "derma": "피부과",
    "interior": "인테리어", "cancer": "암",
    "construction": "건설분쟁",
}

RECENT_DAYS = 14        # 기본 화면에 보여줄 기간
ARCHIVE_MAX = 200       # 아카이브 보관 상한 (파일 크기 방어)
VALUABLE_BUZZ = {"S", "A"}  # 아카이브에 남길 화제성 등급


def _parse_json_field(value, default):
    try:
        parsed = json.loads(value) if value else default
        return parsed if isinstance(parsed, type(default)) else default
    except (json.JSONDecodeError, TypeError):
        return default


def build(rows: list[dict]) -> dict:
    topics = []
    for idx, r in enumerate(rows):
        topics.append({
            "_idx": idx,  # 시트 append 순서 = 최신성 보조 키 (같은 날짜 내 중복 제거용)
            "date": str(r.get("date", "")),
            "industry": r.get("industry", ""),
            "keyword": r.get("keyword", ""),
            "power_grade": r.get("power_grade", ""),
            "buzz_grade": r.get("buzz_grade", ""),
            "is_sweetspot": str(r.get("is_sweetspot", "")).upper() == "TRUE",
            "score": int(float(r.get("score") or 0)),
            "click_reason": r.get("click_reason", ""),
            "naver_questions": str(r.get("naver_questions", ""))[:200],
            "ref_videos": _parse_json_field(r.get("ref_videos"), []),
            "trend": _parse_json_field(r.get("trend"), []),
        })
    # 최신 날짜 우선(같은 날짜면 나중에 적립된 행 우선), 같은 키워드는 최신 것만
    topics.sort(key=lambda t: (t["date"], t["_idx"]), reverse=True)
    seen, unique = set(), []
    for t in topics:
        key = (t["industry"], t["keyword"])
        if key in seen:
            continue
        seen.add(key)
        t.pop("_idx", None)
        unique.append(t)

    # 최근 14일은 그대로, 그보다 오래된 것은 가치가 남은 주제만 아카이브로
    cutoff = (dt.date.today() - dt.timedelta(days=RECENT_DAYS)).isoformat()
    recent = [t for t in unique if t["date"] >= cutoff]
    archive = [t for t in unique
               if t["date"] < cutoff
               and (t["is_sweetspot"] or t["buzz_grade"] in VALUABLE_BUZZ)][:ARCHIVE_MAX]
    return {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "labels": INDUSTRY_LABEL,
        "topics": recent,
        "archive": archive,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        with open(os.path.join(HERE, "dry_run_vault.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        import sheets
        rows = sheets.fetch_all()

    data = build(rows)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"data/vault.json 발행 완료 — 최근 {len(data['topics'])}개 + 아카이브 {len(data['archive'])}개")


if __name__ == "__main__":
    main()
