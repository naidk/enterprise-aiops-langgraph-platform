import requests
from tenacity import retry, stop_after_attempt, wait_exponential

class OrderAPIService:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def make_request(self, url, timeout=5):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Log the exception and re-raise it to trigger the retry
            print(f"Request failed: {e}")
            raise

    def get_order(self, order_id):
        url = f"/orders/{order_id}"
        return self.make_request(url)