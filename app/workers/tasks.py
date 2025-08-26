import asyncio
import logging

from celery import Celery

from app.config import settings
from app.db import AsyncSessionLocal
from app.db.models import Company
from app.services import discovery, scraping

from .agent import AIExtractionAgent

celery = Celery(broker=settings.RABBITMQ_URL)
ai_agent = AIExtractionAgent()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def process_company(company_id: int, db):
    company = await db.get(Company, company_id)

    if not company:
        logger.error(f"Company with ID {company_id} not found.")
        return

    company_name = company.name

    logger.info(f"Starting Step 1: Discovering URLs for {company_name}")
    discovered_urls = await discovery.discover_company_resources(company, db)

    logger.info(f"Starting Step 2: Scraping for {company_name}")
    scraped_pages = await scraping.scrape_discovered_urls(discovered_urls, company, db)

    logger.info(f"Starting Step 3: AI Extraction for {company_name}")
    await ai_agent.extract_aum(company, scraped_pages, db)

    logger.info(f"Complete processing for company: {company_name}")


@celery.task
def process_company_task(company_id: int):
    """Main task to process a single company from start to finish."""

    async def task():
        async with AsyncSessionLocal.session() as db:
            await process_company(company_id, db)

    asyncio.run(task())
