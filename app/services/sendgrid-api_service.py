import time
import requests
import logging

class SendgridAPIService:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url

    def send_request(self, endpoint, data):
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            try:
                response = requests.post(f"{self.base_url}{endpoint}", json=data, headers={"Authorization": f"Bearer {self.api_key}"})
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as errh:
                if errh.response.status_code == 429:
                    retry_after = int(errh.response.headers.get("Retry-After", 60))
                    logging.warning(f"API rate limit exceeded. Retrying after {retry_after} seconds.")
                    time.sleep(retry_after)
                    retry_count += 1
                else:
                    raise
            except requests.exceptions.RequestException as err:
                logging.error(f"Request failed: {err}")
                retry_count += 1
        logging.error("Max retries exceeded. Request failed.")
        return None