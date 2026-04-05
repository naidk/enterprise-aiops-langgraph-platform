import psycopg2
from psycopg2 import Error
import time

# Define database connection settings
DB_HOST = '127.0.0.1'
DB_PORT = 5433  # Corrected port number
DB_NAME = 'notification_db'
DB_USER = 'notification_user'
DB_PASSWORD = 'notification_password'

# Define retry settings
MAX_RETRIES = 5
RETRY_DELAY = 1  # seconds

def connect_to_db():
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Attempt to connect to the database
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return conn
        except (Exception, Error) as error:
            # Handle connection failure and retry
            print(f"Error connecting to database: {error}")
            retries += 1
            time.sleep(RETRY_DELAY)
    # If all retries fail, raise an exception
    raise Exception("Failed to connect to database after retries")

# Usage example
conn = connect_to_db()
# Use the connection object to perform database operations