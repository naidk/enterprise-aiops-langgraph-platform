import logging
import time
import random

import stripe

MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
BACKOFF_MULTIPLIER = 2

def connect_to_database():
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Establish database connection
            stripe.api_key = "YOUR_STRIPE_API_KEY"
            return stripe
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            retries += 1
            backoff = INITIAL_BACKOFF * (BACKOFF_MULTIPLIER ** retries)
            backoff_jitter = random.uniform(0, 1)
            time.sleep(backoff + backoff_jitter)
    logging.error("All retries failed. Giving up.")
    raise Exception("Database connection failed after retries")

# Usage
stripe = connect_to_database()