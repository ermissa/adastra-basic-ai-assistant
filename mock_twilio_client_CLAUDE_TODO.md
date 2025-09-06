I want to create a mock Twilio client for testing my voice assistant project without needing to actually make a phone call via Twilio.
This mock client should behave exactly like Twilio’s real client so that I can use it with my existing call_orchestrator, twilio_service, and openai_service without any modifications.

Specifically, it should:
	•	Simulate an incoming call by triggering the same incoming_call HTTP request that Twilio sends.
	•	Open a WebSocket connection just like Twilio’s MediaStream would do.
	•	Send the same event types (start, media, mark, etc.) with the same payload structure as real Twilio MediaStream.
	•	Accept microphone input from my local machine and send it in real-time over the WebSocket as if it came from Twilio.

This will allow me to test the entire voice pipeline locally with real voice input, without paying Twilio fees or waiting for phone call delays.

Please implement this mock Twilio client, preferably in Python. Use any audio/microphone libraries needed (e.g., pyaudio, sounddevice, websockets, etc.) for real-time input.