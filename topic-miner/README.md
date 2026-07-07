# ⛏️ 주제 채굴 자동화 시스템 (topic-miner)

병원·전문직 유튜브 주제를 **매일 자동으로 채굴**해 금고(구글 시트)에 적립하고,
**매주 월요일** 업종별 상위 5개(총 20개)를 등급·명당 표시와 함께 이메일로 배달합니다.

```
매일 06:00 KST  →  유튜브·네이버 수집 → 등급화 → Claude 채점 → 금고(시트) 적립
매주 월 07:00   →  지난 7일 중 업종별 상위 5개 × 4업종 이메일 배달
                    └ 메일 속 "▶ 이 주제로 기획안 만들기" 클릭 → 생성기 폼 자동 입력
```

**역할 경계 (PRD 원칙)**: 기계는 키워드·등급·클릭이유 *초벌*까지만.
클릭이유 확정 → 썸네일 제목 → 도입부 → 대본은 사람이 (기획안·대본 생성기로) 수행.

---

## 최초 설정 (1회, 약 30분)

### 1. YouTube Data API 키
1. [console.cloud.google.com](https://console.cloud.google.com) → 프로젝트 생성
2. "API 및 서비스" → 라이브러리 → **YouTube Data API v3** 사용 설정
3. 사용자 인증 정보 → **API 키** 생성 → 복사

### 2. 네이버 검색 API
1. [developers.naver.com](https://developers.naver.com/apps) → 애플리케이션 등록
2. 사용 API: **검색** 선택 → Client ID / Client Secret 복사

### 3. 금고 시트 + 서비스 계정
1. 구글 시트 새로 만들기 → URL 중간의 ID 복사 (`docs.google.com/spreadsheets/d/`**`이부분`**`/edit`)
2. Google Cloud 콘솔 → "API 및 서비스" → **Google Sheets API** 사용 설정
3. 사용자 인증 정보 → **서비스 계정** 생성 → 키(JSON) 다운로드
4. 시트 공유 → 서비스 계정 이메일(`...@...iam.gserviceaccount.com`)을 **편집자**로 추가

### 4. Gmail 앱 비밀번호
1. Google 계정 → 보안 → 2단계 인증 켜기
2. [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) → 앱 비밀번호 생성(16자리)

### 5. GitHub Secrets 등록
리포 → Settings → Secrets and variables → **Actions** → New repository secret:

| Secret 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 키 (sk-ant-...) |
| `YOUTUBE_API_KEY` | 1번에서 만든 키 |
| `NAVER_CLIENT_ID` | 2번 Client ID |
| `NAVER_CLIENT_SECRET` | 2번 Client Secret |
| `GOOGLE_SA_JSON` | 3번 JSON 파일 내용 전체를 붙여넣기 |
| `SHEET_ID` | 3번 시트 ID |
| `GMAIL_APP_PASSWORD` | 4번 16자리 비밀번호 |
| `DIGEST_TO` | 주간 메일 받을 주소 (예: ekrk5614@gmail.com) |

### 6. 첫 실행
Actions 탭 → **"주제 채굴 — 매일 수집"** → Run workflow (수동 실행)
→ 시트에 20행이 쌓이면 성공. 이후는 매일 06:00 자동.

---

## 운영

- **씨앗 관리**: `config/seeds.yaml` 하나만 수정하면 됩니다 (업종·씨앗 추가/변경)
- **등급 튜닝**: 첫 2주는 튜닝 기간. `src/grader.py` 상단의 임계값 표 2개만 조정
- **암 업종**: `medical_ad_law: true` → '치료·완치·보장' 표현 차단, '정보·관리·동행' 톤 강제
- **명당(is_sweetspot)**: 화제성 S/A + 콘텐츠파워 B 이하 = 검증된 소재인데 경쟁이 빈 곳

## 로컬 검증 (API 키 없이)

```bash
pip install -r topic-miner/requirements.txt
python topic-miner/src/daily_collect.py --dry-run    # → dry_run_vault.csv
python topic-miner/src/weekly_digest.py --dry-run    # → dry_run_digest.html
```

## 완료 조건 체크리스트 (PRD 13절)

- [ ] daily 1회 실행 → 시트에 20행 append
- [ ] demand/comp/등급이 실제 API 응답값 기반
- [ ] naver_questions가 실제 지식iN·카페 결과
- [ ] 숫자·등급 임의 생성 없음 (규칙 ①·⑤)
- [ ] 암 업종 '완치·보장' 미출현 (10건 수동 검수)
- [ ] is_sweetspot 로직 정상
- [ ] weekly 실행 → 업종별 5개씩 메일 도착
- [ ] 시트 append 방식 확인 (이틀치 누적)
- [ ] cron KST 환산 확인 (06:00 / 월 07:00)
