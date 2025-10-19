
import os
import glob
import hashlib
from datetime import datetime
import pandas as pd
from loguru import logger

from llm_engineering.domain.base.nosql import _database
# ProcessedFileDocument를 import 합니다.
from llm_engineering.domain.documents import CalendarDocument, UserDocument, ProcessedFileDocument
from .base import BaseCrawler


class CalendarCrawler(BaseCrawler):
    """
    A robust ETL pipeline for calendar data.
    Scans a directory for .xlsx files, processes only new or modified files,
    and bulk-inserts new events.
    """
    model = CalendarDocument

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculates the SHA256 hash of a file's content."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _is_file_processed(self, file_path: str, file_hash: str) -> bool:
        """Checks if the file with the same path and hash has been processed."""
        existing_record = ProcessedFileDocument.find(file_path=file_path, file_hash=file_hash)
        return existing_record is not None

    def _process_single_file(self, file_path: str, user: UserDocument) -> bool:
        """Contains the logic to process one Excel file."""
        logger.info(f"Processing file: {file_path}")
        try:
            # (이전의 단일 파일 처리 로직과 거의 동일)
            column_mapping = {
                "Event Title": "title",
                "Notes": "notes",
                "Start Date/Time": "start_datetime",
                "End Date/Time": "end_datetime",
                "Category": "calendar_name",
                "Duration (Minutes)": "duration_minutes",
                "URL": "url",  # This column is read but not currently saved to the database.
            }
            df = pd.read_excel(file_path)
            df.columns = df.columns.str.strip()  # Strip whitespace from column names
            df = df[list(column_mapping.keys())]
            df.rename(columns=column_mapping, inplace=True)
            df = df.where(pd.notna(df), None)
        except Exception as e:
            logger.error(f"Failed to read or preprocess file {file_path}: {e}")
            return False

        if df.empty:
            logger.warning(f"File {file_path} is empty. Skipping.")
            return True # 비어있는 것도 성공으로 처리

        # 이벤트 단위 중복 체크 로직
        filter_options = [{"content.title": row.get("title"), "start_datetime": row.get("start_datetime")} for _, row in df.iterrows()]
        collection = _database[self.model.get_collection_name()]
        existing_docs = list(collection.find({"$or": filter_options}))
        existing_events_set = {(doc.get("content", {}).get("title"), doc.get("start_datetime")) for doc in existing_docs}

        documents_to_insert = []
        for index, row in df.iterrows():
            event_key = (row.get("title"), row.get("start_datetime"))
            if event_key not in existing_events_set:
                try:
                    documents_to_insert.append(self.model(
                        content={"title": row.get("title"), "notes": row.get("notes")},
                        start_datetime=row.get("start_datetime"), end_datetime=row.get("end_datetime"),
                        calendar_name=row.get("calendar_name"), duration_minutes=row.get("duration_minutes"),
                        author_id=user.id, author_full_name=user.full_name
                    ))
                except Exception as e:
                    logger.error(f"Failed to validate data in row {index + 2} of {file_path}: {e}")

        if documents_to_insert:
            logger.info(f"Found {len(documents_to_insert)} new events in {file_path}.")
            if not self.model.bulk_insert(documents_to_insert):
                logger.error(f"Bulk insert failed for file {file_path}.")
                return False
        else:
            logger.info(f"No new events to insert from {file_path}.")
            
        return True

    def extract(self, directory_path: str, **kwargs) -> None:
        """
        Extracts calendar data by scanning all .xlsx files in a directory.
        """
        user = kwargs.get("user")
        if not user or not isinstance(user, UserDocument):
            logger.error("A valid UserDocument object must be provided.")
            return

        logger.info(f"Starting directory scan for calendar files in: {directory_path}")
        
        # 1. 디렉토리 내 모든 .xlsx 파일 탐색
        excel_files = glob.glob(os.path.join(directory_path, "*.xlsx"))
        
        if not excel_files:
            logger.warning(f"No .xlsx files found in directory: {directory_path}")
            return

        logger.info(f"Found {len(excel_files)} Excel files to check.")
        
        for file_path in excel_files:
            try:
                # 2. 파일 해시 계산 및 처리 여부 확인
                file_hash = self._calculate_file_hash(file_path)
                if self._is_file_processed(file_path, file_hash):
                    logger.info(f"Skipping already processed file (identical content): {os.path.basename(file_path)}")
                    continue

                # 3. 단일 파일 처리 로직 호출
                success = self._process_single_file(file_path, user)

                # 4. 성공 시 처리 기록 남기기
                if success:
                    ProcessedFileDocument(file_path=file_path, file_hash=file_hash).save()
                    logger.success(f"Successfully processed and logged: {os.path.basename(file_path)}")
                else:
                    logger.error(f"Failed to process: {os.path.basename(file_path)}")

            except Exception as e:
                logger.exception(f"An unexpected error occurred while handling {file_path}: {e}")
            
            






