"""Persistence models for users, cameras, jobs and safety events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(30), default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    source: Mapped[str] = mapped_column(String(500), default="local")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    zones: Mapped[list["DangerZoneRecord"]] = relationship(back_populates="camera", cascade="all, delete-orphan")


class DangerZoneRecord(Base):
    __tablename__ = "danger_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="Danger zone")
    polygon: Mapped[list[dict[str, float]]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    camera: Mapped[Camera | None] = relationship(back_populates="zones")


class InferenceJobRecord(Base):
    __tablename__ = "inference_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_type: Mapped[str] = mapped_column(String(20), index=True)
    source_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    result_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    camera_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class SafetyEventRecord(Base):
    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    camera_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    evidence_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    zone_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
