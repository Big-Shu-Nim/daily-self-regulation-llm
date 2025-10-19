from enum import StrEnum


from enum import Enum


class DataCategory(str, Enum):
    POSTS = "posts"
    ARTICLES = "articles"
    REPOSITORIES = "repositories"
    QUERIES = "queries"
    NAVER_POSTS = "naver_posts"
    NOTION_PAGES = "notion_pages"
    CALENDAR = "calendar"
    INSTRUCT_DATASET_SAMPLES = "instruct_dataset_samples"
    PREFERENCE_DATASET_SAMPLES = "preference_dataset_samples"
    INSTRUCT_DATASET = "instruct_dataset"
    PREFERENCE_DATASET = "preference_dataset"
    PROMPT = "prompt"
