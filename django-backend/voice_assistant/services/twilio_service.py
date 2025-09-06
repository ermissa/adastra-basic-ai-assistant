import logging
import os
from common.utils.enums import TwilioEvent
from voice_assistant.models import CallSession
from twilio.rest import Client
from django.conf import settings
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)
from dotenv import load_dotenv
import os

load_dotenv()


class TwilioService:
    def __init__(self):
        self.websocket = None
        if "TWILIO_ACCOUNT_SID" in os.environ:
            self.client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        else:
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.openai_service = None
        self.call_sid = ""

    async def get_stream_sid_and_caller_number_from_start_event_payload(self, data):
        """Twilio 'start' event — session başlangıcı, caller numarası vs."""
        stream_sid = data["start"]["streamSid"]
        caller_number = data["start"].get("customParameters", {}).get("callerNumber", "Unknown")
        return {"stream_sid": stream_sid, "caller_number": caller_number}

    async def end_call(self):
        """Twilio aramasını sonlandır."""
        try:
            calls = self.client.calls.list(status="in-progress")
            for call in calls:
                logger.info("HERE IN CALLS FOR")
                logger.info(f"FOR Call SID: {call.sid} , Status: {call.status}")

            calls = self.client.calls.list(status="in-progress")
            logger.info(f"LEN OF CALLS: {len(calls)}")
            for call in calls:
                logger.debug(f"FOR Call SID: {call.sid} , Status: {call.status}")

            logger.info(f"TWILIO Ending call {self.call_sid}...")
            # call = self.client.calls(self.call_sid).fetch()
            # logger.info(f"Call status: {call.status}")
            await self.client.calls(self.call_sid).update(status="completed")
            # await self.hangup_call()
            logger.info(f"Call {self.call_sid} ended.")
        except Exception as e:
            logger.error(f"Failed to end call {self.call_sid}: {str(e)}")

    async def hangup_call(self):
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls/{self.call_sid}.json"
        data = {"Status": "completed"}

        response = requests.post(
            url,
            data=data,
            auth=HTTPBasicAuth(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        )

        # Check the response
        if response.status_code == 200:
            logger.info(f"Call {self.call_sid} ended successfully.")
        else:
            logger.error(f"Failed to end call {self.call_sid}: {response.status_code}")

        return
