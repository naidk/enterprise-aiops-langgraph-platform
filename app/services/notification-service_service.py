import logging
from typing import List

class NotificationService:
    def __init__(self):
        self.notifications = []  # Initialize an empty list to store notifications
        self.max_notifications = 1000  # Set a maximum number of notifications to store

    def add_notification(self, notification):
        if len(self.notifications) >= self.max_notifications:
            # Remove the oldest notification when the maximum is reached
            self.notifications.pop(0)
        self.notifications.append(notification)

    def get_notifications(self):
        return self.notifications

# Example usage:
notification_service = NotificationService()
for i in range(1001):
    notification_service.add_notification(f"Notification {i}")

# This will prevent the memory leak by limiting the number of notifications stored