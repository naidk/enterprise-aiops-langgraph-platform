import requests
import time
import random

class StripeAPIService:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 1  # initial delay in seconds
        self.circuit_breaker_threshold = 5  # threshold for circuit breaker
        self.circuit_breaker_timeout = 30  # timeout for circuit breaker in seconds
        self.circuit_breaker_count = 0

    def make_request(self, url, params):
        if self.circuit_breaker_count >= self.circuit_breaker_threshold:
            # circuit breaker is open, return error immediately
            return {"error": "Circuit breaker open"}

        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                self.circuit_breaker_count += 1
                if attempt < self.max_retries - 1:
                    # retry with exponential backoff
                    delay = self.retry_delay * (2 ** attempt) + random.random()
                    time.sleep(delay)
                else:
                    # all retries failed, return error
                    return {"error": str(e)}

        # if all retries fail, open circuit breaker
        self.circuit_breaker_count = self.circuit_breaker_threshold
        return {"error": "All retries failed"}

    def reset_circuit_breaker(self):
        self.circuit_breaker_count = 0

# usage
stripe_api = StripeAPIService()
response = stripe_api.make_request("https://api.stripe.com/v1/charges", {"limit": 10})
print(response)