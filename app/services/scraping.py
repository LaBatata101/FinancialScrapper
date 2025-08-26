import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Coroutine

from pydoll.browser import Chrome
from pydoll.browser.tab import Tab

from app.db import AsyncSession
from app.db.models import Company, ScrapeLog

from .discovery import get_browser_options

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def scrape_single_url(tab: Tab, url: str, category: str, company_id: int) -> tuple[str | None, ScrapeLog]:
    logger.info(f"Scraping [{category}]: {url}")

    log_entry = ScrapeLog(company_id=company_id, url=url, status="PENDING")

    try:
        await tab.enable_network_events()

        await tab.go_to(url, timeout=45)
        await asyncio.sleep(random.uniform(1, 3))  # Wait for content to load

        if category in ["instagram", "linkedin", "twitter", "x"]:
            # Scroll down to load more content
            for _ in range(3):
                await tab.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(1)

        content = await tab.page_source

        log_entry.status = "SUCCESS"
        log_entry.scraped_at = datetime.now(timezone.utc)
        log_entry.content_length = len(content)

        return content, log_entry
    except Exception as e:
        error = str(e)
        logger.error(f"Failed to scrape {url}: {error}")
        log_entry.status = "FAILED"
        log_entry.error_msg = error
        log_entry.scraped_at = datetime.now(timezone.utc)
        log_entry.content_length = len(error)
        return None, log_entry


async def scrape_discovered_urls(
    discovered_urls: dict[str, set[str]], company: Company, db: AsyncSession
) -> list[dict[str, str]]:
    """
    Orchestrates the scraping of all discovered URLs, following a priority order.
    """
    scraped_content = []
    logs_to_add = []

    priority_order = ["reports", "corporate", "news", "linkedin", "facebook", "instagram", "twitter"]

    urls_to_scrape = []
    for category in priority_order:
        urls = discovered_urls.get(category, set())
        for url in urls:
            urls_to_scrape.append({"url": url, "category": category})

    semaphore = asyncio.Semaphore(4)
    tasks: list[Coroutine] = []
    company_name = company.name

    async def scrape_content(browser, item):
        async with semaphore:
            if item["url"]:
                tab = await browser.new_tab()
                content, log_entry = await scrape_single_url(tab, item["url"], item["category"], company.id)
                logs_to_add.append(log_entry)

                if content:
                    scraped_content.append({"url": item["url"], "category": item["category"], "content": content})
                await asyncio.sleep(1)

    async with Chrome(options=get_browser_options()) as browser:
        await browser.start()
        for item in urls_to_scrape:
            tasks.append(scrape_content(browser, item))

        await asyncio.gather(*tasks)

    db.add_all(logs_to_add)
    await db.commit()

    logger.info(f"Scraping completed for company {company_name}. {len(scraped_content)} pages processed successfully.")
    return scraped_content
