
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
from typing_extensions import Annotated
from zenml import get_step_context, step

from llm_engineering.application import utils
from llm_engineering.domain.base.nosql import NoSQLBaseDocument
from llm_engineering.domain.documents import (
    NaverPostDocument,
    NotionPageDocument,
    CalendarDocument,
    UserDocument,
    Document,
)


@step
def query_custom_data(
    author_full_names: list[str],
) -> Annotated[list, "raw_documents"]:
    """
    Queries the data warehouse for custom data sources (Naver, Notion, Calendar)
    for the given authors.
    """
    documents = []
    authors = []
    for author_full_name in author_full_names:
        logger.info(f"Querying data warehouse for user: {author_full_name}")

        first_name, last_name = utils.split_user_full_name(author_full_name)
        logger.info(f"First name: {first_name}, Last name: {last_name}")
        user = UserDocument.get_or_create(first_name=first_name, last_name=last_name)
        authors.append(user)

        results = fetch_all_custom_data(user)
        user_documents = [doc for query_result in results.values() for doc in query_result]

        documents.extend(user_documents)

    step_context = get_step_context()
    step_context.add_output_metadata(output_name="raw_documents", metadata=_get_metadata(documents))

    return documents


def fetch_all_custom_data(user: UserDocument) -> dict[str, list[NoSQLBaseDocument]]:
    """
    Fetches all custom data types from the data warehouse for a given user.
    """
    user_id = str(user.id)
    with ThreadPoolExecutor() as executor:
        future_to_query = {
            executor.submit(__fetch_naver_posts, user_id): "naver_posts",
            executor.submit(__fetch_notion_pages, user_id): "notion_pages",
            executor.submit(__fetch_calendar_events, user_id): "calendar_events",
        }

        results = {}
        for future in as_completed(future_to_query):
            query_name = future_to_query[future]
            try:
                results[query_name] = future.result()
            except Exception:
                logger.exception(f"'{query_name}' request failed.")
                results[query_name] = []

    return results


def __fetch_naver_posts(user_id: str) -> list[NoSQLBaseDocument]:
    logger.info(f"Fetching Naver posts for user_id: {user_id}")
    start_time = time.time()
    results = NaverPostDocument.bulk_find(author_id=user_id)
    end_time = time.time()
    logger.info(f"Finished fetching Naver posts in {end_time - start_time:.2f} seconds.")
    return results


def __fetch_notion_pages(user_id: str) -> list[NoSQLBaseDocument]:
    logger.info(f"Fetching Notion pages for user_id: {user_id}")
    start_time = time.time()
    results = NotionPageDocument.bulk_find(author_id=user_id)
    end_time = time.time()
    logger.info(f"Finished fetching Notion pages in {end_time - start_time:.2f} seconds.")
    return results


def __fetch_calendar_events(user_id: str) -> list[NoSQLBaseDocument]:
    logger.info(f"Fetching Calendar events for user_id: {user_id}")
    start_time = time.time()
    results = CalendarDocument.bulk_find(author_id=user_id)
    end_time = time.time()
    logger.info(f"Finished fetching Calendar events in {end_time - start_time:.2f} seconds.")
    return results


def _get_metadata(documents: list[Document]) -> dict:
    """Generates metadata about the fetched documents."""
    metadata = {
        "num_documents": len(documents),
    }
    for document in documents:
        collection = document.get_collection_name()
        if collection not in metadata:
            metadata[collection] = {}
        if "authors" not in metadata[collection]:
            metadata[collection]["authors"] = list()

        metadata[collection]["num_documents"] = metadata[collection].get("num_documents", 0) + 1
        metadata[collection]["authors"].append(document.author_full_name)

    for value in metadata.values():
        if isinstance(value, dict) and "authors" in value:
            value["authors"] = list(set(value["authors"]))

    return metadata
