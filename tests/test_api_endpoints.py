import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import AUMSnapshot, Base, Company, Usage

pytestmark = pytest.mark.asyncio


async def test_upload_csv_and_dispatch_task(api_client: AsyncClient, db_session: AsyncSession, mocker):
    mock_delay = mocker.patch("app.workers.tasks.process_company_task.delay")

    csv_content = "Empresa\nMock Company"
    files = {"file": ("companies.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")}

    response = await api_client.post("/api/v1/scraping/start", files=files)

    assert response.status_code == 200
    assert response.json() == {"message": "1 new companies have been queued for processing."}

    result = await db_session.execute(select(Company).where(Company.name == "Mock Company"))
    company = result.scalar_one_or_none()
    assert company is not None

    mock_delay.assert_called_once_with(company.id)


async def test_upload_csv_skips_existing_company(api_client: AsyncClient, db_session: AsyncSession, mocker):
    existing_company = Company(name="Existing Corp")
    db_session.add(existing_company)
    await db_session.commit()

    mock_delay = mocker.patch("app.workers.tasks.process_company_task.delay")

    csv_content = "Empresa\nExisting Corp"
    files = {"file": ("companies.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")}

    response = await api_client.post("/api/v1/scraping/start", files=files)

    assert response.status_code == 200
    assert response.json() == {"message": "0 new companies have been queued for processing."}
    mock_delay.assert_not_called()


async def test_restart_processing_success(api_client: AsyncClient, db_session: AsyncSession, mocker):
    company = Company(name="Test Restart")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    mock_delay = mocker.patch("app.workers.tasks.process_company_task.delay")

    response = await api_client.post(f"/api/v1/scraping/re-scrape?company_id={company.id}")

    assert response.status_code == 200
    assert response.json() == {"message": f"Reprocessing for '{company.name}' has been queued."}
    mock_delay.assert_called_once_with(company.id)


async def test_restart_processing_not_found(api_client: AsyncClient):
    response = await api_client.post("/api/v1/scraping/re-scrape?company_id=999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Company not found"}


async def test_restart_processing_bad_request(api_client: AsyncClient):
    response = await api_client.post("/api/v1/scraping/re-scrape")
    assert response.status_code == 400
    assert response.json() == {"detail": "Either company_id or company_name must be provided"}

    response = await api_client.post("/api/v1/scraping/re-scrape?company_id=1&company_name=Test")
    assert response.status_code == 400
    assert response.json() == {"detail": "Provide either company_id or company_name, not both"}


async def test_export_csv_with_data(api_client: AsyncClient, db_session: AsyncSession):
    company = Company(name="CSV Test Corp")
    db_session.add(company)
    await db_session.flush()

    snapshot = AUMSnapshot(
        company_id=company.id,
        aum_value="R$ 10 bi",
        aum_unit="R$",
        standardized_value=10_000_000_000,
        source_url="https://csv.com/report",
    )
    db_session.add(snapshot)
    await db_session.commit()

    response = await api_client.get("/api/v1/results/export-csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=aum_report.csv" in response.headers["content-disposition"]

    reader = csv.DictReader(StringIO(response.content.decode("utf-8")))
    for row in reader:
        name = row.get("Empresa")
        source_url = row.get("Source URL")
        value = row.get("Standardized Value")

        assert name == "CSV Test Corp"
        assert source_url == "https://csv.com/report"
        assert value == "10000000000"


async def test_export_csv_no_data(api_client: AsyncClient, db_session: AsyncSession):
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(table.delete())

    response = await api_client.get("/api/v1/results/export-csv")
    assert response.status_code == 404


async def test_get_today_usage_details_with_data(api_client: AsyncClient, db_session: AsyncSession):
    company = Company(name="Usage Test Corp")
    db_session.add(company)
    await db_session.flush()

    usage1 = Usage(
        company_id=company.id,
        operation_type="aum_extraction",
        tokens_used=1500,
        timestamp=datetime.now(timezone.utc),
    )
    usage2 = Usage(
        company_id=None,  # Test a log without a linked company
        operation_type="discovery",
        tokens_used=500,
        timestamp=datetime.now(timezone.utc),
    )
    db_session.add_all([usage1, usage2])
    await db_session.commit()

    response = await api_client.get("/api/v1/usage/today")

    assert response.status_code == 200
    data = response.json()

    assert data["total_tokens_today"] == 2000
    assert len(data["details"]) == 2

    extraction_log = next((item for item in data["details"] if item["operation_type"] == "aum_extraction"), None)
    discovery_log = next((item for item in data["details"] if item["operation_type"] == "discovery"), None)

    assert extraction_log is not None
    assert extraction_log["company_name"] == "Usage Test Corp"
    assert extraction_log["tokens_used"] == 1500

    assert discovery_log is not None
    assert discovery_log["company_name"] is None
    assert discovery_log["tokens_used"] == 500


async def test_get_today_usage_details_no_data(api_client: AsyncClient, db_session: AsyncSession):
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(table.delete())

    response = await api_client.get("/api/v1/usage/today")

    assert response.status_code == 200
    data = response.json()
    assert data["total_tokens_today"] == 0
    assert data["details"] == []


async def test_restart_processing_by_name_not_found(api_client: AsyncClient):
    response = await api_client.post("/api/v1/scraping/re-scrape?company_name=NonExistent")
    assert response.status_code == 404
