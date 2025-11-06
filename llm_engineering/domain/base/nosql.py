import uuid
from abc import ABC
from typing import Generic, Type, TypeVar

from loguru import logger
from pydantic import UUID4, BaseModel, Field
from pymongo import errors

from llm_engineering.domain.exceptions import ImproperlyConfigured
from llm_engineering.infrastructure.db.mongo import connection
from llm_engineering.settings import settings

_database = connection.get_database(settings.DATABASE_NAME)


T = TypeVar("T", bound="NoSQLBaseDocument")


class NoSQLBaseDocument(BaseModel, Generic[T], ABC):
    id: UUID4 = Field(default_factory=uuid.uuid4)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, self.__class__):
            return False

        return self.id == value.id

    def __hash__(self) -> int:
        return hash(self.id)

    @classmethod
    def from_mongo(cls: Type[T], data: dict) -> T:
        """Convert "_id" (str object) into "id" (UUID object)."""

        if not data:
            raise ValueError("Data is empty.")

        id = data.pop("_id")

        return cls(**dict(data, id=id))

    def to_mongo(self: T, **kwargs) -> dict:
        """Convert "id" (UUID object) into "_id" (str object)."""
        exclude_unset = kwargs.pop("exclude_unset", False)
        by_alias = kwargs.pop("by_alias", True)

        parsed = self.model_dump(exclude_unset=exclude_unset, by_alias=by_alias, **kwargs)

        if "_id" not in parsed and "id" in parsed:
            parsed["_id"] = str(parsed.pop("id"))

        for key, value in parsed.items():
            if isinstance(value, uuid.UUID):
                parsed[key] = str(value)

        return parsed

    def model_dump(self: T, **kwargs) -> dict:
        dict_ = super().model_dump(**kwargs)

        for key, value in dict_.items():
            if isinstance(value, uuid.UUID):
                dict_[key] = str(value)

        return dict_

    def save(self: T, **kwargs) -> T | None:
        collection = _database[self.get_collection_name()]
        doc_data = self.to_mongo(**kwargs)
        doc_id = doc_data.get("_id")

        try:
            if doc_id:
                # If ID exists, perform an upsert (update or insert)
                collection.replace_one({"_id": doc_id}, doc_data, upsert=True)
            else:
                # If no ID, just insert
                collection.insert_one(doc_data)
            
            return self
        except errors.DuplicateKeyError:
            # This might happen in a race condition if doc_id is None but another key is duplicated
            logger.error(f"Duplicate key error while saving document.")
            return None
        except errors.WriteError as e:
            logger.exception(f"Failed to save document: {e}")
            return None
    
    def update(self: T, filter_options: dict, **kwargs) -> T | None:
        """Updates an existing document in the collection."""
        collection = _database[self.get_collection_name()]
        try:
            # $set 연산자를 사용하여 제공된 필드만 업데이트합니다.
            update_data = {"$set": self.to_mongo(**kwargs)}
            result = collection.update_one(filter_options, update_data)

            if result.modified_count > 0:
                logger.debug(f"Successfully updated document with filter: {filter_options}")
                return self
            elif result.matched_count > 0:
                logger.debug(f"Document matched but no fields were modified: {filter_options}")
                return self
            else:
                logger.warning(f"No document found to update with filter: {filter_options}")
                return None
        except errors.WriteError:
            logger.exception(f"Failed to update document with filter: {filter_options}")
            return None


    @classmethod
    def get_or_create(cls: Type[T], **filter_options) -> T:
        collection = _database[cls.get_collection_name()]
        try:
            instance = collection.find_one(filter_options)
            if instance:
                return cls.from_mongo(instance)

            new_instance = cls(**filter_options)
            new_instance = new_instance.save()

            return new_instance
        except errors.OperationFailure:
            logger.exception(f"Failed to retrieve document with filter options: {filter_options}")

            raise

    @classmethod
    def bulk_insert(cls: Type[T], documents: list[T], **kwargs) -> bool:
        collection = _database[cls.get_collection_name()]
        try:
            collection.insert_many(doc.to_mongo(**kwargs) for doc in documents)

            return True
        except (errors.WriteError, errors.BulkWriteError):
            logger.error(f"Failed to insert documents of type {cls.__name__}")

            return False

    @classmethod
    def bulk_upsert(cls: Type[T], documents: list[T], match_field: str = "_id", **kwargs) -> dict:
        """
        Bulk upsert documents using MongoDB's bulk_write API.

        Args:
            documents: List of documents to upsert
            match_field: Field to match on for upsert (default: "_id")
            **kwargs: Additional options for to_mongo()

        Returns:
            dict with counts: {"matched": int, "modified": int, "upserted": int}
        """
        from pymongo import ReplaceOne

        collection = _database[cls.get_collection_name()]

        if not documents:
            return {"matched": 0, "modified": 0, "upserted": 0}

        try:
            operations = []
            for doc in documents:
                doc_data = doc.to_mongo(**kwargs)
                filter_dict = {match_field: doc_data.get(match_field)}
                operations.append(ReplaceOne(filter_dict, doc_data, upsert=True))

            result = collection.bulk_write(operations, ordered=False)

            logger.info(
                f"Bulk upsert completed for {cls.__name__}: "
                f"matched={result.matched_count}, "
                f"modified={result.modified_count}, "
                f"upserted={result.upserted_count}"
            )

            return {
                "matched": result.matched_count,
                "modified": result.modified_count,
                "upserted": result.upserted_count
            }
        except (errors.WriteError, errors.BulkWriteError) as e:
            logger.error(f"Failed to bulk upsert documents of type {cls.__name__}: {e}")
            return {"matched": 0, "modified": 0, "upserted": 0}

    @classmethod
    def find(cls: Type[T], **filter_options) -> T | None:
        collection = _database[cls.get_collection_name()]
        try:
            instance = collection.find_one(filter_options)
            if instance:
                return cls.from_mongo(instance)

            return None
        except errors.OperationFailure:
            logger.error("Failed to retrieve document")

            return None

    @classmethod
    def bulk_find(cls: Type[T], **filter_options) -> list[T]:
        collection = _database[cls.get_collection_name()]
        try:
            instances = collection.find(filter_options)
            return [document for instance in instances if (document := cls.from_mongo(instance)) is not None]
        except errors.OperationFailure:
            logger.error("Failed to retrieve documents")

            return []

    @classmethod
    def get_collection_name(cls: Type[T]) -> str:
        if not hasattr(cls, "Settings") or not hasattr(cls.Settings, "name"):
            raise ImproperlyConfigured(
                "Document should define an Settings configuration class with the name of the collection."
            )

        return cls.Settings.name

    @classmethod
    def find_latest_by_author(cls: Type[T], author_id: UUID4) -> T | None:
        collection = _database[cls.get_collection_name()]
        try:
            instance = collection.find_one(
                {"author_id": str(author_id)},
                sort=[("last_edited_time", -1)]
            )
            if instance:
                return cls.from_mongo(instance)
            return None
        except errors.OperationFailure:
            logger.error("Failed to retrieve latest document by author")
            return None
