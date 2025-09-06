import logging
import json
import asyncio
import traceback
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Max, Q
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from voice_assistant.services.call_orchestrator import CallOrchestrator

logger = logging.getLogger(__name__)
IS_TEST = os.environ.get("IS_TEST") == "true"
IS_RECORD = os.environ.get("IS_RECORD") == "true"


@csrf_exempt
def incoming_call_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    logger.info("Incoming call received")
    # Twilio'dan gelen caller numarasını al
    caller_number = request.POST.get("From", "Unknown")
    host = request.get_host().split(":")[0]  # IP veya domain

    # TwiML ile yönlendirme cevabı oluştur
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=f"wss://{host}/ws/media-stream/")
    stream.parameter(name="callerNumber", value=caller_number)
    stream.parameter(name="firstMessage", value="Say 'Hello, this is Sofi. What language would you prefer: English, Dutch, or Turkish?'")

    connect.append(stream)
    response.append(connect)

    return HttpResponse(str(response), content_type="application/xml")


class MediaStreamConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orchestrator = None
        self._connection_closed = False

    async def connect(self):
        try:
            await self.accept()
            if not IS_TEST:
                self.orchestrator = CallOrchestrator(consumer=self)
            else:
                self.orchestrator = CallOrchestrator(consumer=self)
            logger.info("Client connected")
        except Exception as e:
            logger.error(f"Error during WebSocket connect: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self.close()

    async def receive(self, text_data):
        if IS_RECORD:
            logging.info(f"incoming message ---{text_data}---")
        if self._connection_closed:
            logger.warning("Ignoring message on closed connection")
            return

        try:
            data = json.loads(text_data)
            event_type = data.get("event")
            if event_type == "start":
                # Twilio'dan gelen start olayını işleyin
                logger.info(f"JSON data WebSocket message:\n{json.dumps(data, indent=2)}")
                caller_number = data["start"].get("customParameters", {}).get("callerNumber")
                if caller_number:
                    self.orchestrator.set_caller_number(caller_number)
            await self.orchestrator.handle_twilio_event(event_type, data)
        except Exception as e:
            logger.error(f"Error in receive: {str(e)}")

            if self.orchestrator:
                await self.orchestrator.handle_twilio_event(event_type, data)
            else:
                logger.error("Orchestrator not initialized")
                await self._emergency_disconnect()

    async def disconnect(self, close_code):
        if self._connection_closed:
            return

        self._connection_closed = True
        logger.info(f"Client disconnected with code: {close_code}")

        try:
            if self.orchestrator:
                await self.orchestrator.shutdown()
        except Exception as e:
            logger.error(f"Error during orchestrator shutdown: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _emergency_disconnect(self):
        logger.warning("_emergency_disconnect is called")
        """Emergency disconnect when critical errors occur."""
        if self._connection_closed:
            return

        logger.warning("Performing emergency disconnect")
        self._connection_closed = True

        try:
            # Try to shutdown orchestrator first
            if self.orchestrator:
                await self.orchestrator.shutdown()
        except Exception as e:
            logger.error(f"Error during emergency orchestrator shutdown: {str(e)}")
            return

        try:
            # Close WebSocket connection
            await self.close(code=1011)  # Internal server error
        except Exception as e:
            logger.error(f"Error closing WebSocket during emergency: {str(e)}")
            return

    async def send(self, text_data=None, bytes_data=None):
        if IS_TEST:
            logger.info(f"passing twillio event {text_data}")
            return
        """Override send to handle connection errors gracefully."""
        if self._connection_closed:
            logger.warning("Attempting to send on closed connection")
            return

        try:
            await super().send(text_data=text_data, bytes_data=bytes_data)
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {str(e)}")
            await self._emergency_disconnect()
            raise


def call_conversation_view(request, call_session_id=None):
    from db.models import EventLog

    """
    Display call conversations in WhatsApp UI format.
    Shows all sessions in sidebar and messages for selected session.
    """
    # Get all unique call sessions with their latest message info
    call_sessions = (
        EventLog.objects.filter(event_name__in=["conversation.item.input_audio_transcription.completed", "response.audio_transcript.done"])
        .values("call_session_id")
        .annotate(message_count=Count("id"), latest_message_time=Max("created_at"))
        .order_by("-latest_message_time")
    )

    # Add latest message content for each session
    for session in call_sessions:
        latest_log = (
            EventLog.objects.filter(
                call_session_id=session["call_session_id"],
                event_name__in=["conversation.item.input_audio_transcription.completed", "response.audio_transcript.done"],
            )
            .order_by("-created_at")
            .first()
        )

        if latest_log:
            if latest_log.event_name == "conversation.item.input_audio_transcription.completed":
                session["latest_message"] = latest_log.event_data.get("transcript", "No transcript") if latest_log.event_data else "No transcript"
            elif latest_log.event_name == "response.audio_transcript.done":
                session["latest_message"] = latest_log.event_data.get("transcript", "No transcript") if latest_log.event_data else "No transcript"
        else:
            session["latest_message"] = "No messages"

    # If no specific session requested, show the first session
    if not call_session_id and call_sessions:
        call_session_id = call_sessions[0]["call_session_id"]

    # Get messages for selected session
    messages = []
    if call_session_id:
        logs = EventLog.objects.filter(
            call_session_id=call_session_id,
            event_name__in=["conversation.item.input_audio_transcription.completed", "response.audio_transcript.done"],
        ).order_by("id")

        for log in logs:
            if log.event_data:
                transcript = log.event_data.get("transcript", "")
                if transcript:
                    messages.append(
                        {
                            "content": transcript,
                            "created_at": log.created_at,
                            "is_user": log.event_name == "conversation.item.input_audio_transcription.completed",
                        }
                    )

    context = {"call_sessions": call_sessions, "current_session_id": call_session_id, "messages": messages}

    return render(request, "whatsapp_ui/conversation.html", context)
