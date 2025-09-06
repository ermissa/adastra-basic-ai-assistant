# voice_assistant/sessions/session_manager.py

from typing import Optional
from voice_assistant.models import CallSession


class CallSessionManager:
    def __init__(self):
        self.session: Optional[CallSession] = None

    def create_session(self, call_sid: str) -> CallSession:
        self.session = CallSession(call_sid=call_sid)
        return self.session

    def get_session(self) -> Optional[CallSession]:
        return self.session

    def get_call_sid(self) -> Optional[str]:
        return self.session.call_sid if self.session else None

    def delete_session(self):
        self.session = None

    def set_stream_sid(self, stream_sid: str):
        if self.session:
            self.session.stream_sid = stream_sid

    def set_caller_number(self, number: str):
        if self.session:
            self.session.caller_number = number

    def append_transcript(self, role: str, text: str):
        if self.session:
            self.session.transcript += f"{role}: {text.strip()}\n"

    def set_openai_ws(self, ws):
        if self.session:
            self.session.openai_ws = ws

    def get_openai_ws(self):
        return self.session.openai_ws if self.session else None
