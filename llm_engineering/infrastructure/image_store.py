import io
import requests
from loguru import logger
from PIL import Image
from gridfs import GridFS
from pymongo import MongoClient
from bson import ObjectId

from llm_engineering.settings import settings


class ImageStore:
    """
    Handles downloading images, resizing them, and storing them in MongoDB's GridFS.
    """

    def __init__(self):
        try:
            self.client = MongoClient(settings.DATABASE_HOST)
            self.db = self.client[settings.DATABASE_NAME]
            self.fs = GridFS(self.db)
            logger.info("ImageStore connected to MongoDB and GridFS.")
        except Exception as e:
            logger.exception(f"Failed to connect ImageStore to MongoDB: {e}")
            self.fs = None

    def save_image_from_url(
        self, url: str, filename: str, max_size: tuple[int, int] = (1024, 1024)
    ) -> ObjectId | None:
        """
        Downloads an image, resizes it, and saves it to GridFS.

        Args:
            url: The URL of the image to download.
            filename: The name to store the file with.
            max_size: A tuple (width, height) for the maximum image dimensions.

        Returns:
            The ObjectId of the stored file in GridFS, or None if failed.
        """
        if not self.fs:
            logger.error("GridFS is not available. Cannot save image.")
            return None

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            image_data = io.BytesIO(response.content)
            with Image.open(image_data) as img:
                # Resize the image if it exceeds the max dimensions
                img.thumbnail(max_size)

                # Save the (potentially resized) image to a memory buffer
                output_buffer = io.BytesIO()
                img_format = img.format if img.format in ["JPEG", "PNG"] else "JPEG"
                img.save(output_buffer, format=img_format)
                output_buffer.seek(0)

                # Store in GridFS
                file_id = self.fs.put(
                    output_buffer,
                    filename=filename,
                    content_type=f"image/{img_format.lower()}",
                    original_url=url,
                )
                logger.success(f"Saved image from {url} to GridFS with ID: {file_id}")
                return file_id

        except requests.RequestException as e:
            logger.warning(f"Failed to download image from {url}: {e}")
        except Exception as e:
            logger.exception(f"An error occurred while processing image {url}: {e}")

        return None
