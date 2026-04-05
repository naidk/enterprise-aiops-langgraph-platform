import asyncio
from typing import Optional

class NotificationApiService:
    def __init__(self, timeout: Optional[int] = 500):  # default timeout is 500ms
        self.timeout = timeout

    async def send_notification(self, notification: dict):
        try:
            # assuming we have a database query here
            async with asyncio.timeout(self.timeout / 1000):  # convert ms to s
                # perform database query or API call here
                await self.perform_database_query(notification)
        except asyncio.TimeoutError:
            # handle timeout error
            print("Timeout error occurred")

    async def perform_database_query(self, notification: dict):
        # simulate a database query
        await asyncio.sleep(0.1)  # replace with actual database query
        # process the notification
        print("Notification sent")