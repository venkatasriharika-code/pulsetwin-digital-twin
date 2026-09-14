from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sqlite_path() -> str:
    return os.getenv("PULSETWIN_SQLITE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "pulsetwin.db"))


@contextmanager
def connection() -> Iterator[Any]:
    if DATABASE_URL.startswith("postgres"):
        try:
            import psycopg
            conn = psycopg.connect(DATABASE_URL)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
            return
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL is PostgreSQL but psycopg is not installed") from exc
    conn = sqlite3.connect(_sqlite_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _placeholder() -> str:
    return "%s" if DATABASE_URL.startswith("postgres") else "?"


def init_db() -> None:
    ph = _placeholder()
    with connection() as conn:
        cur = conn.cursor()
        if DATABASE_URL.startswith("postgres"):
            cur.execute("CREATE TABLE IF NOT EXISTS hospital_config (id TEXT PRIMARY KEY, payload JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS scenarios (id TEXT PRIMARY KEY, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS recommendations (id TEXT PRIMARY KEY, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL)")
        else:
            cur.execute("CREATE TABLE IF NOT EXISTS hospital_config (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS scenarios (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS recommendations (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")


def save_config(payload: dict[str, Any]) -> dict[str, Any]:
    ph = _placeholder(); updated = _utc(); record = {**payload, "updatedAt": updated}
    with connection() as conn:
        cur = conn.cursor()
        if DATABASE_URL.startswith("postgres"):
            cur.execute(f"INSERT INTO hospital_config (id,payload,updated_at) VALUES ({ph},{ph},{ph}) ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload, updated_at=EXCLUDED.updated_at", ("default", json.dumps(record), updated))
        else:
            cur.execute(f"INSERT INTO hospital_config (id,payload,updated_at) VALUES ({ph},{ph},{ph}) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at", ("default", json.dumps(record), updated))
    return record


def load_config(default: dict[str, Any]) -> dict[str, Any]:
    init_db(); ph = _placeholder()
    with connection() as conn:
        cur = conn.cursor(); cur.execute(f"SELECT payload FROM hospital_config WHERE id={ph}", ("default",)); row = cur.fetchone()
    if not row:
        return save_config(default)
    payload = row[0] if not isinstance(row, sqlite3.Row) else row["payload"]
    return payload if isinstance(payload, dict) else json.loads(payload)


def save_scenario(payload: dict[str, Any]) -> None:
    ph = _placeholder(); created = _utc()
    with connection() as conn:
        conn.cursor().execute(f"INSERT INTO scenarios (id,payload,created_at) VALUES ({ph},{ph},{ph}) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (payload["id"], json.dumps(payload), created))


def save_decision(payload: dict[str, Any]) -> None:
    ph = _placeholder()
    with connection() as conn:
        conn.cursor().execute(f"INSERT INTO decisions (id,scenario_id,payload,created_at) VALUES ({ph},{ph},{ph},{ph})", (payload["id"], payload["scenarioId"], json.dumps(payload), payload["createdAt"]))


def list_decisions() -> list[dict[str, Any]]:
    init_db();
    with connection() as conn:
        rows = conn.cursor().execute("SELECT payload FROM decisions ORDER BY created_at DESC").fetchall()
    return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]


def save_alert(payload: dict[str, Any]) -> None:
    ph = _placeholder()
    with connection() as conn:
        conn.cursor().execute(f"INSERT INTO alerts (id,payload,created_at) VALUES ({ph},{ph},{ph}) ON CONFLICT(id) DO NOTHING", (payload["id"], json.dumps(payload), payload["createdAt"]))


def list_alerts(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with connection() as conn:
        rows = conn.cursor().execute(f"SELECT payload FROM alerts ORDER BY created_at DESC LIMIT {_placeholder()}", (limit,)).fetchall()
    return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]


def save_recommendation(payload: dict[str, Any]) -> None:
    ph = _placeholder()
    with connection() as conn:
        conn.cursor().execute(f"INSERT INTO recommendations (id,payload,created_at) VALUES ({ph},{ph},{ph}) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (payload["id"], json.dumps(payload), payload["createdAt"]))


def list_recommendations(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with connection() as conn:
        rows = conn.cursor().execute(f"SELECT payload FROM recommendations ORDER BY created_at DESC LIMIT {_placeholder()}", (limit,)).fetchall()
    return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"
