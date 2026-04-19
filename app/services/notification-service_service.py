# Assuming LegacyClient has been refactored to NewClient in app.clients
from app.clients import NewClient

# Replace LegacyClient with NewClient in the code
class NotificationService:
    def __init__(self):
        self.client = NewClient()

    # Rest of the class remains the same