"""
Bot Omie - Excel Processing Module
===================================

Reads and processes XLSX files downloaded from Omie ERP.
Uses openpyxl as pandas engine for Excel reading.
"""

import pandas as pd
import logging
import re

logger = logging.getLogger(__name__)


def normalize_column_name(col_name: str) -> str:
    """
    Converts column names to snake_case for MySQL compatibility.
    
    Examples:
        "Nome do Cliente" -> "nome_do_cliente"
        "Data Vencimento" -> "data_vencimento"
        "Valor (R$)" -> "valor_r"
    
    Args:
        col_name: Original column name
    
    Returns:
        str: Normalized column name in snake_case
    """
    if not isinstance(col_name, str):
        col_name = str(col_name)
    
    # User requested EXACT match with Excel headers
    # Only stripping whitespace to avoid invisible character issues
    return col_name.strip()


def find_header_row(filepath: str, max_rows: int = 10) -> int:
    """
    Dynamically finds the header row in Excel files.
    Omie exports may have metadata rows before the actual data.
    
    Args:
        filepath: Path to the Excel file
        max_rows: Maximum rows to search for header
    
    Returns:
        int: Row number where headers are located (0-indexed)
    """
    try:
        # Read first few rows without header
        df_preview = pd.read_excel(filepath, engine='openpyxl', header=None, nrows=max_rows)
        
        # Find the row with the most non-null string values (likely the header)
        best_row = 0
        best_score = 0
        
        for idx in range(len(df_preview)):
            row = df_preview.iloc[idx]
            # Count non-null values that are strings
            score = sum(1 for val in row if isinstance(val, str) and len(str(val).strip()) > 0)
            if score > best_score:
                best_score = score
                best_row = idx
        
        logger.info(f"Header row detected at index {best_row}")
        return best_row
        
    except Exception as e:
        logger.warning(f"Could not detect header row, defaulting to 0: {e}")
        return 0


def process_excel(filepath: str, skip_header_detection: bool = False, skiprows: int = 0) -> pd.DataFrame:
    """
    Reads an Excel file and returns a cleaned DataFrame.
    
    Features:
    - Dynamic header row detection (skips metadata rows)
    - Column normalization to snake_case
    - NaN handling
    
    Args:
        filepath: Path to the Excel file
        skip_header_detection: If True, skips automatic header detection
        skiprows: Number of rows to skip (used if skip_header_detection=True)
    
    Returns:
        pd.DataFrame: Processed DataFrame with normalized columns
    """
    try:
        logger.info(f"Processing Excel file: {filepath}")
        
        # Determine header row
        if skip_header_detection:
            header_row = skiprows
        else:
            header_row = find_header_row(filepath)
        
        # Read Excel file
        df = pd.read_excel(
            filepath,
            engine='openpyxl',
            header=header_row
        )
        
        logger.info(f"Read {len(df)} rows and {len(df.columns)} columns")
        
        # Normalize column names
        original_columns = df.columns.tolist()
        df.columns = [normalize_column_name(col) for col in df.columns]
        
        # Log column mapping
        for orig, norm in zip(original_columns, df.columns):
            if orig != norm:
                logger.debug(f"Column renamed: '{orig}' -> '{norm}'")
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Remove completely empty columns
        df = df.dropna(axis=1, how='all')
        
        logger.info(f"After cleanup: {len(df)} rows and {len(df.columns)} columns")
        logger.info(f"Columns: {df.columns.tolist()}")
        
        return df
        
    except FileNotFoundError:
        logger.error(f"Excel file not found: {filepath}")
        raise
    except Exception as e:
        logger.error(f"Error processing Excel file: {e}")
        raise


if __name__ == "__main__":
    # Test with a sample file
    import sys
    if len(sys.argv) > 1:
        df = process_excel(sys.argv[1])
        print(df.head())
        print(f"\nColumns: {df.columns.tolist()}")
    else:
        print("Usage: python process_excel.py <filepath.xlsx>")
