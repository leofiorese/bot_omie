"""
Bot Omie - Upsert Handler: Notas Debito
========================================

Handles database persistence for OMIE_NOTAS_DEBITO table.
Schema is dynamically created based on first data load.
"""

import logging
import pandas as pd
from datetime import datetime
import sys
import os

# Add parent paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from db.db import get_conn
from utils import arquivar_arquivo

logger = logging.getLogger(__name__)

TABLE_NAME = "NOTAS_DEBITO"

# Placeholder columns - will be updated after first XLSX inspection
TABLE_COLUMNS = [
    'id',
    'numero_nota',
    'cliente',
    'data_emissao',
    'valor',
    'status',
    'observacao'
]


def create_table_from_dataframe(df: pd.DataFrame, conn) -> str:
    """
    Dynamically creates table based on DataFrame columns.
    """
    columns_sql = []
    columns_sql.append("`id` INT AUTO_INCREMENT PRIMARY KEY")
    
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            sql_type = "BIGINT"
        elif pd.api.types.is_float_dtype(dtype):
            sql_type = "DECIMAL(15,2)"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            sql_type = "DATETIME"
        else:
            max_len = df[col].astype(str).str.len().max()
            if max_len > 255:
                sql_type = "TEXT"
            else:
                sql_type = f"VARCHAR({min(max(50, int(max_len * 1.5)), 500)})"
        
        columns_sql.append(f"`{col}` {sql_type}")
    
    columns_sql.append("`created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    columns_sql.append("`updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
        {', '.join(columns_sql)}
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    cursor = conn.cursor()
    cursor.execute(create_sql)
    conn.commit()
    cursor.close()
    
    logger.info(f"Table {TABLE_NAME} created/verified with {len(df.columns)} columns")
    return create_sql


def upsert_data(df: pd.DataFrame, csv_path: str = None) -> int:
    """
    Upserts DataFrame data into OMIE_NOTAS_DEBITO table.
    
    Args:
        df: Pandas DataFrame with processed data
        csv_path: Original file path (for archiving)
    
    Returns:
        int: Number of rows affected
    """
    conn = get_conn()
    
    try:
        create_table_from_dataframe(df, conn)
        
        cursor = conn.cursor()
        
        columns = df.columns.tolist()
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join([f'`{col}`' for col in columns])
        update_parts = ', '.join([f'`{col}` = VALUES(`{col}`)' for col in columns])
        
        insert_sql = f"""
        INSERT INTO `{TABLE_NAME}` ({columns_str})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_parts}
        """
        
        rows_affected = 0
        
        for idx, row in df.iterrows():
            try:
                values = []
                for val in row.values:
                    if pd.isna(val):
                        values.append(None)
                    elif isinstance(val, datetime):
                        values.append(val.strftime('%Y-%m-%d %H:%M:%S'))
                    else:
                        values.append(val)
                
                cursor.execute(insert_sql, tuple(values))
                rows_affected += cursor.rowcount
                
            except Exception as e:
                logger.warning(f"Error inserting row {idx}: {e}")
                continue
        
        conn.commit()
        logger.info(f"Upserted {rows_affected} rows into {TABLE_NAME}")
        
        if csv_path and os.path.exists(csv_path):
            arquivar_arquivo(csv_path, TABLE_NAME)
        
        return rows_affected
        
    except Exception as e:
        logger.error(f"Error in upsert_data: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print(f"Upsert handler for {TABLE_NAME}")
