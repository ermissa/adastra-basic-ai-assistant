import os
import json
import base64
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
from dotenv import load_dotenv
from old_functions import Functions
from twilio.rest import Client
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Union

# from utils import logger
from utils.logger import LogLevel, Logger

# Create a global logger instance
logger = Logger()

# Set the default log level (can be changed at runtime)
def set_log_level(level: Union[LogLevel, str]):
    """Set the global logger level"""
    if isinstance(level, str):
        level = level.upper()
        for log_level in LogLevel:
            if log_level.value[1] == level:
                logger.level = log_level
                return
        raise ValueError(f"Invalid log level: {level}")
    else:
        logger.level = level 

# Set log level (can be adjusted as needed)
set_log_level(LogLevel.INFO)

# load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER = os.getenv('TWILIO_NUMBER')
PORT = int(os.getenv('PORT', 5050))
BOOKING_WEBHOOK_URL = "https://hook.eu2.make.com/s2i4ntg7acs38vv1axe2fnt3zow623cq"

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize Functions class
functions = Functions()

# Initialize global variables
SYSTEM_MESSAGE = (
    "You are Sofi, an AI assistant for ACCUDAM. You help users schedule appointments "
    "and provide information about services. You can communicate in English, Dutch, "
    "and Turkish. You are professional, helpful, and clear in your communication."
)

VOICE = 'sage'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created', 'response.text.done',
    'conversation.item.input_audio_transcription.completed'
]

app = FastAPI()

# Session management
sessions = {}

async def end_call(call_sid: str):
    """Helper function to end the call using Twilio"""
    try:
        await twilio_client.calls(call_sid).update(status='completed')
        logger.info(f"Call {call_sid} has been ended successfully.")
    except Exception as e:
        logger.error(f"Error ending the call: {str(e)}")

