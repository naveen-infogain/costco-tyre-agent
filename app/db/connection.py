"""
Module: connection.py
Purpose: PostgreSQL connection pool — single shared pool for the whole app.
Layer: db

Dependencies:
  - psycopg2-binary: PostgreSQL driver
  - python-dotenv: reads DB_* vars from .env

Swap points:
  - Replace SimpleConnectionPool with AsyncConnectionPool (psycopg3) for full async.
  - Replace with DATABASE_URL (single env var) for cloud deployments (Heroku, Railway).

Usage:
    from app.db.connection import get_conn, release_conn, db_available

    if db_available():
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
                rows = cur.fetchall()
        finally:
            release_conn(conn)
"""
from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)

_pool = None
_db_available = False


def _init_pool() -> None:
    global _pool, _db_available
    try:
        import psycopg2
        from psycopg2 import pool as pg_pool

        _pool = pg_pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 5432)),
            dbname=os.environ.get("DB_NAME", "costco_tyre"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "postgres"),
        )
        # quick probe
        conn = _pool.getconn()
        _pool.putconn(conn)
        _db_available = True
        logger.info("PostgreSQL connection pool initialised (%s/%s)",
                    os.environ.get("DB_HOST"), os.environ.get("DB_NAME"))
    except Exception as e:
        _db_available = False
        logger.warning("PostgreSQL unavailable — falling back to JSON files. (%s)", e)


def db_available() -> bool:
    """Return True if the DB pool is initialised and healthy."""
    global _db_available
    if _pool is None:
        _init_pool()
    return _db_available


def get_conn():
    """Borrow a connection from the pool. Must be released with release_conn()."""
    if _pool is None:
        _init_pool()
    return _pool.getconn()


def release_conn(conn) -> None:
    """Return a connection to the pool."""
    if _pool and conn:
        _pool.putconn(conn)
