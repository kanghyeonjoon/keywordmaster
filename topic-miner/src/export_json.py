"""트렌드 대시보드용 데이터 발행.

금고(시트)의 최근 14일 데이터를 data/vault.json으로 저장한다.
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
}


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
    return {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "labels": INDUSTRY_LABEL,
        "topics": unique,
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
        rows = sheets.fetch_last_days(14)

    data = build(rows)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"data/vault.json 발행 완료 — 주제 {len(data['topics'])}개")


if __name__ == "__main__":
    main()