async def send_to_webhook(payload: dict, webhook_url: str) -> str:
    """Send data to webhook"""
    logger.info(f"Sending data to webhook", data=payload, category="Webhook")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                headers={'Content-Type': 'application/json'},
                json=payload
            ) as response:
                logger.info(f"Webhook response status: {response.status}", category="Webhook")
                if response.ok:
                    response_text = await response.text()
                    logger.info(f"Webhook response", data={"response": response_text}, category="Webhook")
                    return response_text
                else:
                    raise Exception(f'Webhook request failed: {response.status}')
    except Exception as e:
        logger.error(f'Error sending data to webhook: {str(e)}', category="Webhook")
        raise

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    form_data = await request.form()
    caller_number = form_data.get('From', 'Unknown')
    
    logger.info(f"Incoming call received", data={"caller": caller_number}, category="Call")
    
    response = VoiceResponse()
    host = request.url.hostname
    connect = Connect()
    stream = Stream(url=f'wss://{host}/media-stream')
    
    # Add parameters like in index.js
    stream.parameter(name="firstMessage", value="Say 'Goedendag , dit is Sofi van ACCUDAM. In welke taal wilt u graag verdergaan: Nederlands, English of Türkçe?' and initiate the converitation with the chosen language")
    stream.parameter(name="callerNumber", value=caller_number)
    
    connect.append(stream)
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    logger.info("Client connected", category="WebSocket")
    await websocket.accept()

    # Get call parameters
    params = dict(websocket.query_params)
    call_sid = params.get('CallSid', f'session_{datetime.now().timestamp()}')
    
    # Set call context for logging
    logger.set_call_context(call_sid, None)
    
    # Initialize session data
    session = {
        'transcript': '',
        'caller_number': None,
        'stream_sid': None
    }
    sessions[call_sid] = session

    async with websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        await initialize_session(openai_ws)

        # Connection specific state
        stream_sid = None
        latest_media_timestamp = 0
        last_assistant_item = None
        mark_queue = []
        response_start_timestamp_twilio = None
        
        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid, latest_media_timestamp, session
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        session['stream_sid'] = stream_sid
                        custom_parameters = data['start'].get('customParameters', {})
                        session['caller_number'] = custom_parameters.get('callerNumber')
                        
                        # Update call context with caller number
                        logger.set_call_context(call_sid, session['caller_number'])
                        
                        logger.info(f"Call started", data={
                            "stream_sid": stream_sid,
                            "caller_number": session['caller_number']
                        }, category="Call")
                        
                    elif data['event'] == 'media' and openai_ws.open:
                        latest_media_timestamp = int(data['media']['timestamp'])
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    
                    elif data['event'] == 'mark':
                        if mark_queue:
                            mark_queue.pop(0)
                            
            except WebSocketDisconnect:
                logger.info(f"Client disconnected", category="WebSocket")
                logger.info("Full Transcript:", data={"transcript": session['transcript']}, category="Transcript")
                
                # Clean up session
                if call_sid in sessions:
                    del sessions[call_sid]
                
                # Clear call context
                logger.clear_call_context()
                
                if openai_ws.open:
                    await openai_ws.close()

        async def handle_function_call(response):
            """Handle function calls from OpenAI"""
            global SYSTEM_MESSAGE
            function_name = response['name']
            args = json.loads(response['arguments'])
            call_id = response.get('call_id')
            
            logger.function_call(function_name, args)

            if function_name == 'end_call':
                goodbye_message = args.get('message', "Goodbye!")
                logger.info(f"Processing end_call function", data={"message": goodbye_message}, category="Function")

                # Send system message
                await openai_ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "role": "system",
                        "call_id": call_id,
                        "output": goodbye_message
                    }
                }))

                # Generate audio response
                await openai_ws.send(json.dumps({
                    "type": "response.create",
                    "response": {
                        "modalities": ["text", "audio"],
                        "instructions": f'Say: "{goodbye_message}".',
                    }
                }))

                # End call after delay
                logger.info("Ending call after delay", category="Call")
                await asyncio.sleep(3)
                if call_sid:
                    await end_call(call_sid)

            elif function_name == 'set_language':
                logger.info("Processing set_language function call", category="Function")
                language_response = args.get('language_response')
                caller_number = session.get('caller_number')
                
                try:
                    # Get the language-specific system message
                    result = functions.get_user_language_file_content(language_response, caller_number)
                    
                    # Update the SYSTEM_MESSAGE with the content from the file
                    if result and result.get('messages'):
                        SYSTEM_MESSAGE = result['messages'][0]['content']
                        logger.info(f"Language set", data={
                            "language": result['language'],
                            "system_message": SYSTEM_MESSAGE
                        }, category="Language")
                        
                        # Update the session with new system message
                        await openai_ws.send(json.dumps({
                            "type": "session.update",
                            "session": {
                                "instructions": SYSTEM_MESSAGE
                            }
                        }))
                        
                        # Continue the conversation with the new language
                        await openai_ws.send(json.dumps({
                            "type": "response.create",
                            "response": {
                                "modalities": ["text", "audio"]
                            }
                        }))
                    
                except Exception as e:
                    logger.error(f"Error setting language: {str(e)}", category="Language")
                    # Handle error by continuing with default system message
                    await openai_ws.send(json.dumps({
                        "type": "response.create",
                        "response": {
                            "modalities": ["text", "audio"],
                            "instructions": "I apologize, but I had trouble setting your language preference. Let's continue in English for now."
                        }
                    }))

            elif function_name == 'get_battery_info':
                logger.info("Processing get_battery_info function call", category="Function")
                question = args.get('question')
                caller_number = session.get('caller_number')
                
                try:
                    # Get battery information using the Functions class
                    answer = functions.get_battery_info(question, caller_number)
                    logger.function_result("get_battery_info", answer)
                    
                    # Send the answer back to the conversation
                    await openai_ws.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "role": "system",
                            "call_id": call_id,
                            "output": answer
                        }
                    }))
                    
                    # Generate audio response
                    await openai_ws.send(json.dumps({
                        "type": "response.create",
                        "response": {
                            "modalities": ["text", "audio"],
                            "instructions": f'Respond with: "{answer}"'
                        }
                    }))
                    
                except Exception as e:
                    logger.error(f"Error getting battery information: {str(e)}", category="Function")
                    error_message = "I apologize, but I'm having trouble accessing the battery information right now. Could you please try asking your question again?"
                    
                    await openai_ws.send(json.dumps({
                        "type": "response.create",
                        "response": {
                            "modalities": ["text", "audio"],
                            "instructions": error_message
                        }
                    }))

            elif function_name == 'book_service':
                logger.info(f"Processing book_service function call", data={"booking_time": args.get('booking_time')}, category="Function")
                booking_time = args.get('booking_time')

                try:
                    webhook_response = await send_to_webhook({
                        "number": session['caller_number'],
                        "message": booking_time
                    }, BOOKING_WEBHOOK_URL)

                    parsed_response = json.loads(webhook_response)
                    status = parsed_response.get('Status', 'unknown')
                    booking_message = parsed_response.get('Booking', 
                        "I'm sorry, I couldn't book the service at that time. Do you have an alternative time?")

                    response_message = (
                        f"The booking was successful: {booking_message}"
                        if status == "Successful"
                        else f"Unfortunately, the booking was unsuccessful. {booking_message}"
                    )
                    
                    logger.info("Booking service result", data={
                        "status": status,
                        "message": response_message
                    }, category="Booking")

                    # Send booking status
                    await openai_ws.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "role": "system",
                            "call_id": call_id,
                            "output": response_message
                        }
                    }))

                    # Generate audio response
                    await openai_ws.send(json.dumps({
                        "type": "response.create",
                        "response": {
                            "modalities": ["text", "audio"],
                            "instructions": f"Inform the user: {response_message}. Be concise and friendly."
                        }
                    }))

                except Exception as e:
                    logger.error(f"Error in booking service: {str(e)}", category="Booking")
                    # Handle error response
                    await openai_ws.send(json.dumps({
                        "type": "response.create",
                        "response": {
                            "modalities": ["text", "audio"],
                            "instructions": "I apologize, but I'm having trouble processing your request right now. Is there anything else I can help you with?"
                        }
                    }))

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio, session
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    
                    # Log relevant events
                    if response['type'] in LOG_EVENT_TYPES:
                        logger.openai_event(response['type'], response)

                    # Handle function calls
                    if response['type'] == 'response.function_call_arguments.done':
                        await handle_function_call(response)

                    # Handle audio responses
                    elif response.get('type') == 'response.audio.delta' and 'delta' in response:
                        audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_payload
                            }
                        })

                        if response_start_timestamp_twilio is None:
                            response_start_timestamp_twilio = latest_media_timestamp

                        if response.get('item_id'):
                            last_assistant_item = response['item_id']

                        await send_mark(websocket, stream_sid)

                    # Handle speech interruption
                    elif response.get('type') == 'input_audio_buffer.speech_started':
                        logger.debug("Speech started detected", category="Audio")
                        await handle_speech_started_event()

                    # Log transcripts
                    elif response.get('type') == 'response.done':
                        agent_message = next(
                            (content.get('transcript') 
                             for item in response.get('response', {}).get('output', [])
                             for content in item.get('content', [])
                             if content.get('transcript')),
                            'Agent message not found'
                        )
                        session['transcript'] += f"Agent: {agent_message}\n"
                        logger.transcript("Agent", agent_message)

                    elif response.get('type') == 'conversation.item.input_audio_transcription.completed':
                        if response.get('transcript'):
                            user_message = response['transcript'].strip()
                            session['transcript'] += f"User: {user_message}\n"
                            logger.transcript("User", user_message)

            except Exception as e:
                logger.error(f"Error in send_to_twilio: {str(e)}", category="WebSocket")

        async def handle_speech_started_event():
            """Handle interruption when the caller's speech starts."""
            nonlocal response_start_timestamp_twilio, last_assistant_item
            logger.debug("Handling speech started event", category="Audio")
            
            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio

                if last_assistant_item:
                    await openai_ws.send(json.dumps({
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time
                    }))

                # Clear Twilio buffer
                await websocket.send_json({
                    "event": "clear",
                    "streamSid": stream_sid
                })

                # Reset state
                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

        async def send_mark(connection, stream_sid):
            if stream_sid:
                mark_event = {
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "responsePart"}
                }
                await connection.send_json(mark_event)
                mark_queue.append('responsePart')

        await asyncio.gather(receive_from_twilio(), send_to_twilio())

