from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc)
    )

    company_links: Mapped[list["CompanyLink"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    search_results: Mapped[list["SearchResult"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    scrape_logs: Mapped[list["ScrapeLog"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    aum_snapshots: Mapped[list["AUMSnapshot"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    usage_logs: Mapped[list["Usage"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company(name='{self.name}')>"


class CompanyLink(Base):
    __tablename__ = "company_links"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    company: Mapped["Company"] = relationship(back_populates="company_links")


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    query: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    company: Mapped["Company"] = relationship(back_populates="search_results")

    def __repr__(self):
        return f"<SearchResult(company='{self.company.name}', title='{self.title}', query='{self.query}', url='{self.url}')>"


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    url: Mapped[str]
    status: Mapped[str]
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    content_length: Mapped[int]
    error_msg: Mapped[str | None]

    company: Mapped["Company"] = relationship(back_populates="scrape_logs")


class AUMSnapshot(Base):
    __tablename__ = "aum_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    aum_value: Mapped[str] = mapped_column(String)  # Raw value, ex: "2,3 bi"
    aum_unit: Mapped[str | None] = mapped_column(String)  # Currency/unit, ex: "R$"
    standardized_value: Mapped[int | None] = mapped_column(BigInteger)  # Decimal value, ex: 2300000000
    source_url: Mapped[str | None] = mapped_column(String, index=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    company: Mapped["Company"] = relationship(back_populates="aum_snapshots")


class Usage(Base):
    __tablename__ = "usage"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    operation_type: Mapped[str] = mapped_column(String, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    company: Mapped[Company | None] = relationship(back_populates="usage_logs")
