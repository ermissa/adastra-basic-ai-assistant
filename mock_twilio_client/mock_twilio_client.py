#!/usr/bin/env python3
"""
Mock Twilio Client for Testing Voice Assistant Locally

This script simulates a complete Twilio call flow:
1. Sends an HTTP POST request to simulate incoming call
2. Opens WebSocket connection like Twilio MediaStream
3. Captures real microphone input and streams it
4. Handles all Twilio event types with proper payload structure

Usage:
    python mock_twilio_client.py

Requirements:
    pip install websockets pyaudio requests
"""
import asyncio
import json
import base64
import time
import logging
import threading
import requests
from typing import Optional
import websockets
import pyaudio
import wave
try:
    import audioop
except ImportError:
    # Fallback for Python 3.12+ where audioop is removed
    import pylaw as audioop

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class MockTwilioClient:
    def __init__(self, django_host="localhost:8000", caller_number="+31623925157"):
        self.django_host = django_host
        self.caller_number = caller_number
        self.call_sid = f"CA{int(time.time())}{hash(caller_number) % 10000:04d}"
        self.stream_sid = f"MZ{int(time.time())}{hash(caller_number) % 10000:04d}"
        self.websocket = None
        self.audio_thread = None
        self.is_streaming = False

        # Audio configuration (matches Twilio's format)
        # self.audio_format = pyaudio.paULaw

        # chatgpt recommendation:
        # self.audio_format = pyaudio.paInt16  # Input format is PCM, we'll convert to ulaw later

        self.channels = 1
        self.rate = 8000  # 8kHz sample rate for ulaw
        self.chunk = 160  # 20ms chunks (8000 * 0.02)
        self.pyaudio_instance = None
        self.stream = None

    async def simulate_incoming_call(self):
        """Simulate Twilio's incoming call HTTP POST request"""
        logger.info(f"Simulating incoming call from {self.caller_number}")

        # Prepare POST data that matches Twilio's incoming call webhook
        post_data = {
            "AccountSid": "AC1234567890abcdef",
            "ApiVersion": "2010-04-01",
            "CallSid": self.call_sid,
            "CallStatus": "ringing",
            "Called": "+1987654321",  # Your Twilio number
            "CalledCity": "Amsterdam",
            "CalledCountry": "NL",
            "CalledState": "",
            "CalledZip": "",
            "Caller": self.caller_number,
            "CallerCity": "Unknown",
            "CallerCountry": "Unknown",
            "CallerState": "",
            "CallerZip": "",
            "Direction": "inbound",
            "From": self.caller_number,
            "FromCity": "Unknown",
            "FromCountry": "Unknown",
            "FromState": "",
            "FromZip": "",
            "To": "+1987654321",
            "ToCity": "Amsterdam",
            "ToCountry": "NL",
            "ToState": "",
            "ToZip": "",
        }

        try:
            # Send POST request to Django incoming call endpoint
            url = f"http://{self.django_host}/incoming-call"
            response = requests.post(url, data=post_data, timeout=10)

            if response.status_code == 200:
                logger.info("✅ Incoming call request sent successfully")
                logger.info(f"TwiML Response: {response.text}")
                return True
            else:
                logger.error(f"❌ Failed to send incoming call: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error sending incoming call request: {e}")
            return False

    async def connect_websocket(self):
        """Connect to the Django WebSocket endpoint"""
        ws_url = f"ws://{self.django_host}/ws/media-stream/"
        logger.info(f"Connecting to WebSocket: {ws_url}")

        try:
            self.websocket = await websockets.connect(ws_url)
            logger.info("✅ WebSocket connected successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect WebSocket: {e}")
            return False

    async def send_start_event(self):
        """Send Twilio 'start' event to initialize the media stream"""
        start_event = {
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "accountSid": "AC1234567890abcdef",
                "streamSid": self.stream_sid,
                "callSid": self.call_sid,
                "tracks": ["inbound"],
                "customParameters": {
                    "callerNumber": self.caller_number,
                    "firstMessage": "Say 'Hello, this is Sofi. What language would you prefer: English, Dutch, or Turkish?'",
                },
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
            },
            "streamSid": self.stream_sid,
        }

        logger.info("📤 Sending START event")
        await self.websocket.send(json.dumps(start_event))

    def init_audio(self):
        """Initialize PyAudio for microphone input and speaker output"""
        try:
            self.pyaudio_instance = pyaudio.PyAudio()

            # List available input devices
            logger.info("Available audio input devices:")
            for i in range(self.pyaudio_instance.get_device_count()):
                info = self.pyaudio_instance.get_device_info_by_index(i)
                if info["maxInputChannels"] > 0:
                    logger.info(f"  {i}: {info['name']} (inputs: {info['maxInputChannels']})")

            # Microphone input stream (16-bit PCM)
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

            # Speaker output stream (for playing assistant's response)
            self.speaker_stream = self.pyaudio_instance.open(format=pyaudio.paInt16, channels=1, rate=8000, output=True)

            logger.info("🎤 Microphone and 🔈 Speaker initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize audio: {e}")
            return False

    def convert_to_ulaw(self, pcm_data):
        """Convert PCM audio to μ-law encoding (matches Twilio format)"""
        # audioop is already imported at the top with fallback

        # Convert 16-bit PCM to μ-law
        ulaw_data = audioop.ulaw2lin(audioop.lin2ulaw(pcm_data, 2), 1)
        return ulaw_data

    async def stream_audio(self):
        """Stream microphone audio to WebSocket in real-time"""
        if not self.stream:
            logger.error("❌ Audio stream not initialized")
            return

        logger.info("🎤 Starting audio streaming... Speak into your microphone!")
        sequence_number = 2  # Start after the START event

        try:
            while self.is_streaming:
                # Read audio data from microphone
                try:
                    audio_data = self.stream.read(self.chunk, exception_on_overflow=False)

                    # Convert to μ-law and encode as base64
                    ulaw_data = audioop.lin2ulaw(audio_data, 2)
                    audio_b64 = base64.b64encode(ulaw_data).decode("utf-8")

                    # Create media event in Twilio format
                    media_event = {
                        "event": "media",
                        "sequenceNumber": str(sequence_number),
                        "media": {
                            "track": "inbound",
                            "chunk": str(sequence_number - 1),
                            "timestamp": str(int(time.time() * 1000)),
                            "payload": audio_b64,
                        },
                        "streamSid": self.stream_sid,
                    }

                    # Send audio data
                    logger.debug(f"📤 Sending audio chunk , sequence_number : {sequence_number - 1}")
                    await self.websocket.send(json.dumps(media_event))
                    sequence_number += 1

                    # Small delay to maintain real-time streaming
                    await asyncio.sleep(0.02)  # 20ms chunks

                except Exception as e:
                    if self.is_streaming:  # Only log if we're still supposed to be streaming
                        logger.error(f"Error reading audio: {e}")
                    return

                except Exception as e:
                    if self.is_streaming:
                        logger.error(f"Error streaming audio: {e}")
                    return

        except Exception as e:
            logger.error(f"❌ Error in audio streaming: {e}")
            return
        finally:
            logger.info("🛑 Audio streaming stopped")
            return

    async def handle_outbound_audio(self):
        """Handle audio responses from the voice assistant"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    event = data.get("event")

                    if event == "media":
                        audio_payload = data.get("media", {}).get("payload")
                        if audio_payload:
                            logger.info("🔊 Received audio from assistant (would play to speaker)")
                            audio_bytes = base64.b64decode(audio_payload)
                            pcm_audio = audioop.ulaw2lin(audio_bytes, 2)
                            self.speaker_stream.write(pcm_audio)

                    elif event == "mark":
                        # Mark events for synchronization
                        logger.debug("📍 Received mark event")

                    elif event == "clear":
                        # Clear buffer event
                        logger.info("🧹 Received clear buffer event")

                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON message: {message}")
                    return

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed by server")
            return
        except Exception as e:
            logger.error(f"Error handling outbound audio: {e}")
            return

    async def send_periodic_marks(self):
        """Send periodic mark events (used by Twilio for synchronization)"""
        mark_counter = 1
        try:
            while self.is_streaming:
                await asyncio.sleep(1.0)  # Send marks every second

                mark_event = {
                    "event": "mark",
                    "sequenceNumber": str(1000 + mark_counter),
                    "mark": {"name": f"periodic_mark_{mark_counter}"},
                    "streamSid": self.stream_sid,
                }

                await self.websocket.send(json.dumps(mark_event))
                mark_counter += 1

        except Exception as e:
            if self.is_streaming:
                logger.error(f"Error sending periodic marks: {e}")
            return

    async def run_mock_call(self):
        """Run the complete mock Twilio call simulation"""
        try:
            # Step 1: Simulate incoming call HTTP request
            logger.info("🚀 Starting mock Twilio call simulation...")
            if not await self.simulate_incoming_call():
                return False

            # Small delay to let Django process the incoming call
            await asyncio.sleep(1)

            # Step 2: Connect WebSocket
            if not await self.connect_websocket():
                return False

            # Step 3: Send START event
            await self.send_start_event()

            # Step 4: Initialize audio
            if not self.init_audio():
                return False

            # Step 5: Start streaming
            self.is_streaming = True

            # Run all tasks concurrently
            tasks = [
                asyncio.create_task(self.stream_audio()),
                asyncio.create_task(self.handle_outbound_audio()),
                asyncio.create_task(self.send_periodic_marks()),
            ]

            logger.info("✅ Mock call is now active! Speak into your microphone.")
            logger.info("Press Ctrl+C to end the call")

            # Wait for all tasks or until interrupted
            await asyncio.gather(*tasks, return_exceptions=True)

        except KeyboardInterrupt:
            logger.info("📞 Call ended by user")
            return
        except Exception as e:
            logger.error(f"❌ Error in mock call: {e}")
            return
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up resources...")

        self.is_streaming = False

        # Close audio stream
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

        # Close WebSocket
        if self.websocket:
            await self.websocket.close()

        logger.info("✅ Cleanup completed")


async def main():
    """Main function to run the mock Twilio client"""
    import argparse

    parser = argparse.ArgumentParser(description="Mock Twilio Client for Voice Assistant Testing")
    parser.add_argument("--host", default="localhost:8000", help="Django server host:port")
    parser.add_argument("--caller", default="+31623925157", help="Mock caller number")

    args = parser.parse_args()

    print("🎭 Mock Twilio Client for Voice Assistant Testing")
    print("=" * 50)
    print(f"Django Host: {args.host}")
    print(f"Caller Number: {args.caller}")
    print("=" * 50)

    client = MockTwilioClient(django_host=args.host, caller_number=args.caller)
    await client.run_mock_call()


if __name__ == "__main__":
    asyncio.run(main())
