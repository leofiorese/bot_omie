"""
Bot Omie - PostgreSQL Database Connection Module
=================================================

Provides thread-safe connection pool for PostgreSQL.
Uses schema 'omie' for all bot tables.
"""

import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import Error
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('omie_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SCHEMA = "omie"

_pool = None


def _get_pool():
    """Returns the connection pool, creating it lazily if needed."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = ThreadedConnectionPool(
            minconn=int(os.getenv('DB_POOL_MIN', 2)),
            maxconn=int(os.getenv('DB_POOL_MAX', 5)),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 5432)),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        logger.info("Connection pool created successfully.")
        _init_schema()
    return _pool


def _init_schema():
    """Creates the schema and trigger function if they don't exist."""
    conn = _pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        cursor.execute(f"""
            CREATE OR REPLACE FUNCTION {SCHEMA}.set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        cursor.close()
        logger.info(f"Schema '{SCHEMA}' and trigger function verified/created.")
    except Error as e:
        conn.rollback()
        logger.error(f"Error initializing schema: {e}")
        raise
    finally:
        _pool.putconn(conn)


def get_conn():
    """
    Returns a PostgreSQL connection from the pool.

    Returns:
        psycopg2 connection object
    """
    pool = _get_pool()
    conn = pool.getconn()
    logger.info("Database connection acquired from pool.")
    return conn


def release_conn(conn):
    """
    Returns a connection to the pool.

    Args:
        conn: psycopg2 connection object
    """
    pool = _get_pool()
    pool.putconn(conn)
    logger.info("Database connection released to pool.")


if __name__ == "__main__":
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    print(f"Connection successful! Result: {cursor.fetchone()}")
    cursor.close()
    release_conn(conn)