def fetch_and_save_calendar_events_bulk(file_path: str):
    """
    Reads calendar events, renames columns to match the model,
    checks for duplicates, and saves new events in bulk.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    try:
        # 1. 컬럼 이름 매핑 정의
        column_mapping = {
            "Start Date/Time (SQL Timestamp)": "start_datetime",
            "End Date/Time (SQL Timestamp)": "end_datetime",
            "Calendar Name": "calendar_name",
            "Event Title": "event_title",
            "Duration (Minutes)": "duration_minutes",
            "Event Notes": "event_notes",
        }
        
        df = pd.read_excel(file_path)

        # 2. 필요한 컬럼만 선택
        df = df[list(column_mapping.keys())]
        
        # 3. 선택된 컬럼들의 이름을 짧은 이름으로 변경
        df.rename(columns=column_mapping, inplace=True)
        
        # 4. NaN 값을 None으로 변환
        df = df.where(pd.notna(df), None)

    except Exception as e:
        logger.exception(f"Failed to read or process Excel file: {e}")
        return

    if df.empty:
        logger.info("Excel file is empty.")
        return

    # 이제부터는 코드 전체에서 짧은 이름만 사용합니다.
    filter_options = []
    for _, row in df.iterrows():
        filter_options.append({
            "start_datetime": row.get("start_datetime"),
            "end_datetime": row.get("end_datetime"),
            "event_title": row.get("event_title"),
            "calendar_name": row.get("calendar_name"),
        })

    collection = _database[CalendarDocument.get_collection_name()]
    existing_docs = list(collection.find({"$or": filter_options}))
    
    existing_events_set = {
        (
            doc.get("start_datetime"),
            doc.get("end_datetime"),
            doc.get("event_title"),
            doc.get("calendar_name")
        )
        for doc in existing_docs
    }
    logger.info(f"Found {len(existing_events_set)} existing events in the database.")

    documents_to_insert = []
    for index, row in df.iterrows():
        event_key = (
            row.get("start_datetime"),
            row.get("end_datetime"),
            row.get("event_title"),
            row.get("calendar_name")
        )
        
        if event_key not in existing_events_set:
            try:
                # 이제 row.to_dict()는 짧은 키를 가진 딕셔너리를 반환합니다.
                documents_to_insert.append(CalendarDocument(**row.to_dict()))
            except Exception as e:
                logger.error(f"Failed to validate row {index + 2}: {e}. Row data: {row.to_dict()}")

    if documents_to_insert:
        logger.info(f"Attempting to bulk insert {len(documents_to_insert)} new documents.")
        success = CalendarDocument.bulk_insert(documents_to_insert)
        if success:
            logger.info(f"Successfully saved {len(documents_to_insert)} new calendar events.")
        else:
            logger.error("Bulk insert operation failed.")
    else:
        logger.info("No new calendar events to save.")