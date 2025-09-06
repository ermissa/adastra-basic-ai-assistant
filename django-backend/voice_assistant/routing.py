from django.urls import re_path
from voice_assistant.views import MediaStreamConsumer

websocket_urlpatterns = [
    re_path(r"^ws/media-stream/$", MediaStreamConsumer.as_asgi()),
]
