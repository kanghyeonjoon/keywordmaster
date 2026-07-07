"""Claude API 채점·번역 (PRD 10절).

입력(실제 지표·질문 목록·근사 등급)만 사용해 0~100 점수와
click_reason 초벌을 산출한다. 숫자·등급을 새로 만들지 않는다.
"""
import os
import json
import re
import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
TIMEOUT = 120


def _rules() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "config", "rules.md"), encoding="utf-8") as f:
        return f.read()


SYSTEM = """너는 병원·전문직 유튜브 주제 리서치 어시스턴트다.
입력: YouTube API 실제 데이터 + 네이버 질문 목록 + 등급 근사값.

절대 규칙:
① 숫자를 생성하지 마라. 입력에 없는 검색량·조회수·통계를 새로 만들지 마라.
   주어진 값과 그 상대비교만 사용한다.
② "수요 신호 높음 + 경쟁 신호 낮음"을 우선하여 0~100으로 점수화한다.
③ 네이버 질문 목록에서 '반복되는 질문 패턴'을 추출하여
   각 키워드를 클릭이유 한 문장으로 초벌 번역한다.
   과장·효과보장·근거 없는 단정은 금지한다.
④ medical_ad_law=true 이면 '치료·완치·보장' 표현을 쓰지 말고
   '정보·관리·동행' 톤으로만 번역한다.
⑤ 두 축 등급(power_grade·buzz_grade)은 입력된 지표를 그대로 옮겨 적는다. 지어내지 마라.
⑥ keyword는 입력된 씨앗·영상 제목·질문에 실제로 등장하는 표현으로만 다듬는다.

추가 하드룰:
{rules}

출력: JSON 배열만. 설명·코드블록 금지.
[{"seed":"", "keyword":"", "demand":"높음|보통|낮음", "comp":"높음|보통|낮음",
  "score":0, "click_reason":"", "naver_questions":""}]
"""


def _extract_json(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"scorer 응답에서 JSON 배열을 찾지 못했습니다: {text[:200]}")
    return json.loads(match.group(0))


def rank_and_translate(candidates: list[dict], medical_ad_law: bool = False) -> list[dict]:
    """업종 단위로 후보들(씨앗별 지표 묶음)을 한 번에 채점한다.

    candidates 항목: seed, videos(제목·조회수 요약), demand_signal, comp_signal,
                     power_grade, buzz_grade, questions
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 없습니다.")

    payload_input = []
    for c in candidates:
        payload_input.append({
            "seed": c["seed"],
            "video_titles_and_views": [
                {"title": v["title"], "views": v["view_count"],
                 "days": v["days_since_upload"], "subs": v["subscriber_count"]}
                for v in c["videos"][:6]
            ],
            "demand_signal": c["demand_signal"],
            "comp_signal": c["comp_signal"],
            "power_grade": c["power_grade"],
            "buzz_grade": c["buzz_grade"],
            "naver_questions": c["questions"][:12],
        })

    user_msg = (
        f"medical_ad_law={'true' if medical_ad_law else 'false'}\n\n"
        f"[입력 데이터]\n{json.dumps(payload_input, ensure_ascii=False, indent=1)}\n\n"
        "각 seed마다 정확히 1개의 항목을 출력하라."
    )

    r = requests.post(
        API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 3000,
            "system": SYSTEM.replace("{rules}", _rules()),
            "messages": [{"role": "user", "content": user_msg}],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    return _extract_json(text)


def mock_rank_and_translate(candidates: list[dict], medical_ad_law: bool = False) -> list[dict]:
    """dry-run용 규칙 기반 채점 (Claude 호출 없음)."""
    out = []
    for c in candidates:
        demand_pt = {"높음": 40, "보통": 25, "낮음": 10}[c["demand_signal"]]
        comp_pt = {"낮음": 40, "보통": 25, "높음": 10}[c["comp_signal"]]
        grade_pt = {"S": 20, "A": 16, "B": 10, "C": 5, "D": 2}[c["buzz_grade"]]
        q = c["questions"][0] if c["questions"] else c["seed"]
        tone = "정보·관리 관점" if medical_ad_law else "실익 관점"
        out.append({
            "seed": c["seed"],
            "keyword": c["seed"],
            "demand": c["demand_signal"],
            "comp": c["comp_signal"],
            "score": demand_pt + comp_pt + grade_pt,
            "click_reason": f"(드라이런 초벌·{tone}) {q[:40]}",
            "naver_questions": " / ".join(c["questions"][:3]),
        })
    return out
