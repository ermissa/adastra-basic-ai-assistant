"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include


urlpatterns = [
    # path('admin/', admin.site.urls),

    # Voice Assistant için route
    # TODO: Twilio admin panelinden WEBHOOK_URL'i degistirip /voice-assistant'a cevirdikten sonra burda da degistir.
    # path('voice-assistant/', include('voice_assistant.urls')),
    path('', include('voice_assistant.urls')),

    # LLM ve AI işlemleri için
    path('ai/', include('ai_core.urls')),

    # Dış servis entegrasyonları (örnek: Dropbox, Calendar)
    # path('integrations/', include('integrations.urls')),
]
