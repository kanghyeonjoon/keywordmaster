"""Google Sheets(금고) 읽기/쓰기 — append 전용, 절대 덮어쓰지 않는다 (PRD 7절)."""
import os
import json

COLUMNS = [
    "date", "industry", "seed", "keyword", "demand", "comp",
    "power_grade", "buzz_grade", "is_sweetspot", "naver_questions",
    "score", "click_reason", "ref_url",
]
WORKSHEET = "vault"


def _client():
    import gspread
    from google.oauth2.service_account import Credentials

    sa_json = os.environ.get("GOOGLE_SA_JSON", "").strip()
    if not sa_json:
        raise RuntimeError("GOOGLE_SA_JSON 환경변수가 없습니다.")
    creds = Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(creds)


def _worksheet():
    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("SHEET_ID 환경변수가 없습니다.")
    book = _client().open_by_key(sheet_id)
    try:
        ws = book.worksheet(WORKSHEET)
    except Exception:
        ws = book.add_worksheet(title=WORKSHEET, rows=1000, cols=len(COLUMNS))
        ws.append_row(COLUMNS)
    if not ws.row_values(1):
        ws.append_row(COLUMNS)
    return ws


def append(rows: list[dict]) -> None:
    """행 추가만 한다. 기존 데이터는 절대 수정·삭제하지 않는다."""
    ws = _worksheet()
    values = [[str(r.get(c, "")) for c in COLUMNS] for r in rows]
    ws.append_rows(values, value_input_option="RAW")


def fetch_last_days(days: int = 7) -> list[dict]:
    """date 컬럼 기준 최근 N일 행을 반환 (주간 배달용)."""
    import datetime as dt

    ws = _worksheet()
    records = ws.get_all_records()
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    return [r for r in records if str(r.get("date", "")) >= cutoff]
