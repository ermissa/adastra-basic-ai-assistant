from django.urls import path, re_path
from . import views

app_name = 'voice_assistant'

urlpatterns = [
    path("incoming-call", views.incoming_call_view, name="incoming_call"),
    path("call-conversations/", views.call_conversation_view, name="call_conversations"),
    path("call-conversation/<str:call_session_id>/", views.call_conversation_view, name="call_conversation"),
    # re_path(r'media-stream/?$', views.MediaStreamConsumer.as_asgi()),
]
