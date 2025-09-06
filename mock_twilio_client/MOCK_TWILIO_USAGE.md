# Mock Twilio Client Usage Guide

This mock Twilio client allows you to test your voice assistant locally without making actual phone calls or paying Twilio fees.

## Installation

1. Install the required dependencies:
```bash
pip install -r mock_requirements.txt
```

**Note for macOS users**: If you encounter issues installing PyAudio, you may need to install PortAudio first:
```bash
brew install portaudio
pip install pyaudio
```

## Quick Start

1. **Start your Django server** (in one terminal):
```bash
cd django-backend
python manage.py runserver 8000
```

2. **Run the mock client** (in another terminal):
```bash
python mock_twilio_client.py
```

3. **Speak into your microphone** - the voice assistant will respond just like a real Twilio call!

## Usage Options

### Basic Usage
```bash
python mock_twilio_client.py
```

### Custom Django Host
```bash
python mock_twilio_client.py --host localhost:8001
```

### Custom Caller Number
```bash
python mock_twilio_client.py --caller "+31612345678"
```

### Full Custom Configuration
```bash
python mock_twilio_client.py --host your-ngrok-url.ngrok.io --caller "+31612345678"
```

## How It Works

The mock client simulates the complete Twilio call flow:

1. **HTTP POST Request**: Sends a POST request to `/incoming-call` endpoint with Twilio-formatted data
2. **WebSocket Connection**: Connects to `/ws/media-stream/` WebSocket endpoint
3. **START Event**: Sends the initial `start` event with call metadata
4. **Audio Streaming**: Captures microphone input and streams it as `media` events in μ-law format
5. **Response Handling**: Receives and logs audio responses from the voice assistant
6. **Mark Events**: Sends periodic `mark` events for synchronization

## Event Types Simulated

- ✅ **start**: Initializes the call with metadata (callSid, streamSid, caller number)
- ✅ **media**: Real-time audio data from microphone in μ-law encoding
- ✅ **mark**: Synchronization events for audio timing

## Audio Format

The mock client matches Twilio's exact audio specifications:
- **Encoding**: μ-law (G.711)
- **Sample Rate**: 8000 Hz
- **Channels**: 1 (mono)
- **Chunk Size**: 160 samples (20ms)

## Testing Your Voice Assistant

1. **Language Selection**: The assistant should greet you and ask for language preference
2. **Order Flow**: Try saying "I want to place an order" to test the ordering flow
3. **Status Check**: Try saying "I want to check my order status" to test status checking
4. **Multi-language**: Test different languages by saying "Dutch" or "Turkish"

## Troubleshooting

### Audio Issues
- **No microphone input**: Check your default microphone in system settings
- **PyAudio errors**: Install PortAudio (see installation section)
- **Permission denied**: Grant microphone permissions to your terminal/Python

### Connection Issues
- **Django not running**: Make sure Django server is running on the specified host
- **WebSocket failed**: Check that the WebSocket routing is properly configured
- **HTTP 405 error**: Ensure the `/incoming-call` endpoint accepts POST requests

### Common Logs
- ✅ `Mock call is now active! Speak into your microphone.` - Everything working correctly
- ❌ `Failed to send incoming call: 404` - Django server not running or wrong URL
- ❌ `Failed to connect WebSocket` - WebSocket routing issue or server not running

## Development Tips

- Use `--host localhost:8000` for local development
- Use `--host your-ngrok-url.ngrok.io` to test with ngrok tunnels
- Check Django logs to see how your voice assistant processes the events
- Press `Ctrl+C` to end the mock call cleanly

## Comparison with Real Twilio

| Feature | Mock Client | Real Twilio |
|---------|-------------|-------------|
| HTTP webhook | ✅ Simulated | ✅ Real |
| WebSocket connection | ✅ Local | ✅ Cloud |
| Audio encoding | ✅ μ-law | ✅ μ-law |
| Event types | ✅ start, media, mark | ✅ start, media, mark, stop |
| Real-time streaming | ✅ 20ms chunks | ✅ 20ms chunks |
| Cost | 🆓 Free | 💰 Paid |
| Phone number | 📱 Simulated | ☎️ Real |

This mock client provides 95% of Twilio's functionality for development and testing purposes!