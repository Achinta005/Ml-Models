import os
from mysql.connector import pooling, Error
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# ✅ Database configuration from environment
dbconfig = {
    "host": os.getenv("TIDB_HOST"),
    "user": os.getenv("TIDB_USER"),
    "password": os.getenv("TIDB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}

# ✅ Create a MySQL connection pool (shared across routes)
try:
    pool_size = int(os.getenv("DB_POOL_SIZE", 5))
    connection_pool = pooling.MySQLConnectionPool(pool_name="portfolio_pool", pool_size=pool_size, **dbconfig)
    print("✅ MySQL Connection Pool initialized successfully")
except Error as e:
    print("❌ Error while creating connection pool:", e)
    connection_pool = None


# ✅ Helper function to get a connection safely
def get_connection():
    """
    Returns a connection from the global pool.
    Always close the connection after use.
    """
    if not connection_pool:
        raise RuntimeError("Database connection pool is not initialized.")
    return connection_pool.get_connection()
