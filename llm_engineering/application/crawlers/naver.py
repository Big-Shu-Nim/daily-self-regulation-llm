# llm_engineering/application/crawlers/naver.py

import time
import re
import json
from urllib.parse import urlparse, parse_qs
from loguru import logger

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from llm_engineering.domain.documents import NaverPostDocument, UserDocument
from llm_engineering.settings import settings
from .base import BaseCrawler

class NaverCrawler(BaseCrawler):
    """
    Crawls all public posts from a Naver Blog using mobile list view pagination.
    This version is based on a proven, robust script and integrated into the ETL framework.
    """
    model = NaverPostDocument

    def __init__(self, headless: bool = True):
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--log-level=3")
        opts.add_argument("--disable-extensions")
        opts.add_argument(f"--user-agent={settings.NAVER_USER_AGENT}")
        
        self.driver = webdriver.Chrome(options=opts)
        self.driver.set_page_load_timeout(30)
        logger.info("NaverCrawler WebDriver (headless) initialized.")

    # --- 기존 유틸리티 함수들을 그대로 클래스 메소드로 가져옴 ---
    
    def _blog_id(self, x: str) -> str:
        x = x.strip()
        if x.startswith(("http://","https://")):
            p = urlparse(x); qs = parse_qs(p.query)
            if qs.get("blogId"): return qs["blogId"][0]
            segs = [s for s in p.path.strip("/").split("/") if s]
            if segs: return segs[-1]
        return x

    def _log_no(self, link: str) -> str | None:
        try:
            p = urlparse(link); qs = parse_qs(p.query)
            if qs.get("logNo"): return qs["logNo"][0]
            m = re.search(r"logNo=(\d+)", link)
            return m.group(1) if m else None
        except Exception: return None

    def _clean_text(self, s: str | None) -> str | None:
        if not s: return s
        s = re.sub(r'\s+\n', '\n', s)
        s = re.sub(r'\n\s+', '\n', s)
        s = re.sub(r'[ \t]+', ' ', s)
        return s.strip()

    def _pick_attr(self, el, attrs=("data-src","data-lazy-src","src")) -> str | None:
        for a in attrs:
            v = el.get_attribute(a)
            if v: return v
        return None

    def _norm_url(self, u: str) -> str:
        if u.startswith("//"): return "https:" + u
        return u

    # --- 핵심 로직 함수들도 클래스 메소드로 가져옴 ---

    def _collect_links_from_mobile_list(self, blog_id: str, page: int, sleep: float = 0.6) -> list[str]:
        url = f"https://m.blog.naver.com/PostList.naver?blogId={blog_id}&categoryNo=0&from=postList&currentPage={page}"
        try:
            self.driver.get(url)
        except TimeoutException:
            logger.warning(f"Timeout while trying to access page {page}. This might be the last page. Stopping pagination.")
            return [] # Return an empty list to signal the end.
        time.sleep(sleep)
        for _ in range(2):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.3)
        anchors = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/m/PostView.naver"], a[href*="PostView.naver"]')
        seen, links = set(), []
        for a in anchors:
            href = a.get_attribute("href") or ""
            if "PostView" in href and href not in seen:
                seen.add(href)
                links.append(href)
        return links

    def _parse_post_detail(self, link: str, sleep: float = 0.5) -> dict:
        self.driver.get(link)
        time.sleep(sleep)
        title_candidates = [('meta[property="og:title"]', "content"), ('h3.tit_post', None), ('h3.se_textarea', None), ('#postTitleText', None), ('strong.se_textarea', None), ('div.se-title-text', None)]
        title = None
        for sel, attr in title_candidates:
            els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                title = (els[0].get_attribute(attr) if attr else els[0].text).strip()
                if title: break
        pub_date = ""
        for sel in ["p.blog_date", "span.se_publishDate.pcol2", "span.se_publishDate", "span.tit_date"]:
            els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                txt = (els[0].text or "").strip()
                if txt: pub_date = txt; break
        category = ""
        el_cat_wrap = self.driver.find_elements(By.CSS_SELECTOR, "div.blog_category a[href*='PostList.naver'][href*='categoryNo=']")
        if el_cat_wrap: category = (el_cat_wrap[0].text or "").strip()
        if not category:
            els = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='PostList.naver'][href*='categoryNo=']")
            if els: category = (els[0].text or "").strip()
        container_selectors = ["div.se-main-container", "#postViewArea", "div#viewTypeSelector", "div#content-area", "div#post-view"]
        container = None
        for sel in container_selectors:
            els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if els: container = els[0]; break
        content_text, image_urls = None, []
        if container:
            content_text = self._clean_text(container.text)
            imgs = container.find_elements(By.CSS_SELECTOR, "img")
            seen_imgs = set()
            for im in imgs:
                u = self._pick_attr(im)
                if not u: continue
                u = self._norm_url(u)
                if u not in seen_imgs: seen_imgs.add(u); image_urls.append(u)
        return {"title": title, "link": link, "logNo": self._log_no(link), "pubDate": pub_date, "content": content_text, "images": image_urls, "category": category}

    # --- 프레임워크와 통합되는 `extract` 메소드 ---
    
    def extract(self, blog_id: str, max_pages: int | None = None, **kwargs):
        user = kwargs.get("user")
        if not user or not isinstance(user, UserDocument):
            logger.error("A valid UserDocument must be provided.")
            return

        bid = self._blog_id(blog_id)
        logger.info(f"Starting Naver Blog crawl for '{bid}' for user '{user.full_name}'...")

        try:
            # 1. 모든 링크를 수집
            all_links = []
            page = 1
            while True:
                logger.info(f"Collecting links from page {page}...")
                links_on_page = self._collect_links_from_mobile_list(bid, page)
                if not links_on_page:
                    logger.info("No more links found. Ending link collection.")
                    break
                all_links.extend(links_on_page)
                page += 1
                if max_pages and page > max_pages:
                    logger.info(f"Reached max_pages limit of {max_pages}.")
                    break
            
            unique_links = list(set(all_links))
            logger.info(f"Collected a total of {len(unique_links)} unique post links.")

            # 2. DB에서 이미 존재하는 logNo를 한번에 조회
            all_log_nos = [self._log_no(link) for link in unique_links if self._log_no(link)]
            existing_posts = self.model.bulk_find(naver_blog_id=bid, naver_log_no={"$in": all_log_nos})
            existing_log_nos = {post.naver_log_no for post in existing_posts}
            logger.info(f"Found {len(existing_log_nos)} posts already in the database.")

            # 3. 새로운 게시물만 파싱하고 저장 준비
            documents_to_insert = []
            new_links_to_parse = [link for link in unique_links if self._log_no(link) not in existing_log_nos]
            logger.info(f"Parsing {len(new_links_to_parse)} new posts...")

            for link in new_links_to_parse:
                info = self._parse_post_detail(link)
                if info and info.get("logNo"):
                    documents_to_insert.append(self.model(
                        naver_blog_id=bid, naver_log_no=info["logNo"], link=info["link"],
                        published_at=info["pubDate"],
                        content={
                            "title": info["title"], "body_text": info["content"],
                            "images": info["images"], "category": info["category"],
                        },
                        author_id=user.id, author_full_name=user.full_name,
                    ))

            # 4. DB에 Bulk Insert
            if documents_to_insert:
                logger.info(f"Attempting to bulk insert {len(documents_to_insert)} new Naver posts.")
                if self.model.bulk_insert(documents_to_insert):
                    logger.success(f"Successfully saved {len(documents_to_insert)} new posts.")
                else:
                    logger.error("Bulk insert operation for Naver posts failed.")
            else:
                logger.info("No new posts to insert.")

        finally:
            self.driver.quit()
            logger.info("WebDriver closed.")