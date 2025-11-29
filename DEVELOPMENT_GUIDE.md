# 🛠️ Development Guide

상세한 개발 환경 설정, 크롤러 실행, 데이터 전처리 가이드입니다.

---

## 📋 Table of Contents

- [개발 환경 설정](#개발-환경-설정)
- [로컬 인프라 실행](#로컬-인프라-실행)
- [크롤러 실행](#크롤러-실행)
  - [Google Calendar API](#1-google-calendar-크롤러-권장)
  - [Calendar (xlsx)](#2-calendar-크롤러)
  - [Notion](#3-notion-크롤러)
  - [Naver Blog](#4-naver-blog-크롤러)
- [파이프라인 시스템](#파이프라인-시스템)
- [데이터 전처리](#데이터-전처리)
- [대시보드 실행](#대시보드-실행)
- [LLM 피드백 시스템](#llm-피드백-시스템)
- [개인정보 보호 시스템](#개인정보-보호-시스템)
- [코드 품질](#코드-품질)
- [테스트](#테스트)

---

## 개발 환경 설정

### 1. Python 설치 (pyenv)

이 프로젝트는 Python 3.11을 사용합니다.

```bash
# pyenv로 Python 3.11 설치
pyenv install 3.11

# 프로젝트 디렉토리에 로컬 버전 설정
cd daily-self-regulation-llm
pyenv local 3.11
```

### 2. Poetry 설정 및 의존성 설치

```bash
# Poetry가 프로젝트 내에 가상환경을 생성하도록 설정
poetry config virtualenvs.in-project true

# 의존성 설치
poetry install
```

### 3. 환경 변수 설정 (.env)

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수들을 설정합니다:

```bash
# MongoDB 연결
DATABASE_HOST="mongodb://localhost:27017"  # 로컬 MongoDB
# 또는
DATABASE_HOST="mongodb+srv://user:pass@cluster.mongodb.net/dbname"  # 클라우드 MongoDB

# API Keys
NOTION_API_KEY="your_notion_integration_secret"
GEMINI_API_KEY="your_gemini_api_key"
OPENAI_API_KEY="your_openai_api_key"

# 사용자 정보
FIRST_NAME="Your_First_Name"
LAST_NAME="Your_Last_Name"
```

#### 환경 변수 설명

| 변수명 | 설명 | 필수 여부 |
|--------|------|-----------|
| `DATABASE_HOST` | MongoDB 연결 URI | ✅ 필수 |
| `NOTION_API_KEY` | Notion Integration Token | Notion 크롤러 사용 시 필수 |
| `GEMINI_API_KEY` | Google Gemini API Key | LLM 피드백 사용 시 필수 |
| `OPENAI_API_KEY` | OpenAI API Key | GPT 모델 사용 시 필수 |
| `FIRST_NAME` | 사용자 이름 (First Name) | ✅ 필수 |
| `LAST_NAME` | 사용자 성 (Last Name) | ✅ 필수 |

---

## 로컬 인프라 실행

MongoDB와 ZenML을 Docker Compose로 실행합니다.

```bash
# 인프라 시작
poe local-infrastructure-up

# 인프라 종료
poe local-infrastructure-down
```

실행 후 다음 서비스들이 사용 가능합니다:
- **MongoDB**: `localhost:27017`
- **ZenML Dashboard**: `http://localhost:8237`

---

## 크롤러 실행

모든 크롤러는 `--first-name`과 `--last-name` 인자를 필수로 요구합니다.

### 1. Google Calendar 크롤러 (권장)

**실시간 API 동기화, OAuth 2.0, 증분 업데이트**

#### 초기 설정

1. **Google Cloud Console 설정**
   - [Google Cloud Console](https://console.cloud.google.com/) 접속
   - 새 프로젝트 생성 또는 선택
   - "Google Calendar API" 검색 및 활성화
   - OAuth 클라이언트 ID 생성 (데스크톱 앱)
   - `credentials.json` 다운로드

2. **credentials.json 배치**
   ```bash
   # 프로젝트 루트에 배치
   daily-self-regulation-llm/
   ├── credentials.json  # Google OAuth 2.0 credentials
   └── token.json        # 자동 생성됨 (첫 인증 후)
   ```

3. **첫 실행 (인증)**
   ```bash
   poe crawl-google-calendar --first-name Eddie --last-name Yun
   # 브라우저가 자동으로 열리고 Google 계정 로그인 요청
   # 인증 후 token.json 자동 생성
   ```

#### 사용법

```bash
# 모든 캘린더 크롤링 (권장)
poe crawl-google-calendar --first-name Eddie --last-name Yun

# 특정 캘린더만 크롤링
poetry run python tools/run_crawler.py \
  --name google_calendar \
  --user-first-name Eddie \
  --user-last-name Yun \
  --calendar-id primary
```

#### 주요 기능

- ✅ **증분 동기화**: 변경된 이벤트만 효율적으로 업데이트
- ✅ **Soft Delete**: 삭제된 이벤트도 `is_deleted=True`로 히스토리 유지
- ✅ **다중 캘린더**: 모든 캘린더 자동 크롤링
- ✅ **sub_category 매핑**: Google Calendar의 "위치" 필드 → `sub_category`

```bash
# 예시 출력
✅ Fetched 10 calendars
📊 Total events collected: 88
✅ Upsert completed: matched=88, modified=5, upserted=2
🗑️  Marked 3 events as deleted
```

상세 가이드: [GOOGLE_CALENDAR_CRAWLER_README.md](GOOGLE_CALENDAR_CRAWLER_README.md)

---

### 2. Calendar 크롤러

Apple Calendar에서 내보낸 `.xlsx` 파일을 파싱합니다.

```bash
# 기본 경로에서 크롤링
poe crawl-calendar --first-name Eddie --last-name Yun

# 특정 파일 지정
poe crawl-calendar --first-name Eddie --last-name Yun -- --file-path '/path/to/calendar.xlsx'
```

**파일 위치**: 기본적으로 `llm_engineering/application/crawlers/data/` 디렉토리에서 `.xlsx` 파일을 찾습니다.

---

### 3. Notion 크롤러

Notion API를 통해 페이지와 데이터베이스를 크롤링합니다.

```bash
poe crawl-notion --first-name Eddie --last-name Yun
```

**사전 준비**:
1. Notion Integration 생성: https://www.notion.so/my-integrations
2. 크롤링할 페이지에 Integration 연결
3. `.env`에 `NOTION_API_KEY` 설정

---

### 4. Naver Blog 크롤러

네이버 블로그 포스트를 Selenium으로 크롤링합니다.

```bash
poe crawl-naver --first-name Eddie --last-name Yun -- --blog-id 'your_blog_id'
```

**참고**:
- Selenium 기반이므로 Chrome/Chromium이 설치되어 있어야 합니다.
- 현재 비활성화 상태 (파이프라인에서 제외됨)

---

## 파이프라인 시스템

크롤링부터 전처리, 임베딩까지 통합 실행하는 파이프라인입니다.

### 통합 파이프라인 (권장)

#### ETL 파이프라인 (크롤링 + 전처리)

```bash
poe pipeline-etl --first-name Eddie --last-name Yun

# 내부 동작
# 1. Google Calendar 크롤링
# 2. Calendar (xlsx) 크롤링
# 3. Notion 크롤링
# 4. 증분 전처리 (변경된 문서만)
```

#### End-to-End 파이프라인 (크롤링 + 전처리 + 임베딩)

```bash
poe pipeline-end-to-end --first-name Eddie --last-name Yun

# 내부 동작
# 1. ETL 파이프라인 (위와 동일)
# 2. Qdrant 임베딩 생성
# 3. 벡터 DB 저장
```

### 개별 스텝 실행

```bash
# 전처리만
poe pipeline-preprocessing

# 임베딩만
poe pipeline-embedding --source calendar

# 커스텀 옵션 (특정 크롤러 건너뛰기)
poe run-pipeline --run-etl \
  --first-name Eddie \
  --last-name Yun \
  --skip-notion
```

### 파이프라인 구조

```
pipelines/
└── data_pipeline.py          # ETL + End-to-End 정의

steps/
├── etl/
│   └── crawl.py              # 크롤링 스텝
├── preprocessing/
│   └── preprocess.py         # 전처리 스텝
└── embedding/
    └── embed.py              # 임베딩 스텝

tools/
└── run.py                    # 통합 CLI 실행기
```

---

## 데이터 전처리

크롤링한 Raw 데이터를 전처리하여 `CleanedCalendarDocument`로 변환합니다.

### 증분 전처리 (기본)

```bash
# 변경된 문서만 전처리
poe preprocess

# 전처리 후 MongoDB에 저장
poe preprocess-save
```

### 전체 전처리

```bash
# 모든 문서 전처리 (저장 안함)
poe preprocess-full

# 모든 문서 전처리 후 저장
poe preprocess-full-save
```

### 전처리 과정

1. **카테고리 자동 분류**: 이벤트명/메모 기반 카테고리 할당
2. **Agency 모드 매핑**: 5개 영역
   - **Creator**: 일/생산 (프로젝트, 개발, 업무)
   - **Learner**: 학습/성장 (논문, 튜토리얼, 연습)
   - **Recharger**: 수면, 휴식/회복, 운동
   - **Maintainer**: 유지/정리, daily/chore (식사, 청소, 행정)
   - **Drain**: 충동루프, 즉각 만족 활동 (유튜브, 무계획 음주 등)
3. **태그 추출**: `#인간관계`, `#즉시만족` 등 특수 태그 감지
4. **시간 정규화**: 날짜별 집계 및 지속시간 계산
5. **중복 제거**: 동일 이벤트 자동 필터링

---

## 대시보드 실행

시스템은 3가지 대시보드를 제공합니다. 각각 다른 용도에 최적화되어 있습니다.

### 1. Public Dashboard (공개용)

**개인정보 보호 최우선**

```bash
# systemd 서비스로 실행 (추천 - 백그라운드)
sudo systemctl start streamlit-public-dashboard

# 또는 직접 실행 (포그라운드)
poe public-dashboard
```

**접속**: http://localhost:8502

**주요 기능**:
- ✅ 자동 개인정보 필터링 및 마스킹
- ✅ 최근 7일 데이터만 표시
- ✅ #인간관계, 민감 정보 자동 마스킹
- ✅ 일/생산, 학습/성장 카테고리만 상세 공개

---

### 2. Experiment Dashboard (실험용)

**LLM 모델 테스트 및 비교**

```bash
poe experiment-dashboard
```

**접속**: http://localhost:8503

**주요 기능**:
- ✅ **17종 LLM 모델** 테스트 (GPT-5, Gemini 2.5 등)
- ✅ **6가지 프롬프트 스타일** (original, minimal, coach, scientist, cbt, v2)
- ✅ **성능 메트릭 추적** (토큰, 시간, 비용)
- ✅ **프라이버시 필터 토글** (on/off 전환)
- ✅ **일별/주간 피드백** 타입 선택

**사용 흐름**:
1. 날짜 선택
2. 리포트 타입 선택 (일별/주간)
3. LLM 모델 선택
4. 프롬프트 스타일 선택
5. 프라이버시 필터 on/off
6. "Generate Feedback" 버튼 클릭
7. 성능 메트릭 확인

---

### 3. Daily Report (개인용)

**전체 데이터 접근 및 상세 분석**

```bash
poe daily-report
```

**접속**: http://localhost:8504

**주요 기능**:
- ✅ 필터링 없이 모든 정보 표시
- ✅ 일별 상세 분석 (이벤트별 메모, 태그)
- ✅ 전체 기간 데이터 조회 가능

---

### RAG Chatbot

**대화형 데이터 쿼리 인터페이스**

```bash
poe chatbot
```

**접속**: http://localhost:8501

**주요 기능**:
- 자연어로 데이터 질문
- Hybrid Search (Vector + BM25)
- 컨텍스트 기반 검색

---

## LLM 피드백 시스템

일별/주간/월간 피드백을 LLM을 통해 자동 생성합니다.

### 일별/주간/월간 피드백 생성

```bash
# 일별 피드백
poe feedback-daily --date 2025-11-20

# 주간 피드백
poe feedback-weekly --start-date 2025-11-14

# 월간 피드백
poe feedback-monthly --year 2025 --month 11
```

### 주간 피드백 V2 프롬프트

**특징**:
- 사전 계산된 메트릭 활용 (LLM 연산 감소)
- 패턴 분석에 집중
- JSON 중괄호 충돌 방지
- 주차별 대표 태그 5~7개 추출

**사전 계산 메트릭**:
```python
{
  "hours": {
    "categories": {...},  # 카테고리별 시간
    "modes": {...}        # Agency 모드별 시간
  },
  "sleep": {...},         # 수면 통계
  "drain": {...},         # Drain 지표
  "daily_breakdown": {...},  # 일별 분석
  "recovery_ratio": 1.5   # 회복/Drain 비율
}
```

### 피드백 내용 구성

**주간 피드백**:
- 📊 핵심 지표 (Agency 모드, 수면, Drain 등)
- ✅ 정성 성과 (3개)
- 🔁 반복 패턴 (성공/실패/요일/캐리오버)
- 💬 숨은 동기 (정서적 욕구)
- 🧪 다음 주 실험 제안 (2~4개)
- 🏷 태그 (5~7개)

---

## 개인정보 보호 시스템

데이터 분석의 가치를 유지하면서 개인정보를 안전하게 보호합니다.

### 주요 기능

1. **자동 중복 제거** (모든 대시보드 적용)
2. **설정 기반 마스킹** (`privacy_filter_config.json`)
3. **카테고리별 자동 필터링** (Public 대시보드)
4. **이벤트 익명화** (#인간관계 → "인간관계 활동")

### 설정 방법

```bash
# 1. 설정 파일 생성
poetry run python tools/create_privacy_config.py

# 2. privacy_filter_config.json 편집
{
  "masked_events": [
    {
      "event_name": "프로젝트 작업",
      "start_time": "22:15",
      "date": "2025-11-05"
    }
  ],
  "masked_subcategories": ["이직준비", "이사준비", "재무관리"]
}

# 3. 대시보드 새로고침 (자동 적용)
```

### 필터 적용 범위

| 대시보드 | 중복 제거 | 메모 마스킹 | 카테고리 필터링 |
|---------|----------|-----------|----------------|
| Daily Report | ✅ | ❌ | ❌ |
| Experiment | ✅ | ⚙️ (토글) | ❌ |
| Public | ✅ | ✅ | ✅ |

### 마스킹 규칙

**이벤트명 + 시간 기반**:
```json
{
  "event_name": "개인 미팅",
  "start_time": "14:30",  // 선택
  "date": "2025-11-05"    // 선택
}
```

**서브카테고리 기반** (일/생산 카테고리만):
```json
{
  "masked_subcategories": ["이직준비", "재무관리"]
}
```

상세 가이드: [PRIVACY_FILTER_README.md](PRIVACY_FILTER_README.md)

---

## 코드 품질

### Linting

```bash
# 린트 체크
poe lint-check

# 자동 수정
poe lint-fix
```

### Formatting

```bash
# 포맷 체크
poe format-check

# 자동 포맷팅
poe format-fix
```

---

## 테스트

```bash
# 모든 테스트 실행 (.env.testing 사용)
poe test

# 특정 테스트 파일 실행
poetry run pytest tests/test_specific.py

# 커버리지와 함께 실행
poetry run pytest --cov=llm_engineering tests/
```

---

## Poetry 명령어 (poe) 전체 목록

### 인프라 관리
```bash
poe local-infrastructure-up          # 로컬 인프라 시작 (MongoDB + ZenML)
poe local-infrastructure-down        # 로컬 인프라 종료
```

### 크롤러
```bash
poe crawl-google-calendar            # Google Calendar 크롤러 (권장)
poe crawl-calendar                   # Calendar (.xlsx) 크롤러
poe crawl-notion                     # Notion 크롤러
poe crawl-naver                      # Naver Blog 크롤러 (비활성화)
```

### 파이프라인 (권장)
```bash
poe pipeline-etl                     # ETL 파이프라인 (크롤링 + 전처리)
poe pipeline-end-to-end              # End-to-End 파이프라인 (크롤링 + 전처리 + 임베딩)
poe pipeline-preprocessing           # 전처리만
poe pipeline-embedding               # 임베딩만
poe run-pipeline                     # 커스텀 파이프라인
```

### 전처리
```bash
poe preprocess                       # 증분 전처리 (변경분만)
poe preprocess-save                  # 증분 전처리 + 저장
poe preprocess-full                  # 전체 전처리
poe preprocess-full-save             # 전체 전처리 + 저장
```

### 대시보드
```bash
poe public-dashboard                 # Public Dashboard (8502)
poe experiment-dashboard             # Experiment Dashboard (8503)
poe daily-report                     # Daily Report (8504)
poe chatbot                          # RAG Chatbot (8501)
```

### LLM 피드백
```bash
poe feedback-daily                   # 일별 피드백
poe feedback-weekly                  # 주간 피드백
poe feedback-monthly                 # 월간 피드백
```

### RAG 쿼리
```bash
poe query                            # 단일 쿼리 실행
poe query-interactive                # 인터랙티브 쿼리 모드
```

### 코드 품질
```bash
poe lint-check                       # 린트 체크
poe lint-fix                         # 린트 자동 수정
poe format-check                     # 포맷 체크
poe format-fix                       # 포맷 자동 수정
```

### 테스트
```bash
poe test                             # 테스트 실행 (.env.testing 사용)
```

### ZenML
```bash
poe export-settings-to-zenml         # 환경 변수를 ZenML Secret Store로 내보내기
```

---

## 프로젝트 구조

```
daily-self-regulation-llm/
├── llm_engineering/
│   ├── domain/                      # 도메인 모델 (Documents)
│   │   ├── documents.py             # Raw 문서 모델
│   │   ├── cleaned_documents.py     # 전처리된 문서 모델
│   │   └── feedback_documents.py    # 피드백 문서 모델
│   ├── application/
│   │   ├── crawlers/                # 데이터 수집
│   │   │   ├── calendar.py
│   │   │   ├── notion.py
│   │   │   └── naver.py
│   │   ├── preprocessing/           # 데이터 전처리
│   │   │   └── calendar_preprocessor.py
│   │   ├── visualization/           # Streamlit 대시보드
│   │   │   ├── streamlit_public_dashboard.py
│   │   │   └── streamlit_daily_report.py
│   │   └── rag/                     # RAG 시스템
│   │       ├── retriever.py
│   │       ├── pipeline.py
│   │       └── streamlit_app.py
│   ├── infrastructure/              # 인프라 (DB 연결)
│   │   └── db/
│   │       ├── mongo.py
│   │       └── qdrant.py
│   └── settings.py                  # 환경 변수 설정
├── tools/                           # CLI 진입점
│   ├── run_crawler.py
│   ├── run_preprocessing.py
│   └── run_rag_query.py
├── tests/                           # 테스트
├── pyproject.toml                   # Poetry 설정 (poe 명령어)
├── .env                             # 환경 변수 (git 제외)
└── README.md                        # 프로젝트 개요
```

---

## 트러블슈팅

### MongoDB 연결 실패
```bash
# MongoDB가 실행 중인지 확인
docker ps | grep mongo

# 로컬 인프라 재시작
poe local-infrastructure-down
poe local-infrastructure-up
```

### Poetry 가상환경 문제
```bash
# 가상환경 재생성
poetry env remove python
poetry install
```

### Streamlit 포트 충돌
```bash
# 기존 프로세스 종료
pkill -f streamlit

# 또는 특정 포트의 프로세스만 종료
kill $(lsof -ti:8502)
```

---

## 추가 문서

- [README.md](README.md) - 프로젝트 개요 및 파이프라인

- [DASHBOARD_README.md](DASHBOARD_README.md) - 대시보드 상세 가이드



**Made with ❤️ by Eddie Yun**
