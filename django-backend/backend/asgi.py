# """
# ASGI config for backend project.

# It exposes the ASGI callable as a module-level variable named ``application``.

# For more information on this file, see
# https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
# """

# import os

# from django.core.asgi import get_asgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# application = get_asgi_application()


import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import voice_assistant.routing  # 👈 routing.py buradan çekiliyor

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # normal HTTP requestler için
    "websocket": AuthMiddlewareStack(  # websocket requestler için
        URLRouter(
            voice_assistant.routing.websocket_urlpatterns  # 👈 yönlendirme burada yapılır
        )
    ),
})


