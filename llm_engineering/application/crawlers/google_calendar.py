"""
Google Calendar API Crawler

Google Calendar API를 사용하여 캘린더 이벤트를 실시간으로 크롤링합니다.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from loguru import logger
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from pathlib import Path

from llm_engineering.domain.base.nosql import _database
from llm_engineering.domain.documents import GoogleCalendarDocument, UserDocument
from .base import BaseCrawler


class GoogleCalendarCrawler(BaseCrawler):
    """
    Google Calendar API를 사용한 캘린더 이벤트 크롤러.

    - OAuth 2.0 인증 사용
    - 실시간 API 호출로 이벤트 가져오기
    - 중복 체크 및 bulk insert
    """

    model = GoogleCalendarDocument

    # Google Calendar API 스코프 (읽기 전용)
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    def __init__(self, credentials_file: str = 'credentials.json', token_file: str = 'token.json'):
        """
        Args:
            credentials_file: Google Cloud Console에서 다운로드한 OAuth 2.0 credentials 파일
            token_file: 인증 토큰 저장 파일 (자동 생성)
        """
        # 절대 경로로 변환 (프로젝트 루트 기준)
        project_root = Path(__file__).parents[3]

        # 상대 경로면 프로젝트 루트 기준으로 변환
        if not os.path.isabs(credentials_file):
            self.credentials_file = str(project_root / credentials_file)
        else:
            self.credentials_file = credentials_file

        if not os.path.isabs(token_file):
            self.token_file = str(project_root / token_file)
        else:
            self.token_file = token_file

        self.service = None

    def _authenticate(self) -> None:
        """Google Calendar API 인증"""
        creds = None

        # 기존 토큰 파일이 있으면 로드
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)

        # 토큰이 없거나 유효하지 않으면 재인증
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}. Re-authenticating...")
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_file}\n"
                        "Please download OAuth 2.0 credentials from Google Cloud Console"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES
                )
                # 서버 환경: 브라우저 자동 열기 비활성화
                logger.info("Starting OAuth authentication...")
                logger.info("=" * 80)
                logger.info("Please open the following URL in your browser:")
                logger.info("(The authorization URL will be displayed below)")
                logger.info("=" * 80)
                creds = flow.run_local_server(port=8080, open_browser=False)

            # 토큰 저장
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())

        # Google Calendar API 서비스 생성
        self.service = build('calendar', 'v3', credentials=creds)
        logger.info("✅ Google Calendar API authentication successful")

    def _parse_datetime(self, event_time: dict) -> datetime:
        """
        Google Calendar API의 datetime 또는 date 형식을 파싱하여 한국 시간(Asia/Seoul) 기준 naive datetime 반환

        Args:
            event_time: {'dateTime': 'ISO 8601', 'timeZone': ...} 또는 {'date': 'YYYY-MM-DD'}

        Returns:
            한국 시간 기준 naive datetime 객체
        """
        if 'dateTime' in event_time:
            # ISO 8601 형식: 2024-11-14T10:00:00+09:00
            dt_aware = datetime.fromisoformat(event_time['dateTime'])

            # 한국 시간(Asia/Seoul)으로 변환
            korea_tz = ZoneInfo("Asia/Seoul")
            dt_korea = dt_aware.astimezone(korea_tz)

            # Naive datetime으로 변환 (timezone 정보 제거, 한국 시간 유지)
            return dt_korea.replace(tzinfo=None)
        elif 'date' in event_time:
            # 종일 이벤트: 2024-11-14 (이미 날짜만 있으므로 한국 시간 기준으로 해석)
            return datetime.strptime(event_time['date'], '%Y-%m-%d')
        else:
            raise ValueError(f"Invalid event time format: {event_time}")

    def _calculate_duration_minutes(self, start: datetime, end: datetime) -> int:
        """이벤트 지속 시간 계산 (분 단위)"""
        delta = end - start
        return int(delta.total_seconds() / 60)

    def _mark_deleted_events(
        self,
        user: 'UserDocument',
        fetched_event_ids: set[str],
        time_min: datetime = None,
        time_max: datetime = None
    ) -> int:
        """
        Google Calendar API에서 조회되지 않은 이벤트를 soft delete 처리

        Args:
            user: UserDocument
            fetched_event_ids: API에서 조회된 이벤트 ID 집합
            time_min: 조회한 시간 범위 시작
            time_max: 조회한 시간 범위 종료

        Returns:
            soft delete 처리된 이벤트 수
        """
        collection = _database[self.model.get_collection_name()]

        # 조회 범위 내에서 DB에는 있지만 API에서 조회되지 않은 이벤트 찾기
        query = {
            "author_id": str(user.id),
            "is_deleted": False
        }

        # 시간 범위가 지정된 경우 해당 범위만 확인
        if time_min and time_max:
            query["start_datetime"] = {
                "$gte": time_min,
                "$lte": time_max
            }

        # DB의 기존 이벤트 조회
        existing_events = list(collection.find(query))

        # 삭제된 이벤트 찾기
        events_to_delete = []
        for event in existing_events:
            if event.get("google_event_id") not in fetched_event_ids:
                events_to_delete.append(event.get("google_event_id"))

        # Soft delete 수행
        if events_to_delete:
            result = collection.update_many(
                {"google_event_id": {"$in": events_to_delete}},
                {"$set": {"is_deleted": True, "last_synced_at": datetime.now()}}
            )
            logger.info(f"🗑️  Marked {result.modified_count} events as deleted")
            return result.modified_count
        else:
            logger.info("No events to mark as deleted")
            return 0

    def _fetch_calendar_list(self) -> list[dict]:
        """
        사용자의 모든 캘린더 목록 가져오기

        Returns:
            캘린더 리스트 (id, summary 포함)
        """
        if not self.service:
            self._authenticate()

        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])

            logger.info(f"✅ Fetched {len(calendars)} calendars")
            for calendar in calendars:
                logger.info(f"  - {calendar.get('summary')} (ID: {calendar.get('id')})")

            return calendars

        except HttpError as error:
            logger.error(f"Google Calendar API error while fetching calendar list: {error}")
            return []

    def _fetch_events(
        self,
        calendar_id: str = 'primary',
        time_min: datetime = None,
        time_max: datetime = None,
        max_results: int = 2500
    ) -> list[dict]:
        """
        Google Calendar API에서 이벤트 가져오기

        Args:
            calendar_id: 캘린더 ID ('primary' = 기본 캘린더)
            time_min: 조회 시작 시간 (기본: 30일 전)
            time_max: 조회 종료 시간 (기본: 오늘)
            max_results: 최대 결과 수

        Returns:
            이벤트 리스트
        """
        if not self.service:
            self._authenticate()

        # 기본값: 최근 30일
        if time_min is None:
            time_min = datetime.now() - timedelta(days=30)
        if time_max is None:
            time_max = datetime.now()

        # RFC 3339 형식으로 변환 (naive datetime을 UTC로 가정)
        # Google Calendar API는 'Z' suffix를 제대로 처리하려면 시간에 밀리초가 없어야 함
        time_min_str = time_min.replace(microsecond=0).isoformat() + 'Z'
        time_max_str = time_max.replace(microsecond=0).isoformat() + 'Z'

        logger.info(f"Fetching events from {calendar_id} ({time_min.date()} ~ {time_max.date()})")
        logger.debug(f"API request: timeMin={time_min_str}, timeMax={time_max_str}, maxResults={max_results}")

        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,  # 반복 이벤트를 개별 인스턴스로 펼침
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            logger.info(f"✅ Fetched {len(events)} events from Google Calendar")

            # 디버깅: 첫 3개 이벤트의 요약 출력
            if events:
                logger.debug(f"Sample events (first 3):")
                for i, event in enumerate(events[:3]):
                    location = event.get('location', 'No Location')
                    logger.debug(f"  {i+1}. {event.get('summary', 'No Title')} - {event.get('start')} - Location: {location}")

            return events

        except HttpError as error:
            logger.error(f"Google Calendar API error: {error}")
            return []

    def extract(self, user: UserDocument, **kwargs) -> None:
        """
        Google Calendar API를 사용하여 모든 캘린더의 이벤트를 크롤링하고 DB에 저장

        Args:
            user: UserDocument (author)
            **kwargs:
                - calendar_id: str (특정 캘린더만 크롤링, 기본: None = 모든 캘린더)
                - time_min: datetime (기본: 30일 전)
                - time_max: datetime (기본: 오늘)
                - max_results: int (기본: 2500)
        """
        specific_calendar_id = kwargs.get('calendar_id', None)
        time_min = kwargs.get('time_min', None)
        time_max = kwargs.get('time_max', None)
        max_results = kwargs.get('max_results', 2500)

        # Google Calendar API 인증
        self._authenticate()

        # 캘린더 목록 가져오기
        if specific_calendar_id:
            # 특정 캘린더만 크롤링
            calendars_to_crawl = [{'id': specific_calendar_id, 'summary': specific_calendar_id}]
            logger.info(f"Crawling specific calendar: {specific_calendar_id}")
        else:
            # 모든 캘린더 크롤링
            calendars_to_crawl = self._fetch_calendar_list()
            if not calendars_to_crawl:
                logger.warning("No calendars found")
                return
            logger.info(f"Crawling all {len(calendars_to_crawl)} calendars")

        # 모든 캘린더에서 이벤트 수집
        all_events = []
        for calendar in calendars_to_crawl:
            calendar_id = calendar.get('id')
            calendar_name = calendar.get('summary', calendar_id)

            logger.info(f"📅 Fetching events from calendar: {calendar_name}")

            events = self._fetch_events(
                calendar_id=calendar_id,
                time_min=time_min,
                time_max=time_max,
                max_results=max_results
            )

            # 각 이벤트에 캘린더 정보 추가
            for event in events:
                event['_calendar_name'] = calendar_name
                event['_calendar_id'] = calendar_id

            all_events.extend(events)

        if not all_events:
            logger.warning("No events found across all calendars")
            return

        logger.info(f"📊 Total events collected from all calendars: {len(all_events)}")

        # 현재 시점 기록 (동기화 타임스탬프)
        sync_time = datetime.now()

        # API에서 가져온 이벤트 ID 집합 (삭제 감지용)
        fetched_event_ids = set()

        # Upsert할 문서 리스트 (신규 + 수정)
        documents_to_upsert = []

        for event in all_events:
            # 필수 필드 확인
            if 'start' not in event or 'end' not in event:
                logger.warning(f"Skipping event without start/end time: {event.get('id')}")
                continue

            try:
                # 시간 파싱
                start_datetime = self._parse_datetime(event['start'])
                end_datetime = self._parse_datetime(event['end'])
                duration_minutes = self._calculate_duration_minutes(start_datetime, end_datetime)

                # 제목 및 메모 추출
                title = event.get('summary', 'No Title')
                notes = event.get('description', '')

                # 캘린더명 (크롤링 시 추가한 정보 사용)
                calendar_name = event.get('_calendar_name', event.get('organizer', {}).get('displayName', 'Google Calendar'))
                calendar_id = event.get('_calendar_id', 'primary')

                # location을 sub_category로 매핑
                sub_category = event.get('location', None)

                # Google Event ID 기록 (삭제 감지용)
                fetched_event_ids.add(event['id'])

                # GoogleCalendarDocument 생성
                doc = self.model(
                    content={"title": title, "notes": notes},
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    calendar_name=calendar_name,
                    sub_category=sub_category,  # location 필드를 sub_category로 사용
                    duration_minutes=duration_minutes,
                    google_event_id=event['id'],
                    google_calendar_id=calendar_id,
                    author_id=user.id,
                    author_full_name=user.full_name,
                    last_synced_at=sync_time,
                    is_deleted=False
                )

                documents_to_upsert.append(doc)

            except Exception as e:
                logger.error(f"Failed to process event {event.get('id')}: {e}")
                continue

        # Bulk upsert (신규 삽입 + 기존 업데이트)
        if documents_to_upsert:
            logger.info(f"Upserting {len(documents_to_upsert)} events to database")
            result = self.model.bulk_upsert(documents_to_upsert, match_field="google_event_id")
            logger.info(
                f"✅ Upsert completed: "
                f"matched={result['matched']}, "
                f"modified={result['modified']}, "
                f"upserted={result['upserted']}"
            )
        else:
            logger.info("No events to upsert")

        # 삭제된 이벤트 감지 및 soft delete 처리
        self._mark_deleted_events(user, fetched_event_ids, time_min, time_max)
