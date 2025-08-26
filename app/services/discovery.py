import asyncio
import logging
import os
import random
import re
from typing import Coroutine
from urllib.parse import parse_qs, quote_plus, urlparse

from fake_useragent import UserAgent
from pydoll.browser import Chrome
from pydoll.browser.chromium.base import Browser
from pydoll.browser.options import ChromiumOptions
from sqlalchemy import select

from app.db import AsyncSession
from app.db.models import Company, CompanyLink, SearchResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ua = UserAgent()


def get_browser_options() -> ChromiumOptions:
    options = ChromiumOptions()

    options.binary_location = f"{os.path.expanduser("~")}/.cache/ms-playwright/chromium-1181/chrome-linux/chrome"
    options.add_argument(f"--user-agent={ua.random}")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return options


async def duckduckgo_search(browser: Browser, query: str, company_name: str) -> list[dict[str, str]]:
    logger.info(f"Searching for: '{query}'")
    results = []
    company_name = company_name.lower()
    company_name_no_space = company_name.replace(" ", "")

    tab = await browser.new_tab()
    await tab.enable_network_events()

    await asyncio.sleep(random.uniform(1.5, 3.5))

    encoded_query = quote_plus(query)
    await tab.go_to(f"https://html.duckduckgo.com/html/?q={encoded_query}", timeout=40)

    # Search for links in the DuckDuckGo search results
    elements = await tab.query('a[class="result__a"]', find_all=True, raise_exc=False)
    if elements is None:
        return []

    for element in elements:
        title = await element.text
        href = element.get_attribute("href")

        decoded_url = urlparse(href)
        queries = parse_qs(str(decoded_url.query))

        if urls := queries.get("uddg"):
            url = urls[0]

            if href and (company_name in title.lower() or company_name_no_space in url.lower()):
                results.append({"title": title, "url": url})

    logger.info(f"Found {len(results)} relevant results for '{query}'")
    return results


REPORTS_KW = re.compile("(relat[óo]rio|report|balan[çc]o|demonstrativo|investor relations)")
NEWS_KW = re.compile("(notícia|news|jornal|magazine|g1|cnn|bloomberg)")


def categorize_search_results(results: list[dict], categories: dict[str, set]):
    for result in results:
        url = result["url"]
        title = result["title"].lower()

        if "linkedin.com" in url:
            categories["linkedin"].add(url)
        elif "instagram.com" in url:
            if "stories" not in url and "reel" not in url:
                categories["instagram"].add(url)
        elif "twitter.com" in url or "x.com" in url:
            categories["twitter"].add(url)
        elif "facebook.com" in url:
            categories["facebook"].add(url)
        elif REPORTS_KW.search(title):
            categories["reports"].add(url)
        elif NEWS_KW.search(title):
            categories["news"].add(url)
        else:
            categories["corporate"].add(url)


async def discover_company_resources(company: Company, db: AsyncSession) -> dict[str, set[str]]:
    """
    Run searches, categorize results and save them in the database.
    """
    company_name = company.name
    search_queries = [
        f'"{company_name}"',
        f'"{company_name}" site:linkedin.com/company',
        f'"{company_name}" site:instagram.com',
        f'"{company_name}" site:facebook.com',
        f'"{company_name}" site:twitter.com OR site:x.com',
        f'"{company_name}" patrimônio sob gestão',
        f'"{company_name}" assets under management',
        f'"{company_name}" AUM relatório',
    ]

    discovered_urls = {
        "corporate": set(),
        "linkedin": set(),
        "instagram": set(),
        "twitter": set(),
        "facebook": set(),
        "news": set(),
        "reports": set(),
    }

    semaphore = asyncio.Semaphore(4)
    tasks: list[Coroutine] = []

    async def search_and_process(browser, query: str):
        async with semaphore:
            try:
                search_res = await duckduckgo_search(browser, query, company_name)
                for res in search_res:
                    db_res = SearchResult(company_id=company.id, query=query, title=res["title"], url=res["url"])
                    db.add(db_res)

                categorize_search_results(search_res, discovered_urls)
            except Exception as e:
                logger.error(f"The search for query '{query}' failed after retries: {e}")
            await asyncio.sleep(1)

    async with Chrome(options=get_browser_options()) as browser:
        await browser.start()
        for q in search_queries:
            tasks.append(search_and_process(browser, q))

        await asyncio.gather(*tasks)

    for platform, urls in discovered_urls.items():
        for url in urls:
            existing_link = await db.execute(select(CompanyLink).where(CompanyLink.url == url))
            if existing_link.scalar_one_or_none() is None:
                db_social = CompanyLink(company_id=company.id, platform=platform, url=url)
                db.add(db_social)

    await db.commit()
    logger.info(
        f"Discovery completed for {company_name}. URLs found: { {k: len(v) for k,v in discovered_urls.items()} }"
    )
    return discovered_urls
