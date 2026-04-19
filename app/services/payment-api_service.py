import logging
from typing import Optional

class PaymentAPIService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def process_payment(self, payment_data: Optional[dict]) -> None:
        if payment_data is None:
            self.logger.error("Payment data is null")
            return
        
        try:
            # Process payment data here
            pass
        except Exception as e:
            self.logger.error(f"Error processing payment: {e}")
        finally:
            # Ensure all resources are closed and garbage collected
            payment_data = None

    def handle_request(self, request: dict) -> None:
        payment_data = request.get("payment_data")
        self.process_payment(payment_data)