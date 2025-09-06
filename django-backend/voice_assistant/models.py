from django.db import models
from dataclasses import dataclass
from voice_assistant.services.openai_service import OpenAIService
from typing import Optional


@dataclass
class CallSession:
    """
    Represents a call session with attributes related to the call and OpenAI service.

    Attributes:
        call_sid (str): The unique identifier for the call session.
        openai_service (OpenAIService): The OpenAI service instance used during the session.
        openai_ws (str): The WebSocket URL for OpenAI communication.
        transcript (str): The transcript of the call session. Defaults to an empty string.
        stream_sid (str): The unique identifier for the audio stream.
        caller_number (str): The phone number of the caller.
    """

    call_sid: str
    # openai_service: Optional[OpenAIService] = None
    openai_ws: Optional[str] = None
    transcript: str = ""
    stream_sid: Optional[str] = None
    caller_number: Optional[str] = None
