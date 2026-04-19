# Assuming the database connection settings are in the order-service_service.py file
import psycopg2
from psycopg2 import pool

# Define the database connection settings
DB_HOST = '127.0.0.1'
DB_PORT = 5432
DB_NAME = 'order_db'
DB_USER = 'order_user'
DB_PASSWORD = 'order_password'

# Create a connection pool with a minimum and maximum number of connections
minconn = 1
maxconn = 20

# Create a connection pool
conn_pool = pool.ThreadedConnectionPool(
    minconn, maxconn, 
    host=DB_HOST, 
    port=DB_PORT, 
    database=DB_NAME, 
    user=DB_USER, 
    password=DB_PASSWORD
)

# Get a connection from the pool
def get_db_connection():
    return conn_pool.getconn()

# Release a connection back to the pool
def release_db_connection(conn):
    conn_pool.putconn(conn)