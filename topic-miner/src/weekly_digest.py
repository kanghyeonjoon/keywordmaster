"""매주 월 07:00 KST 배달부 (PRD 11절).

금고에서 지난 7일 필터 → 업종별 상위 5개 → Gmail 발송.
--dry-run: 시트·메일 없이 dry_run_vault.csv를 읽어 HTML 파일로 렌더링.
"""
import argparse
import csv
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mailer  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP_N = 5
INDUSTRY_ORDER = ["dental", "derma", "interior", "cancer", "construction"]


def pick_top(rows: list[dict]) -> dict[str, list[dict]]:
    by_industry: dict[str, list[dict]] = {}
    for code in INDUSTRY_ORDER:
        candidates = [r for r in rows if r.get("industry") == code]
        candidates.sort(
            key=lambda r: (str(r.get("is_sweetspot", "")).upper() == "TRUE",
                           float(r.get("score") or 0)),
            reverse=True,
        )
        # 같은 keyword 중복 제거 후 상위 N
        seen, top = set(), []
        for r in candidates:
            if r.get("keyword") in seen:
                continue
            seen.add(r.get("keyword"))
            top.append(r)
            if len(top) >= TOP_N:
                break
        by_industry[code] = top
    return by_industry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    date_str = dt.date.today().isoformat()

    if args.dry_run:
        csv_path = os.path.join(HERE, "dry_run_vault.csv")
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        import sheets
        rows = sheets.fetch_last_days(7)

    if not rows:
        print("지난 7일 데이터가 없습니다. 메일을 보내지 않습니다.")
        return

    by_industry = pick_top(rows)
    html = mailer.render_digest(by_industry, date_str, os.environ.get("SHEET_ID", "").strip())
    subject = f"[주간 주제] 이번 주 명당 20개 — {date_str}"

    if args.dry_run:
        out_path = os.path.join(HERE, "dry_run_digest.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[dry-run] 메일 발송 대신 HTML 렌더링: {out_path}")
    else:
        mailer.send(subject, html)
        print(f"주간 메일 발송 완료: {subject}")


if __name__ == "__main__":
    main()
