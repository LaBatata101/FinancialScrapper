import csv
from datetime import datetime, time, timezone
from io import StringIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import get_async_db
from app.db.models import AUMSnapshot, Company, Usage
from app.services.reporting import generate_csv_report
from app.workers.tasks import process_company_task

from .schemas import TodayUsageResponse, UsageLogDetail

router = APIRouter()


@router.post("/scraping/start")
async def upload_companies_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_async_db)):
    contents = await file.read()
    decoded_contents = contents.decode("utf-8")

    reader = csv.DictReader(StringIO(decoded_contents))
    tasks_dispatched = 0

    for row in reader:
        name = row.get("Empresa")
        if not name:
            continue

        existing_company = await db.execute(select(Company).where(Company.name == name))
        if not existing_company.scalar_one_or_none():
            company = Company(name=name)
            db.add(company)
            await db.commit()
            await db.refresh(company)

            process_company_task.delay(company.id)
            tasks_dispatched += 1

    return {"message": f"{tasks_dispatched} new companies have been queued for processing."}


@router.post("/scraping/re-scrape")
async def restart_processing(
    company_id: int | None = None, company_name: str | None = None, db: AsyncSession = Depends(get_async_db)
):
    """Manually trigger reprocessing for a specific company."""
    if not company_id and not company_name:
        raise HTTPException(status_code=400, detail="Either company_id or company_name must be provided")

    if company_id and company_name:
        raise HTTPException(status_code=400, detail="Provide either company_id or company_name, not both")

    if company_id:
        company = await db.get(Company, company_id)
    else:
        company = await db.execute(select(Company).where(Company.name == company_name))
        company = company.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    process_company_task.delay(company.id)
    return {"message": f"Reprocessing for '{company.name}' has been queued."}


@router.get("/results/export-csv")
async def export_results_to_csv(db: AsyncSession = Depends(get_async_db)):
    """Export all AUM results to a CSV file."""
    stmt = select(AUMSnapshot).options(selectinload(AUMSnapshot.company))
    snapshots = list((await db.scalars(stmt)).all())

    if not snapshots:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No AUM results found for export.")

    csv_file = await generate_csv_report(snapshots)

    return StreamingResponse(
        csv_file,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=aum_report.csv"},
    )


@router.get("/usage/today", response_model=TodayUsageResponse)
async def get_today_usage_details(db: AsyncSession = Depends(get_async_db)):
    """
    Returns details of executions and token consumption for the current day (UTC).
    """
    today_start = datetime.combine(datetime.now(timezone.utc), time.min)
    today_end = datetime.combine(datetime.now(timezone.utc), time.max)

    stmt = (
        select(Usage)
        .options(selectinload(Usage.company))
        .where(Usage.timestamp.between(today_start, today_end))
        .order_by(Usage.timestamp.desc())
    )
    result = await db.execute(stmt)
    usage_logs = result.scalars().all()

    total_tokens = sum(log.tokens_used for log in usage_logs)

    detailed_logs = [
        UsageLogDetail(
            company_name=log.company.name if log.company else None,
            operation_type=log.operation_type,
            tokens_used=log.tokens_used,
            timestamp=log.timestamp,
        )
        for log in usage_logs
    ]

    return TodayUsageResponse(total_tokens_today=total_tokens, details=detailed_logs)
