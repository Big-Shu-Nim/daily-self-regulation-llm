# 🧠 daily-self-regulation-llm

An LLM system for daily behavior analysis, reflection, and adaptive self-improvement.
일일 행동 분석, 성찰, 자기조정 피드백을 위한 LLM 시스템

# 📌 1. 프로젝트 개요 (Overview)

daily-self-regulation-llm은
개인의 하루 데이터를 기반으로 행동 개선, 집중력 분석, 조언 및 격려를 제공하는
LLM 기반 자기조정형 리포트 생성 시스템입니다.

이 시스템은 다음 세 가지 질문에 답하기 위해 설계되었습니다:

1.나는 오늘 시간을 어떻게 썼는가?

2.오늘의 행동이 주간 목표에 어떤 기여/방해를 했는가?

3.성장과 행복 사이의 균형이 잘 이루어졌는가? 

# 🪄 Motivation

2018년부터 제 일상(icalnder, naver, notion,etc)을 기록해왔어요.
그때마다 “나는 지금 내 목표를 향해 제대로 가고 있을까?”를 자주 되묻곤 했습니다.

이 프로젝트는 그 질문에 답하기 위한 시도예요.
RAG를 활용해 하루를 추적하고,
주간·월간·분기 목표와의 간격을 점검하며,
비생산적인 습관이나 컨디션 하락의 징후를 포착합니다.

유튜브나 드라마를 줄이는 게 아니라,
“언제, 얼마나, 어떤 리듬으로 즐기는 게 나에게 도움이 되는가”
그 균형을 배우고 싶습니다.

---

## 🚀 시작하기

로컬 개발 환경을 설정하고 데이터 크롤러를 실행하는 방법은 다음과 같습니다.

### 1. 개발 환경 설정

이 프로젝트는 `pyenv`를 사용하여 파이썬 버전을 관리하고, `poetry`를 사용하여 의존성을 관리합니다.

**1.1. `pyenv` 설치 및 설정:**

사용하시는 운영체제에 맞춰 공식 `pyenv` 설치 가이드를 따라 설치를 진행합니다. 설치가 완료되면, 이 프로젝트를 위한 로컬 파이썬 버전을 설정합니다.

```bash
# 필요한 파이썬 버전 설치 (이미 설치되어 있다면 생략)
pyenv install 3.11

# 현재 프로젝트 디렉토리에 로컬 파이썬 버전 설정
pyenv local 3.11
```

### 1.2. `poetry` 설치 및 의존성 해결:

`poetry`가 설치되어 있지 않다면, 공식 가이드를 따라 설치합니다. 그 후, 프로젝트 의존성을 설치합니다.

```bash
# poetry가 프로젝트 폴더 내에 가상환경을 만들도록 설정하는 것을 권장합니다.
poetry config virtualenvs.in-project true

# 의존성 설치
poetry install
```

### 1.3. `.env` 파일 설정

프로젝트를 실행하려면 루트 디렉토리에 `.env` 파일을 생성하고 필요한 환경 변수를 설정해야 합니다.

```bash
# .env 파일 예시
NOTION_API_KEY="your_notion_api_key"
DATABASE_HOST="your_mongodb_connection_string"

# 기타 필요한 API 키들
GEMINI_API_KEY="your_gemini_api_key"
OPENAI_API_KEY="your_openai_api_key"
```

- **`NOTION_API_KEY`**: Notion API에 접근하기 위한 통합 시크릿 키입니다.
- **`DATABASE_HOST`**: MongoDB 데이터베이스 연결을 위한 전체 URI입니다. (예: `mongodb+srv://...`) 클라우드 DB 사용 시 이 변수를 필수로 설정해야 합니다.

### 2. 로컬 인프라 실행

이 프로젝트는 MongoDB와 같은 로컬 인프라가 실행되어야 합니다. 아래의 `poe` 명령어를 사용하여 인프라를 시작하세요.

```bash
poe local-infrastructure-up
```
이 명령어는 Docker Compose를 사용하여 필요한 서비스들을 시작하고 ZenML 서버를 설정합니다.

### 3. 크롤러 실행하기

이제 `poe crawl-*` 명령어를 사용하여 다양한 소스로부터 데이터를 수집할 수 있습니다. 이 명령어들은 사용자의 이름(first name, last name)을 필수로 요구합니다.

**3.1. 네이버 크롤러**

네이버 블로그를 크롤링하려면 블로그 ID를 제공해야 합니다.

```bash
poe crawl-naver --first-name '이름' --last-name '성' -- --blog-id '네이버_블로그_ID'

# 예시:
poe crawl-naver --first-name 'Eddie' --last-name 'Yun' -- --blog-id 'eddieyun6'
```

**3.2. 캘린더 크롤러**

이 크롤러는 로컬 캘린더 파일(.xlsx)을 처리합니다. 기본 경로는 이미 설정되어 있습니다.

```bash
poe crawl-calendar --first-name '이름' --last-name '성'

# 예시:
poe crawl-calendar --first-name 'Eddie' --last-name 'Yun'
```

**3.3. 노션 크롤러**

이 명령어는 사용자와 연결된 노션 페이지를 크롤링합니다.

```bash
poe crawl-notion --first-name '이름' --last-name '성'

# 예시:
poe crawl-notion --first-name 'Eddie' --last-name 'Yun'
```
