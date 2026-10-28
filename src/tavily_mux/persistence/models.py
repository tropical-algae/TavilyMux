from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from tavily_mux.common.time import utc_now
from tavily_mux.persistence.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class AdminCredential(TimestampMixin, Base):
    __tablename__ = "admin_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SystemSettings(TimestampMixin, Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    upstream_base_url: Mapped[str] = mapped_column(
        String(500), nullable=False, default="https://api.tavily.com"
    )
    http_proxy_encrypted: Mapped[str | None] = mapped_column(Text)
    https_proxy_encrypted: Mapped[str | None] = mapped_column(Text)
    allow_direct_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    monitor_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    request_timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    log_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)


class Pool(TimestampMixin, Base):
    __tablename__ = "pools"
    __table_args__ = (Index("ix_pools_name", "name", unique=True),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="max_remaining")
    monitor_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    max_attempts: Mapped[int | None] = mapped_column(Integer)
    concurrency_limit: Mapped[int | None] = mapped_column(Integer)
    rpm_limit: Mapped[int | None] = mapped_column(Integer)
    upstream_base_url: Mapped[str | None] = mapped_column(String(500))
    http_proxy_encrypted: Mapped[str | None] = mapped_column(Text)
    https_proxy_encrypted: Mapped[str | None] = mapped_column(Text)
    allow_direct_fallback: Mapped[bool | None] = mapped_column(Boolean)


class RelayKey(TimestampMixin, Base):
    __tablename__ = "relay_keys"
    __table_args__ = (Index("ix_relay_keys_pool", "pool_id", "enabled"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    pool_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pools.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TavilyKey(TimestampMixin, Base):
    __tablename__ = "tavily_keys"
    __table_args__ = (
        Index("ix_tavily_keys_pool_status", "pool_id", "enabled", "status"),
        Index("ix_tavily_keys_fingerprint", "fingerprint", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    pool_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pools.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    usage: Mapped[int | None] = mapped_column(Integer)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    account_plan: Mapped[str | None] = mapped_column(String(100))
    account_plan_usage: Mapped[int | None] = mapped_column(Integer)
    account_plan_limit: Mapped[int | None] = mapped_column(Integer)
    paygo_usage: Mapped[int | None] = mapped_column(Integer)
    paygo_limit: Mapped[int | None] = mapped_column(Integer)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class UsageSnapshot(Base):
    __tablename__ = "usage_snapshots"
    __table_args__ = (Index("ix_usage_snapshots_key_time", "key_id", "captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tavily_keys.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    usage: Mapped[int | None] = mapped_column(Integer)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    account_plan_usage: Mapped[int | None] = mapped_column(Integer)
    account_plan_limit: Mapped[int | None] = mapped_column(Integer)
    paygo_usage: Mapped[int | None] = mapped_column(Integer)
    paygo_limit: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class ProxyRequest(Base):
    __tablename__ = "proxy_requests"
    __table_args__ = (
        Index("ix_proxy_requests_pool_time", "pool_id", "created_at"),
        Index("ix_proxy_requests_status_time", "status_code", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pool_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("pools.id", ondelete="SET NULL")
    )
    final_key_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("tavily_keys.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_code: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credits: Mapped[int | None] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(String(100))
    external_request_id: Mapped[str | None] = mapped_column(String(200))


class ProxyAttempt(Base):
    __tablename__ = "proxy_attempts"
    __table_args__ = (Index("ix_proxy_attempts_request", "request_id", "attempt_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("proxy_requests.id", ondelete="CASCADE"), nullable=False
    )
    key_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("tavily_keys.id", ondelete="SET NULL")
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error_type: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