async def initialize_session(openai_ws):
    """Initialize session with OpenAI."""
    global SYSTEM_MESSAGE
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
            "input_audio_transcription": {
                "model": "whisper-1"
            },
            "tools": [
                {
                    "type": "function",
                    "name": "end_call",
                    "description": "End the call and say goodbye to the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "default": "Goodbye! Ending the call now."
                            }
                        },
                        "required": ["message"]
                    }
                },
                {
                    "type": "function",
                    "name": "book_service",
                    "description": "Book a car service for the customer",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "booking_time": {
                                "type": "string"
                            }
                        },
                        "required": ["booking_time"]
                    }
                },
                {
                    "type": "function",
                    "name": "set_language",
                    "description": "Run this function when you get the preferred language",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "language_response": {
                                "type": "string"
                            }
                        },
                        "required": ["language_response"]
                    }
                },
                {
                    "type": "function",
                    "name": "get_battery_info",
                    "description": "Get information about batteries when user asks about battery specifications, prices, or availability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The user's question about batteries"
                            }
                        },
                        "required": ["question"]
                    }
                }
            ],
            "tool_choice": "auto",
            "parallel_tool_calls": False
        }
    }
    logger.info("Initializing session with OpenAI", category="OpenAI")
    await openai_ws.send(json.dumps(session_update))
    await send_initial_conversation_item(openai_ws)

async def send_initial_conversation_item(openai_ws):
    """Send initial conversation item."""
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Say 'Goedendag , dit is Sofi van ACCUDAM. In welke taal wilt u graag verdergaan: Nederlands, English of Türkçe?' and initiate the converitation with the chosen language"
                }
            ]
        }
    }
    logger.info("Sending initial conversation item", category="OpenAI")
    await openai_ws.send(json.dumps(initial_conversation_item))
    await openai_ws.send(json.dumps({"type": "response.create"}))

if __name__ == "__main__":
    import uvicorn
    import aiohttp
    logger.info(f"Starting server on port {PORT}", category="Server")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
