"""
Bot Omie - Upsert Handler: Contas a Pagar
==========================================

Handles database persistence for omie.a_pagar table (PostgreSQL).
Schema is dynamically created based on first data load if table doesn't exist.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from db.db import get_conn, release_conn, SCHEMA
from utils import arquivar_arquivo

from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

TABLE_NAME = "a_pagar"
ARCHIVE_NAME = "A PAGAR"


def _map_dtype_to_pg(df, col):
    """Maps a pandas column dtype to a PostgreSQL type."""
    dtype = df[col].dtype
    if pd.api.types.is_integer_dtype(dtype):
        return "BIGINT"
    elif pd.api.types.is_float_dtype(dtype):
        return "NUMERIC(15,2)"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "TIMESTAMP"
    else:
        max_len = df[col].astype(str).str.len().max()
        if max_len > 255:
            return "TEXT"
        return f"VARCHAR({min(max(50, int(max_len * 1.5)), 500)})"


def _convert_value(val):
    """Converts a pandas value to a psycopg2-compatible Python type."""
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return Decimal(str(val))
    if isinstance(val, (datetime, pd.Timestamp)):
        return val
    return val


def create_table_from_dataframe(df: pd.DataFrame, conn) -> str:
    """
    Dynamically creates table in PostgreSQL based on DataFrame columns.
    No-op if the table already exists (CREATE TABLE IF NOT EXISTS).
    """
    columns_sql = ["id SERIAL PRIMARY KEY"]

    for col in df.columns:
        sql_type = _map_dtype_to_pg(df, col)
        columns_sql.append(f'"{col}" {sql_type}')

    columns_sql.append("created_at TIMESTAMPTZ DEFAULT NOW()")
    columns_sql.append("updated_at TIMESTAMPTZ DEFAULT NOW()")

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{TABLE_NAME} (
        {', '.join(columns_sql)}
    );
    """

    cursor = conn.cursor()
    cursor.execute(create_sql)

    # Trigger for auto-updating updated_at on UPDATE
    cursor.execute(f"""
        DROP TRIGGER IF EXISTS trg_updated_at ON {SCHEMA}.{TABLE_NAME};
        CREATE TRIGGER trg_updated_at
            BEFORE UPDATE ON {SCHEMA}.{TABLE_NAME}
            FOR EACH ROW
            EXECUTE FUNCTION {SCHEMA}.set_updated_at();
    """)

    conn.commit()
    cursor.close()

    logger.info(f"Table {SCHEMA}.{TABLE_NAME} created/verified with {len(df.columns)} data columns")
    return create_sql


def upsert_data(df: pd.DataFrame, csv_path: str = None) -> int:
    """
    Bulk inserts DataFrame data into omie.a_pagar using execute_values.

    Args:
        df: Pandas DataFrame with processed data
        csv_path: Original file path (for archiving)

    Returns:
        int: Number of rows affected
    """
    conn = get_conn()
    cursor = None

    try:
        create_table_from_dataframe(df, conn)

        cursor = conn.cursor()

        columns = df.columns.tolist()
        columns_str = ', '.join([f'"{col}"' for col in columns])

        insert_sql = f"""
        INSERT INTO {SCHEMA}.{TABLE_NAME} ({columns_str})
        VALUES %s
        """

        # Prepare data tuples with type conversion
        data = [
            tuple(_convert_value(val) for val in row.values)
            for _, row in df.iterrows()
        ]

        execute_values(cursor, insert_sql, data, page_size=1000)
        rows_affected = cursor.rowcount

        conn.commit()
        logger.info(f"Inserted {rows_affected} rows into {SCHEMA}.{TABLE_NAME}")

        if csv_path and os.path.exists(csv_path):
            arquivar_arquivo(csv_path, ARCHIVE_NAME)

        return rows_affected

    except Exception as e:
        logger.error(f"Error in upsert_data: {e}")
        conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        release_conn(conn)


if __name__ == "__main__":
    print(f"Upsert handler for {SCHEMA}.{TABLE_NAME}")
