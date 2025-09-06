from django.db import models


class EventLog(models.Model):
    call_session_id = models.CharField(max_length=50)
    event_name = models.CharField(max_length=100, null=True)
    event_data = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
