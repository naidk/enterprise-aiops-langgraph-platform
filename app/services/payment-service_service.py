# Assuming LegacyClient has been replaced or removed during the refactor
# and the correct client class is now named 'PaymentClient' in 'app.clients'

from app.clients import PaymentClient

# Replace all occurrences of LegacyClient with PaymentClient
# Example:
# legacy_client = LegacyClient()
payment_client = PaymentClient()