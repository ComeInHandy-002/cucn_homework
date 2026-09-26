"""SQLAlchemy database setup with SQLite/PostgreSQL compatibility."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models here so metadata is populated before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_danger_zone_coordinate_space()


def _migrate_danger_zone_coordinate_space() -> None:
    """Convert legacy zone rows that were saved in workbench canvas pixels.

    Zones created before relative coordinates existed were drawn on the
    fixed 720x405 workbench canvas; they are converted to 0-1 fractions
    exactly once, when the coordinate_space column is first added.
    """

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "danger_zones" not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns("danger_zones")}
    if "coordinate_space" in column_names:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE danger_zones ADD COLUMN coordinate_space VARCHAR(20) DEFAULT 'pixel'"))
    # Lazy import: models must not be imported before metadata setup above.
    from .models import DangerZoneRecord

    db = SessionLocal()
    try:
        for record in db.query(DangerZoneRecord).all():
            if record.coordinate_space == "relative":
                continue
            record.polygon = [
                {
                    "x": round(min(max(float(point["x"]) / 720.0, 0.0), 1.0), 6),
                    "y": round(min(max(float(point["y"]) / 405.0, 0.0), 1.0), 6),
                }
                for point in (record.polygon or [])
            ]
            record.coordinate_space = "relative"
        db.commit()
    finally:
        db.close()
