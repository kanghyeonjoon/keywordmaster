"""두 축 등급 근사 (PRD 9절).

공개 지표(조회수·업로드 경과일·구독자수)만으로 근사 등급을 낸다.
임계값은 초기 하드코딩이며, 운영 첫 2주 실측값으로 튜닝한다 (PRD 12·14절).
"""

# ── 튜닝 포인트: 운영 데이터를 보고 이 두 표만 조정한다 ─────────────
POWER_THRESHOLDS = [  # 검색결과 상위 영상들의 "누적 총 조회수 합" 기준
    ("S", 3_000_000),
    ("A", 1_000_000),
    ("B", 300_000),
    ("C", 50_000),
]  # 미만이면 "D"

BUZZ_THRESHOLDS = [  # 속도(조회/일) × 파급력(조회/구독자) 상위 영상 평균 기준
    ("S", 3_000),
    ("A", 800),
    ("B", 150),
    ("C", 20),
]  # 미만이면 "D"
# ─────────────────────────────────────────────────────────────────


def _bucket(value: float, thresholds: list[tuple[str, float]]) -> str:
    for grade, cut in thresholds:
        if value >= cut:
            return grade
    return "D"


def grade(videos: list[dict]) -> dict:
    """검색결과 영상 묶음에서 power/buzz 등급과 근거 수치를 계산."""
    if not videos:
        return {"power_grade": "D", "buzz_grade": "D",
                "total_views": 0, "buzz_score": 0.0, "top_video": None}

    total_views = sum(v["view_count"] for v in videos)

    buzz_scores = []
    for v in videos:
        velocity = v["view_count"] / max(v["days_since_upload"], 1)      # 속도
        reach = v["view_count"] / max(v["subscriber_count"], 100)        # 파급력
        buzz_scores.append(velocity * reach)
    buzz_scores.sort(reverse=True)
    top3_avg = sum(buzz_scores[:3]) / min(len(buzz_scores), 3)

    top_video = max(videos, key=lambda v: v["view_count"])
    return {
        "power_grade": _bucket(total_views, POWER_THRESHOLDS),
        "buzz_grade": _bucket(top3_avg, BUZZ_THRESHOLDS),
        "total_views": total_views,
        "buzz_score": round(top3_avg, 1),
        "top_video": top_video,
    }


def is_sweetspot(power_grade: str, buzz_grade: str) -> bool:
    """명당: 화제성 검증(S/A) + 콘텐츠파워 약함(B 이하) → 빈틈."""
    return buzz_grade in ("S", "A") and power_grade in ("B", "C", "D")
