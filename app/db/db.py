"""
Bot Omie - MySQL Database Connection Module
============================================

Provides database connection factory with auto-creation of database.
Based on bot_pso architecture.
"""

import logging
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('omie_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _ensure_database_exists():
    """
    Ensures the target database exists. Creates it if it doesn't.
    """
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        cursor = conn.cursor()
        db_name = os.getenv('DB_NAME', 'omie_db')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Database '{db_name}' verified/created successfully.")
    except Error as e:
        logger.error(f"Error ensuring database exists: {e}")
        raise


def get_conn():
    """
    Returns a MySQL connection to the configured database.
    Creates the database if it doesn't exist.
    
    Returns:
        mysql.connector.connection.MySQLConnection: Active database connection
    """
    _ensure_database_exists()
    
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME', 'omie_db')
        )
        logger.info("Database connection established successfully.")
        return conn
    except Error as e:
        logger.error(f"Error connecting to database: {e}")
        raise


if __name__ == "__main__":
    # Test connection
    conn = get_conn()
    print("Connection successful!")
    conn.close()
