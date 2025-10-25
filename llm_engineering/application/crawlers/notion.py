# llm_engineering/application/crawlers/notion.py

from loguru import logger
import notion_client
from datetime import datetime, timezone # timezone을 import 합니다.
import requests

from llm_engineering.domain.documents import NotionPageDocument, UserDocument
from llm_engineering.settings import settings
from llm_engineering.infrastructure.image_store import ImageStore
from .base import BaseCrawler


class NotionCrawler(BaseCrawler):
    """
    Crawls and syncs all accessible pages from a Notion workspace.
    - Inserts new pages.
    - Updates pages that have been modified since the last crawl.
    - Skips unchanged pages.
    """
    model = NotionPageDocument
    BASE_URL = "https://api.notion.com/v1"

    def __init__(self):
        self.notion = notion_client.Client(auth=settings.NOTION_API_KEY)
        self.headers = {
            "Authorization": f"Bearer {settings.NOTION_API_KEY}",
            "Notion-Version": "2022-06-28",
        }

    def _get_page(self, page_id: str) -> dict:
        res = requests.get(f"{self.BASE_URL}/pages/{page_id}", headers=self.headers, timeout=30)
        res.raise_for_status()
        return res.json()

    def _get_db(self, db_id: str) -> dict:
        res = requests.get(f"{self.BASE_URL}/databases/{db_id}", headers=self.headers, timeout=30)
        res.raise_for_status()
        return res.json()

    def _get_block_children(self, block_id: str) -> list:
        """Get all blocks (including pagination)"""
        results, cursor = [], None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            res = requests.get(
                f"{self.BASE_URL}/blocks/{block_id}/children",
                headers=self.headers,
                params=params,
                timeout=30,
            )
            res.raise_for_status()
            data = res.json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    def _rich_to_text(self, rich: list) -> str:
        return "".join(x.get("plain_text", "") for x in (rich or []))

    def _extract_property_value(self, prop: dict, resolve_relations: bool = True) -> any:
        """
        Property 타입에 따라 값을 추출

        Args:
            prop: Property 데이터
            resolve_relations: True이면 relation의 실제 제목을 조회 (API 호출 발생)
        """
        prop_type = prop.get("type")

        if prop_type == "title":
            return self._rich_to_text(prop.get("title", []))

        elif prop_type == "rich_text":
            return self._rich_to_text(prop.get("rich_text", []))

        elif prop_type == "number":
            return prop.get("number")

        elif prop_type == "select":
            select = prop.get("select")
            return select.get("name") if select else None

        elif prop_type == "multi_select":
            return [item.get("name") for item in prop.get("multi_select", [])]

        elif prop_type == "date":
            date_obj = prop.get("date")
            if date_obj:
                return {
                    "start": date_obj.get("start"),
                    "end": date_obj.get("end"),
                    "time_zone": date_obj.get("time_zone")
                }
            return None

        elif prop_type == "people":
            return [person.get("name") for person in prop.get("people", [])]

        elif prop_type == "files":
            files = []
            for file in prop.get("files", []):
                if file.get("type") == "file":
                    files.append(file.get("file", {}).get("url"))
                elif file.get("type") == "external":
                    files.append(file.get("external", {}).get("url"))
            return files

        elif prop_type == "checkbox":
            return prop.get("checkbox")

        elif prop_type == "url":
            return prop.get("url")

        elif prop_type == "email":
            return prop.get("email")

        elif prop_type == "phone_number":
            return prop.get("phone_number")

        elif prop_type == "formula":
            formula = prop.get("formula", {})
            formula_type = formula.get("type")
            if formula_type:
                return formula.get(formula_type)
            return None

        elif prop_type == "relation":
            relation_ids = [rel.get("id") for rel in prop.get("relation", [])]

            # resolve_relations=True이면 실제 제목 조회
            if resolve_relations and relation_ids:
                relation_titles = []
                for rel_id in relation_ids:
                    try:
                        rel_page = self._get_page(rel_id)
                        rel_title = self._get_page_title(rel_page)
                        relation_titles.append({
                            "id": rel_id,
                            "title": rel_title
                        })
                    except requests.HTTPError:
                        # 접근 권한이 없거나 삭제된 페이지
                        relation_titles.append({
                            "id": rel_id,
                            "title": "(inaccessible)"
                        })
                return relation_titles

            # 기본적으로는 ID만 반환
            return relation_ids

        elif prop_type == "rollup":
            rollup = prop.get("rollup", {})
            rollup_type = rollup.get("type")
            if rollup_type:
                return rollup.get(rollup_type)
            return None

        elif prop_type == "created_time":
            return prop.get("created_time")

        elif prop_type == "created_by":
            created_by = prop.get("created_by", {})
            return created_by.get("name") if created_by else None

        elif prop_type == "last_edited_time":
            return prop.get("last_edited_time")

        elif prop_type == "last_edited_by":
            edited_by = prop.get("last_edited_by", {})
            return edited_by.get("name") if edited_by else None

        elif prop_type == "status":
            status = prop.get("status")
            return status.get("name") if status else None

        else:
            # 알 수 없는 타입은 None 반환 (button 등)
            return None

    def _extract_page_properties(self, page: dict, resolve_relations: bool = True) -> dict:
        """
        페이지의 모든 properties를 추출하여 딕셔너리로 반환

        Args:
            page: Notion 페이지 객체
            resolve_relations: True이면 relation property의 실제 제목을 조회
        """
        properties = {}
        for prop_name, prop_data in page.get("properties", {}).items():
            prop_value = self._extract_property_value(prop_data, resolve_relations=resolve_relations)
            # None이 아닌 값만 저장 (button 등 불필요한 property 제외)
            if prop_value is not None:
                properties[prop_name] = {
                    "type": prop_data.get("type"),
                    "value": prop_value
                }
        return properties

    def _get_page_title(self, page: dict) -> str:
        for _, prop in page.get("properties", {}).items():
            if prop.get("type") == "title":
                return self._rich_to_text(prop.get("title"))
        return "(untitled)"

    def _get_parent_title(self, page_obj: dict):
        """Parent document or database information"""
        parent = page_obj.get("parent", {})
        t = parent.get("type")
        if t == "page_id":
            pid = parent.get("page_id")
            try:
                p = self._get_page(pid)
                return ("page", pid, self._get_page_title(p))
            except requests.HTTPError:
                logger.warning(f"Could not retrieve parent page {pid}. It might be inaccessible.")
                return ("page", pid, "(inaccessible page)")
        elif t == "database_id":
            did = parent.get("database_id")
            try:
                db = self._get_db(did)
                return ("database", did, self._rich_to_text(db.get("title")) or "(untitled db)")
            except requests.HTTPError:
                logger.warning(f"Could not retrieve parent database {did}. It might be inaccessible.")
                return ("database", did, "(inaccessible database)")
        elif t == "workspace":
            return ("workspace", None, "Workspace Root")
        else:
            return ("unknown", None, "(no parent)")

    def _get_ancestor_titles(self, page_obj: dict, max_hops: int = 10) -> list:
        """Collect parent-ancestor title chain (root->current order)"""
        chain = []
        cur = page_obj
        for _ in range(max_hops):
            kind, pid, title = self._get_parent_title(cur)
            chain.append({"type": kind, "id": pid, "title": title})
            if kind in ("workspace", "unknown") or not pid:
                break
            if kind == "page":
                try:
                    cur = self._get_page(pid)
                except requests.HTTPError:
                    break # Stop if we can't access an ancestor
            elif kind == "database":
                break
        chain = [c for c in chain if c["type"] != "unknown"]
        return list(reversed(chain))

    def _render_block(self, block: dict) -> str:
        """Convert a Notion block to a markdown string"""
        t = block.get("type")
        b = block.get(t, {})
        if not b:
            return ""

        if t == "paragraph":
            return self._rich_to_text(b.get("rich_text")) + "\n"
        if t == "heading_1":
            return "# " + self._rich_to_text(b.get("rich_text")) + "\n"
        if t == "heading_2":
            return "## " + self._rich_to_text(b.get("rich_text")) + "\n"
        if t == "heading_3":
            return "### " + self._rich_to_text(b.get("rich_text")) + "\n"
        if t == "bulleted_list_item":
            return "- " + self._rich_to_text(b.get("rich_text")) + "\n"
        if t == "numbered_list_item":
            return "1. " + self._rich_to_text(b.get("rich_text")) + "\n"
        if t == "callout":
            icon = b.get("icon", {}).get("emoji", "")
            text = self._rich_to_text(b.get("rich_text"))
            return f"{icon} {text}\n"
        if t == "quote":
            return "> " + self._rich_to_text(b.get("rich_text")) + "\n"
        if t == "code":
            lang = b.get("language", "")
            code = self._rich_to_text(b.get("rich_text"))
            return f"```{lang}\n{code}\n```\n"
        return ""

    def _extract_child_titles(self, blocks: list) -> dict:
        """Extract child/grandchild document titles"""
        children, grandchildren = [], []
        for blk in blocks:
            if blk.get("type") == "child_page":
                cid = blk["id"]
                ctitle = blk["child_page"]["title"]
                children.append({"title": ctitle, "id": cid})
                # Find grandchildren
                try:
                    sub_blocks = self._get_block_children(cid)
                    for sb in sub_blocks:
                        if sb.get("type") == "child_page":
                            gcid = sb["id"]
                            gctitle = sb["child_page"]["title"]
                            grandchildren.append(
                                {"parent_title": ctitle, "title": gctitle, "id": gcid}
                            )
                except requests.HTTPError:
                    logger.warning(f"Could not retrieve blocks for child page {cid}. It might be inaccessible.")

        return {"children": children, "grandchildren": grandchildren}

    def _parse_page_to_document(self, page: dict, user: UserDocument) -> NotionPageDocument | None:
        """Helper function to parse a Notion API page object into our document model."""
        try:
            page_id = page["id"]

            # Re-fetch the full page object to ensure all properties are present
            full_page_obj = self._get_page(page_id)

            page_title = self._get_page_title(full_page_obj)
            if not page_title or page_title == "(untitled)":
                logger.warning(f"Page (ID: {page_id}) has no title. Skipping.")
                return None

            # Extract properties (with relation titles resolved)
            properties = self._extract_page_properties(full_page_obj, resolve_relations=True)

            ancestors = self._get_ancestor_titles(full_page_obj)
            blocks = self._get_block_children(page_id)

            # Extract image URLs from blocks
            image_urls = []
            for block in blocks:
                if block.get("type") == "image":
                    image_block = block.get("image", {})
                    image_type = image_block.get("type")
                    url = None
                    if image_type == "external":
                        url = image_block.get("external", {}).get("url")
                    elif image_type == "file":
                        url = image_block.get("file", {}).get("url")

                    if url:
                        image_urls.append(url)

            content = "".join(self._render_block(b) for b in blocks if self._render_block(b))

            hierarchy = self._extract_child_titles(blocks)

            last_edited_time_dt = datetime.fromisoformat(page.get("last_edited_time"))
            created_time_dt = datetime.fromisoformat(page.get("created_time"))

            doc = self.model(
                notion_page_id=page_id,
                url=page.get("url", ""),
                title=page_title,
                content=content,
                image_gridfs_ids=image_urls,  # Initially store URLs
                properties=properties,  # Add properties to document
                ancestors=ancestors,
                children=hierarchy["children"],
                grandchildren=hierarchy["grandchildren"],
                last_edited_time=last_edited_time_dt,
                created_time=created_time_dt,
                author_id=user.id,
                author_full_name=user.full_name,
            )

            # If images were found, process them and replace URLs with GridFS IDs
            if doc.image_gridfs_ids:
                logger.info(f"Found {len(doc.image_gridfs_ids)} images in page '{doc.title}'. Processing...")
                image_store = ImageStore()
                gridfs_ids = []
                for i, img_url in enumerate(doc.image_gridfs_ids):
                    filename = f"{doc.notion_page_id}_{i}.jpg"
                    file_id = image_store.save_image_from_url(img_url, filename=filename)
                    if file_id:
                        gridfs_ids.append(str(file_id))
                doc.image_gridfs_ids = gridfs_ids

            return doc

        except Exception as e:
            logger.exception(f"Failed to parse Notion page (ID: {page.get('id')}): {e}")
            return None

    def extract(self, **kwargs) -> None:
        user = kwargs.get("user")
        if not user:
            logger.error("A valid UserDocument must be provided.")
            return

        logger.info(f"Starting Notion data sync for user '{user.full_name}'...")

        # 1. Get last sync time from DB
        last_synced_doc = self.model.find_latest_by_author(user.id)
        last_sync_time = last_synced_doc.last_edited_time if last_synced_doc else None

        if last_sync_time:
            logger.info(f"Last sync was at {last_sync_time}. Will process pages edited after this time.")
        else:
            logger.info("No previous sync found. Performing a full sync...")

        # 2. Fetch ALL pages from Notion using pagination (search API doesn't support timestamp filters)
        all_api_pages = []
        next_cursor = None
        logger.info("Fetching all accessible pages from Notion...")
        while True:
            response = self.notion.search(
                filter={"value": "page", "property": "object"},
                start_cursor=next_cursor,
                page_size=100,
            )
            all_api_pages.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
        logger.info(f"Fetched a total of {len(all_api_pages)} pages from the Notion API.")

        # 3. Manually filter for new or updated pages based on last_sync_time
        if last_sync_time:
            last_sync_time_utc = last_sync_time.replace(tzinfo=timezone.utc)
            pages_to_process = [
                page for page in all_api_pages 
                if datetime.fromisoformat(page.get("last_edited_time")) > last_sync_time_utc
            ]
            logger.info(f"{len(pages_to_process)} pages found edited after last sync time.")
        else:
            pages_to_process = all_api_pages

        if not pages_to_process:
            logger.info("No new or updated Notion pages to process.")
            return

        # 4. Fetch existing documents from MongoDB for comparison
        pages_to_process_ids = [page["id"] for page in pages_to_process]
        existing_mongo_docs = self.model.bulk_find(notion_page_id={"$in": pages_to_process_ids})
        
        existing_docs_map = {doc.notion_page_id: doc for doc in existing_mongo_docs}
        logger.info(f"Found {len(existing_docs_map)} relevant existing Notion documents in MongoDB.")

        docs_to_insert = []
        docs_to_update = []
        skipped_count = 0

        # 5. Compare API data with DB data to determine sync actions
        for page in pages_to_process:
            page_id = page["id"]
            api_last_edited_time = datetime.fromisoformat(page.get("last_edited_time"))
            
            existing_doc = existing_docs_map.get(page_id)

            if not existing_doc:
                # Case 1: Not in DB -> New document
                title_list = page.get('properties', {}).get('title', {}).get('title', [])
                log_title = title_list[0].get('plain_text', page_id) if title_list else f"Untitled Page ({page_id})"
                logger.info(f"New page found: '{log_title}'. Preparing for insertion.")
                new_doc = self._parse_page_to_document(page, user)
                if new_doc:
                    docs_to_insert.append(new_doc)
            
            elif api_last_edited_time > existing_doc.last_edited_time.replace(tzinfo=timezone.utc):
                # Case 2: In DB and updated -> Update document
                logger.info(f"Updated page found: '{existing_doc.title}'. Preparing for update.")
                updated_doc = self._parse_page_to_document(page, user)
                if updated_doc:
                    updated_doc.id = existing_doc.id
                    docs_to_update.append(updated_doc)
            
            else:
                # Case 3: In DB and unchanged -> Skip
                skipped_count += 1

        if skipped_count > 0:
            logger.debug(f"Skipped {skipped_count} unchanged pages.")

        # 6. Execute DB operations
        if docs_to_insert:
            logger.info(f"Attempting to bulk insert {len(docs_to_insert)} new Notion pages...")
            if self.model.bulk_insert(docs_to_insert):
                logger.success(f"Successfully inserted {len(docs_to_insert)} new pages.")
            else:
                logger.error("Bulk insert operation failed.")

        if docs_to_update:
            logger.info(f"Attempting to update {len(docs_to_update)} modified Notion pages...")
            updated_count = 0
         
            # If a bulk update method is available, it would be more efficient.
            for doc in docs_to_update:
                # A simple save() call is often how Bevy ODM persists changes to an existing doc
                try:
                    doc.save()
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update document {doc.id}: {e}")

            if updated_count > 0:
                logger.success(f"Successfully updated {updated_count} pages.")