from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.db.models import AUMSnapshot, Company, Usage
from app.utils.extraction import extract_relevant_chunks
from app.utils.normalization import normalize_aum_value
from app.workers.tasks import process_company


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("R$ 2,3 bi", 2.3e9),
        ("$500 million", 500e6),
        ("1.5 trilhão", 1.5e12),
        ("US$ 100,5 mil", 100.5e3),
        ("€ 123.456,78", 123456.78),
        ("25b", 25e9),
        ("Invalid Text", None),
    ],
)
def test_normalize_aum_value(raw_value, expected):
    assert normalize_aum_value(raw_value) == expected


def test_extract_relevant_chunks_finds_keywords():
    html_content = """
    <html><body>
        <p>Some random text here.</p>
        <span>Nosso patrimônio sob gestão é de R$ 5 bi.</span>
        <p>Another paragraph without info.</p>
        <span>Assets under management: $10 Billion</span>
    </body></html>
    """
    expected_text = "Nosso patrimônio sob gestão é de R$ 5 bi.\nAssets under management: $10 Billion"
    result = extract_relevant_chunks(html_content)
    assert result == expected_text


def test_extract_relevant_chunks_respects_token_limit(mocker):
    mocker.patch("app.utils.extraction.encoding.encode", return_value=[0] * 500)

    html_content = """
    <html><body>
        <p>AUM: 1 bilhão</p> <p>AUM: 2 bilhões</p> <p>AUM: 3 bilhões</p> </body></html>
    """

    result = extract_relevant_chunks(html_content)

    assert "1 bilhão" in result
    assert "2 bilhões" in result
    assert "3 bilhões" not in result


@pytest.mark.asyncio
async def test_process_company_flow(db_session, mocker):
    company = Company(name="Flow Test Corp")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    company_id = company.id

    mocker.patch(
        "app.services.discovery.discover_company_resources",
        return_value={"corporate": {"https://fake.url/report"}},
    )

    mocker.patch(
        "app.services.scraping.scrape_discovered_urls",
        return_value=[{"url": "https://fake.url/report", "content": "<html>AUM é R$ 500 milhões</html>"}],
    )

    mock_ai_response = MagicMock()
    mock_ai_response.get_content_as_string.return_value = "R$ 500 milhões\n\nFonte: https://fake.url/report"
    mock_ai_response.metrics = {"total_tokens": [125]}
    mocker.patch("app.workers.agent.AIExtractionAgent.arun", new_callable=AsyncMock, return_value=mock_ai_response)

    await process_company(company_id, db_session)

    aum_result = await db_session.execute(select(AUMSnapshot).where(AUMSnapshot.company_id == company_id))
    snapshot = aum_result.scalar_one_or_none()
    assert snapshot is not None
    assert snapshot.aum_value == "R$ 500 milhões"
    assert snapshot.standardized_value == 500_000_000
    assert snapshot.source_url == "https://fake.url/report"

    usage_result = await db_session.execute(select(Usage).where(Usage.company_id == company_id))
    usage_log = usage_result.scalar_one_or_none()
    assert usage_log is not None
    assert usage_log.tokens_used == 125
    assert usage_log.operation_type == "aum_extraction"
