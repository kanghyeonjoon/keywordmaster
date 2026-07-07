"""Gmail 발송 (주간 배달부) — 앱 비밀번호 + smtplib."""
import os
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 기획안 생성기(폼) 주소 — GitHub Pages 활성화 후 사용
PAGES_BASE = os.environ.get(
    "PAGES_BASE_URL", "https://kanghyeonjoon.github.io/keywordmaster"
).strip()

INDUSTRY_FIELD = {
    "dental": "치과", "derma": "피부과",
    "interior": "인테리어(맞춤가구)", "cancer": "암",
}


def plan_link(row: dict) -> str:
    """주제 행 → 기획안 생성기 폼 자동 입력 링크."""
    params = {
        "topic": row.get("keyword", ""),
        "field": INDUSTRY_FIELD.get(row.get("industry", ""), row.get("industry", "")),
        "mode": "기획안만",
        "notes": f"클릭이유 초벌: {row.get('click_reason','')} / 반복질문: {row.get('naver_questions','')}"[:300],
    }
    return f"{PAGES_BASE}/script-generator.html?{urllib.parse.urlencode(params)}"


def render_digest(by_industry: dict[str, list[dict]], date_str: str, sheet_id: str = "") -> str:
    """주간 메일 HTML 렌더링 (PRD 11절 + 기획안 링크)."""
    parts = [f"<h2>📬 이번 주 명당 주제 — {date_str}</h2>"]
    for code, rows in by_industry.items():
        label = INDUSTRY_FIELD.get(code, code)
        parts.append(f"<h3>■ {label}</h3><ol>")
        for r in rows:
            spot = " <b style='color:#c0392b'>[명당]</b>" if str(r.get("is_sweetspot")).upper() == "TRUE" else ""
            ref = f" · <a href='{r['ref_url']}'>참고영상</a>" if r.get("ref_url") else ""
            parts.append(
                "<li style='margin-bottom:14px'>"
                f"<b>{r.get('keyword','')}</b>{spot}<br/>"
                f"화제성 {r.get('buzz_grade','')} / 콘텐츠파워 {r.get('power_grade','')}"
                f" · 점수 {r.get('score','')}<br/>"
                f"반복질문: {str(r.get('naver_questions',''))[:120]}<br/>"
                f"클릭이유(초벌): {r.get('click_reason','')}<br/>"
                f"<a href='{plan_link(r)}' style='color:#667eea;font-weight:700'>▶ 이 주제로 기획안 만들기</a>{ref}"
                "</li>"
            )
        parts.append("</ol>")
    if sheet_id:
        parts.append(
            f"<p><a href='https://docs.google.com/spreadsheets/d/{sheet_id}'>전체 금고·등급 보기(시트)</a></p>"
        )
    parts.append("<p style='color:#888;font-size:12px'>클릭이유 최종 확정·도입부·대본은 사람이 결정합니다. | 주제 채굴 자동화</p>")
    return "".join(parts)


def send(subject: str, html: str) -> None:
    sender = os.environ.get("GMAIL_SENDER", "ekrk5614@gmail.com").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    to = os.environ.get("DIGEST_TO", sender).strip()
    if not password:
        raise RuntimeError("GMAIL_APP_PASSWORD 환경변수가 없습니다.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, [to], msg.as_string())
