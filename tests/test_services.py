from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import Base, Company, ScrapeLog, Usage
from app.services.budget_manager import BudgetManager
from app.services.discovery import (categorize_search_results,
                                    discover_company_resources,
                                    get_browser_options)
from app.services.scraping import scrape_discovered_urls, scrape_single_url

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_company():
    """Provides a mock Company object."""
    return Company(id=1, name="Test Corp")


async def test_get_today_usage(db_session):
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(table.delete())

    manager = BudgetManager(db_session)
    usage1 = Usage(tokens_used=100, operation_type="test")
    usage2 = Usage(tokens_used=200, operation_type="test")
    db_session.add_all([usage1, usage2])
    await db_session.commit()

    total_tokens = await manager.get_today_usage()
    assert total_tokens == 300


async def test_log_usage(db_session):
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(table.delete())

    manager = BudgetManager(db_session)
    await manager.log_usage(company_id=1, operation="aum_extraction", tokens=1000)

    result = await db_session.execute(select(Usage))
    usage_log = result.scalar_one_or_none()
    assert usage_log is not None
    assert usage_log.tokens_used == 1000


async def test_categorize_search_results():
    results = [
        {"url": "https://linkedin.com/company/test", "title": "Test Corp"},
        {"url": "https://example.com/report", "title": "Relatório Anual"},
        {"url": "https://news.com/article", "title": "Grande notícia sobre Test Corp"},
        {"url": "https://testcorp.com", "title": "Site Oficial"},
    ]
    categories = {
        "corporate": set(),
        "linkedin": set(),
        "instagram": set(),
        "twitter": set(),
        "facebook": set(),
        "news": set(),
        "reports": set(),
    }
    categorize_search_results(results, categories)
    assert categories["linkedin"] == {"https://linkedin.com/company/test"}
    assert categories["reports"] == {"https://example.com/report"}
    assert categories["news"] == {"https://news.com/article"}
    assert categories["corporate"] == {"https://testcorp.com"}


async def test_scrape_single_url_success(mocker, mock_company):
    mock_tab = AsyncMock()
    mock_tab.enable_network_events = AsyncMock()
    mock_tab.go_to = AsyncMock()
    mock_tab.execute_script = AsyncMock()

    async def mock_page_source():
        return "<html>Hello World</html>"

    mock_tab.page_source = mock_page_source()

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    content, log_entry = await scrape_single_url(mock_tab, "https://test.com", "corporate", mock_company.id)

    assert content == "<html>Hello World</html>"
    assert log_entry.status == "SUCCESS"
    assert log_entry.content_length == len(content)
    assert log_entry.company_id == mock_company.id
    assert log_entry.url == "https://test.com"

    mock_tab.enable_network_events.assert_called_once()
    mock_tab.go_to.assert_called_once_with("https://test.com", timeout=45)

    # Should not call execute_script for "corporate" category
    mock_tab.execute_script.assert_not_called()


async def test_scrape_single_url_failure(mocker, mock_company):
    mock_tab = AsyncMock()
    mock_tab.enable_network_events = AsyncMock()
    mock_tab.go_to = AsyncMock()
    mock_tab.execute_script = AsyncMock()
    mock_tab.go_to.side_effect = Exception("Page timeout")

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    content, log_entry = await scrape_single_url(mock_tab, "https://fail.com", "corporate", mock_company.id)

    assert content is None
    assert log_entry.status == "FAILED"
    assert log_entry.error_msg and "Page timeout" in log_entry.error_msg

    mock_tab.enable_network_events.assert_called_once()
    mock_tab.go_to.assert_called_once_with("https://fail.com", timeout=45)

    # Should not call execute_script for "corporate" category
    mock_tab.execute_script.assert_not_called()


async def test_get_browser_options():
    """Test browser options configuration"""
    options = get_browser_options()

    assert "--headless=new" in str(options._arguments)
    assert "--no-sandbox" in str(options._arguments)
    assert "--disable-dev-shm-usage" in str(options._arguments)


async def test_scrape_discovered_urls_success(mocker, db_session: AsyncSession):
    company = Company(name="Scraping Test Corp")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    discovered_urls = {
        "corporate": {"https://testcorp.com"},
        "reports": {"https://testcorp.com/reports"},
        "linkedin": {"https://linkedin.com/company/testcorp"},
        "instagram": set(),
        "twitter": set(),
        "facebook": set(),
        "news": set(),
    }

    mock_content_map = {
        "https://testcorp.com": "<html>Corporate content</html>",
        "https://testcorp.com/reports": "<html>Reports content</html>",
        "https://linkedin.com/company/testcorp": "<html>LinkedIn content</html>",
    }

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    async def mock_scrape_single_url(_tab, url, _category, company_id):
        content = mock_content_map.get(url, "<html>Default content</html>")
        log_entry = ScrapeLog(
            company_id=company_id,
            url=url,
            status="SUCCESS",
            scraped_at=datetime.now(timezone.utc),
            content_length=len(content),
        )
        return content, log_entry

    with (
        patch("app.services.scraping.Chrome") as mock_chrome_class,
        patch("app.services.scraping.scrape_single_url", new_callable=AsyncMock) as mock_scrape_single,
        patch("asyncio.gather", new_callable=AsyncMock) as mock_gather,
    ):

        mock_browser = AsyncMock()
        mock_tab = AsyncMock()
        mock_browser.new_tab.return_value = mock_tab
        mock_chrome_class.return_value.__aenter__.return_value = mock_browser
        mock_chrome_class.return_value.__aexit__ = AsyncMock()

        mock_scrape_single.side_effect = mock_scrape_single_url

        # Mock gather to execute coroutines
        async def mock_gather_side_effect(*coroutines):
            results = []
            for coro in coroutines:
                if hasattr(coro, "__await__"):
                    results.append(await coro)
            return results

        mock_gather.side_effect = mock_gather_side_effect

        scraped_content = await scrape_discovered_urls(discovered_urls, company, db_session)

        assert len(scraped_content) == 3

        for item in scraped_content:
            assert "url" in item
            assert "category" in item
            assert "content" in item
            assert item["url"] in mock_content_map
            assert item["content"] == mock_content_map[item["url"]]


async def test_discover_company_resources_success(mocker, db_session: AsyncSession):
    company = Company(name="Discovery Test Corp")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    mock_search_results = [
        {"title": "Discovery Test Corp LinkedIn", "url": "https://linkedin.com/company/discovery-test"},
        {"title": "Discovery Test Corp Site", "url": "https://discoverytest.com"},
    ]

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    with (
        patch("app.services.discovery.duckduckgo_search", new_callable=AsyncMock) as mock_search,
        patch("app.services.discovery.Chrome") as mock_chrome_class,
        patch("asyncio.gather", new_callable=AsyncMock) as mock_gather,
    ):

        mock_browser = AsyncMock()
        mock_chrome_class.return_value.__aenter__.return_value = mock_browser
        mock_chrome_class.return_value.__aexit__ = AsyncMock()

        mock_search.return_value = mock_search_results

        # Mock gather to execute coroutines
        async def mock_gather_side_effect(*coroutines):
            results = []
            for coro in coroutines:
                if hasattr(coro, "__await__"):
                    results.append(await coro)
            return results

        mock_gather.side_effect = mock_gather_side_effect

        result = await discover_company_resources(company, db_session)

        assert isinstance(result, dict)
        expected_categories = ["corporate", "linkedin", "instagram", "twitter", "facebook", "news", "reports"]
        for category in expected_categories:
            assert category in result
