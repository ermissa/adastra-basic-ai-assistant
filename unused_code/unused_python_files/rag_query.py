import os
import json
import base64
import asyncio
import time
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
from dotenv import load_dotenv
# from old_functions import Functions
from twilio.rest import Client
from datetime import datetime, timezone, timedelta
# from utils import logger, set_log_level, LogLevel
from functions import Functions
from utils.db import VectorDB
from utils.logger import Logger
from utils.langchain import LangChainBatteryExpert

# Set log level (can be adjusted as needed)
# set_log_level(LogLevel.INFO)

load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER = os.getenv('TWILIO_NUMBER')
PORT = int(os.getenv('PORT', 5050))
BOOKING_WEBHOOK_URL = "https://hook.eu2.make.com/s2i4ntg7acs38vv1axe2fnt3zow623cq"

async def main():
    start_time = time.time()
    
    langchain_object = LangChainBatteryExpert()
    query_response = await langchain_object.get_battery_info(
        # question="What is the battery capacity of the Lithium Battery 22?",
        question="What is the price of the Lithium Battery 1?",
    )
    print(query_response)
    elapsed = time.time() - start_time

    print(f"\n\nQuery process completed in {elapsed:.2f} seconds")



if __name__ == "__main__":
    asyncio.run(main())
