"""매일 06:00 KST 수집기 (PRD 8절).

씨앗 → 수집 → 등급화 → 채점 → 금고 적립.
--dry-run: 외부 API 없이 fixtures로 전체 파이프라인을 검증하고 CSV로 출력.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

import requests
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youtube  # noqa: E402
import naver  # noqa: E402
import grader  # noqa: E402
import scorer  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP_N_PER_INDUSTRY = 5  # 업종당 적립 수 (하루 총 20개 = 5 × 4업종)


def f_demand(videos: list[dict]) -> str:
    """수요 신호: 검색결과 영상들의 조회수 규모 기반."""
    if not videos:
        return "낮음"
    avg_views = sum(v["view_count"] for v in videos) / len(videos)
    if avg_views >= 100_000:
        return "높음"
    if avg_views >= 20_000:
        return "보통"
    return "낮음"


def f_comp(videos: list[dict]) -> str:
    """경쟁 신호: 대형 채널(구독 10만+)의 영상 밀도 기반."""
    if not videos:
        return "낮음"
    big = sum(1 for v in videos if v["subscriber_count"] >= 100_000)
    ratio = big / len(videos)
    if ratio >= 0.5:
        return "높음"
    if ratio >= 0.25:
        return "보통"
    return "낮음"


def load_seeds() -> dict:
    with open(os.path.join(HERE, "config", "seeds.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)["industries"]


def collect(dry_run: bool = False) -> list[dict]:
    today = dt.date.today().isoformat()
    industries = load_seeds()
    all_rows: list[dict] = []
    total_seeds = 0
    yt_failures = 0

    for code, ind in industries.items():
        label = ind["label"]
        medical = bool(ind.get("medical_ad_law", False))
        candidates = []

        # 데이터랩 검색추세 (업종당 1콜, 미신청·실패 시 빈 dict)
        trends = (naver.load_trend_fixture(ind["seeds"]) if dry_run
                  else naver.search_trends(ind["seeds"]))

        for seed in ind["seeds"]:
            total_seeds += 1
            try:
                videos = youtube.load_fixture(seed) if dry_run else youtube.search(seed)
            except requests.RequestException as e:
                yt_failures += 1
                print(f"  ⚠ 유튜브 수집 실패({seed}): {e}")
                videos = []
            questions = naver.load_fixture(seed) if dry_run else naver.search_questions(seed)
            grades = grader.grade(videos)
            candidates.append({
                "seed": seed,
                "videos": videos,
                "demand_signal": f_demand(videos),
                "comp_signal": f_comp(videos),
                "power_grade": grades["power_grade"],
                "buzz_grade": grades["buzz_grade"],
                "questions": questions,
                "_top_video": grades["top_video"],
                "_top3_videos": sorted(videos, key=lambda v: v["view_count"], reverse=True)[:3],
                "_trend": trends.get(seed, []),
            })

        rank = scorer.mock_rank_and_translate if dry_run else scorer.rank_and_translate
        scored = rank(
            [{k: v for k, v in c.items() if not k.startswith("_")} for c in candidates],
            medical_ad_law=medical,
        )

        by_seed = {c["seed"]: c for c in candidates}
        rows = []
        for s in scored:
            c = by_seed.get(s.get("seed"))
            if not c:
                continue
            rows.append({
                "date": today,
                "industry": code,
                "seed": c["seed"],
                "keyword": s.get("keyword", c["seed"]),
                "demand": s.get("demand", c["demand_signal"]),
                "comp": s.get("comp", c["comp_signal"]),
                "power_grade": c["power_grade"],     # 등급은 항상 실측 근사값 사용 (규칙 ⑤)
                "buzz_grade": c["buzz_grade"],
                "is_sweetspot": "TRUE" if grader.is_sweetspot(c["power_grade"], c["buzz_grade"]) else "FALSE",
                "naver_questions": s.get("naver_questions", " / ".join(c["questions"][:3])),
                "score": s.get("score", 0),
                "click_reason": s.get("click_reason", ""),
                "ref_url": (c["_top_video"] or {}).get("url", ""),
                "ref_videos": json.dumps([
                    {"t": v["title"], "id": v["video_id"],
                     "v": v["view_count"], "d": v["days_since_upload"]}
                    for v in c["_top3_videos"]
                ], ensure_ascii=False),
                "trend": json.dumps(c["_trend"]),
            })

        top_n = int(ind.get("top_n", TOP_N_PER_INDUSTRY))
        rows.sort(key=lambda r: (r["is_sweetspot"] == "TRUE", r["score"]), reverse=True)
        all_rows.extend(rows[:top_n])
        print(f"[{label}] {len(rows)}개 채점 → 상위 {min(len(rows), top_n)}개 적립 대기")

    # 유튜브 쿼터 소진 등으로 과반 실패 시: 반쪽 데이터로 금고를 오염시키지 않고 건너뛴다
    if total_seeds and yt_failures > total_seeds / 2:
        print(f"⚠ 유튜브 수집 {yt_failures}/{total_seeds} 실패 (쿼터 소진 추정) — 오늘 적립을 건너뜁니다. "
              "쿼터는 매일 오후 4시(KST)에 리셋됩니다.")
        return []

    return all_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="외부 API·시트 없이 파이프라인 검증")
    args = parser.parse_args()

    rows = collect(dry_run=args.dry_run)

    if not rows:
        print("적립할 데이터가 없습니다 — 종료.")
        return

    if args.dry_run:
        out_path = os.path.join(HERE, "dry_run_vault.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[dry-run] 금고 적립 대신 CSV 출력: {out_path} ({len(rows)}행)")
        for r in rows[:5]:
            print(" ", r["industry"], "|", r["keyword"], "|",
                  f"화제성 {r['buzz_grade']} / 파워 {r['power_grade']}",
                  "| 명당" if r["is_sweetspot"] == "TRUE" else "")
    else:
        import sheets
        sheets.append(rows)
        print(f"금고에 {len(rows)}행 적립 완료 (append 전용)")


if __name__ == "__main__":
    main()
