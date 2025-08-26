from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UsageLogDetail(BaseModel):
    """Pydantic model for individual usage log details."""

    model_config = ConfigDict(from_attributes=True)

    company_name: str | None = Field(description="Name of the company associated with the usage.")
    operation_type: str = Field(description="Type of operation performed.")
    tokens_used: int = Field(description="Tokens consumed by the operation.")
    timestamp: datetime = Field(description="Timestamp of the operation.")


class TodayUsageResponse(BaseModel):
    """Pydantic model for the complete daily usage report."""

    total_tokens_today: int = Field(description="Total tokens consumed today.")
    details: list[UsageLogDetail] = Field(description="List of all token consumption events for the day.")
