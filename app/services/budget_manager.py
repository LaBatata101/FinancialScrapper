import logging
from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Usage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BudgetManager:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_today_usage(self) -> int:
        """Calcula o total de tokens usados hoje (UTC)."""
        today_start = datetime.combine(datetime.now(timezone.utc), time.min)
        today_end = datetime.combine(datetime.now(timezone.utc), time.max)

        result = await self.db.execute(
            select(func.sum(Usage.tokens_used)).where(Usage.timestamp.between(today_start, today_end))
        )
        total_tokens = result.scalar_one_or_none() or 0
        return total_tokens

    async def log_usage(self, company_id: int, operation: str, tokens: int):
        """Registra um novo uso de tokens no banco de dados."""
        usage_log = Usage(company_id=company_id, operation_type=operation, tokens_used=tokens)
        self.db.add(usage_log)
        await self.db.commit()
        logger.info(f"Uso registrado para empresa {company_id}: {tokens} tokens para '{operation}'.")
