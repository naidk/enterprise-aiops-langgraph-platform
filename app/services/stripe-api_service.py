import time
import random
import logging

MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
BACKOFF_MULTIPLIER = 2

def connect_to_database():
    # existing database connection code
    pass

def stripe_api_service():
    retries = 0
    while retries < MAX_RETRIES:
        try:
            connect_to_database()
            break
        except ConnectionRefusedError:
            logging.error("Database connection refused, retrying...")
            backoff = INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** retries)
            time.sleep(backoff + random.random())  # add some jitter
            retries += 1
    if retries == MAX_RETRIES:
        logging.error("Database connection failed after {} retries".format(MAX_RETRIES))
        raise Exception("Database connection failed")