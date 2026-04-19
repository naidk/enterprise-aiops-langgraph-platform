import requests
from requests.exceptions import Timeout
import time

class PaymentAPIService:
    def __init__(self, timeout=5, retries=3):
        self.timeout = timeout
        self.retries = retries

    def make_request(self, url):
        for attempt in range(self.retries):
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except (Timeout, requests.exceptions.RequestException) as e:
                if attempt < self.retries - 1:
                    time.sleep(1)  # wait before retrying
                else:
                    raise Exception(f"Failed after {self.retries} retries: {e}")

# Usage
payment_api = PaymentAPIService()
url = "https://downstream-service.com/api/endpoint"
response = payment_api.make_request(url)