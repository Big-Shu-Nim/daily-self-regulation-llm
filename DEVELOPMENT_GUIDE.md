# 🛠️ Development Guide

상세한 개발 환경 설정, 크롤러 실행, 데이터 전처리 가이드입니다.

---

## 📋 Table of Contents

- [개발 환경 설정](#개발-환경-설정)
- [로컬 인프라 실행](#로컬-인프라-실행)
- [크롤러 실행](#크롤러-실행)
- [데이터 전처리](#데이터-전처리)
- [대시보드 실행](#대시보드-실행)
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

### 1. Calendar 크롤러

Apple Calendar에서 내보낸 `.xlsx` 파일을 파싱합니다.

```bash
# 기본 경로에서 크롤링
poe crawl-calendar --first-name 'Eddie' --last-name 'Yun'

# 특정 파일 지정
poe crawl-calendar --first-name 'Eddie' --last-name 'Yun' -- --file-path '/path/to/calendar.xlsx'
```

**파일 위치**: 기본적으로 `llm_engineering/application/crawlers/data/` 디렉토리에서 `.xlsx` 파일을 찾습니다.

### 2. Notion 크롤러

Notion API를 통해 페이지와 데이터베이스를 크롤링합니다.

```bash
poe crawl-notion --first-name 'Eddie' --last-name 'Yun'
```

**사전 준비**:
1. Notion Integration 생성: https://www.notion.so/my-integrations
2. 크롤링할 페이지에 Integration 연결
3. `.env`에 `NOTION_API_KEY` 설정

### 3. Naver Blog 크롤러

네이버 블로그 포스트를 Selenium으로 크롤링합니다.

```bash
poe crawl-naver --first-name 'Eddie' --last-name 'Yun' -- --blog-id 'your_blog_id'
```

**참고**: Selenium 기반이므로 Chrome/Chromium이 설치되어 있어야 합니다.

---

## 데이터 전처리

크롤링한 Raw 데이터를 전처리하여 `CleanedCalendarDocument`로 변환합니다.

```bash
# Calendar 데이터 전처리
poe preprocess-calendar --first-name 'Eddie' --last-name 'Yun'
```

전처리 과정:
1. **카테고리 자동 분류**: 이벤트명/메모 기반 카테고리 할당
2. **Agency 매핑**: 5개 영역 (일/생산, 학습/성장, 재충전, 일상관리, Drain)
3. **태그 추출**: `#인간관계`, `#즉시만족` 등
4. **시간 정규화**: 날짜별 집계 및 지속시간 계산

---

## 대시보드 실행

### Public Dashboard (개인정보 보호)

```bash
# systemd 서비스로 실행 (추천 - 백그라운드)
sudo systemctl start streamlit-public-dashboard

# 또는 직접 실행 (포그라운드)
poe public-dashboard
```

접속: http://localhost:8502

### Daily Report (상세 정보 포함)

```bash
poe daily-report
```

접속: http://localhost:8504

### RAG Chatbot

```bash
poe chatbot
```

접속: http://localhost:8501

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

```bash
# 인프라 관리
poe local-infrastructure-up          # 로컬 인프라 시작
poe local-infrastructure-down        # 로컬 인프라 종료

# 크롤러
poe crawl-calendar                   # Calendar 크롤러
poe crawl-notion                     # Notion 크롤러
poe crawl-naver                      # Naver Blog 크롤러

# 전처리
poe preprocess-calendar              # Calendar 데이터 전처리

# 대시보드
poe public-dashboard                 # Public Dashboard (8502)
poe daily-report                     # Daily Report (8504)
poe chatbot                          # RAG Chatbot (8501)

# 피드백 생성
poe feedback-daily                   # 일일 피드백 생성
poe feedback-weekly                  # 주간 피드백 생성
poe feedback-monthly                 # 월간 피드백 생성

# RAG 쿼리
poe query                            # 단일 쿼리 실행
poe query-interactive                # 인터랙티브 쿼리 모드

# 코드 품질
poe lint-check                       # 린트 체크
poe lint-fix                         # 린트 자동 수정
poe format-check                     # 포맷 체크
poe format-fix                       # 포맷 자동 수정

# 테스트
poe test                             # 테스트 실행

# ZenML
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
- [CLAUDE.md](CLAUDE.md) - Claude Code용 컨텍스트
- [DASHBOARD_README.md](DASHBOARD_README.md) - 대시보드 상세 가이드
- [RAG Documentation](llm_engineering/application/rag/README.md) - RAG 시스템 가이드

---

**Made with ❤️ by Eddie Yun**
