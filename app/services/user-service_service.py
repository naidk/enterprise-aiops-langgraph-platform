import psycopg2
import time

def connect_to_db(host, database, user, password):
    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Failed to connect to database: {e}")
        time.sleep(1)  # wait for 1 second before retrying
        return connect_to_db(host, database, user, password)

def main():
    host = 'localhost'
    database = 'user_database'
    user = 'user'
    password = 'password'

    conn = connect_to_db(host, database, user, password)
    if conn:
        print("Connected to database successfully")
    else:
        print("Failed to connect to database")

if __name__ == "__main__":
    main()