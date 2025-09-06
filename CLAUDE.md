# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

Adastra Telecenter is a multi-language voice assistant for pizza ordering using Django Channels, Twilio Voice API, and OpenAI's Realtime API. The system handles real-time voice conversations in English, Dutch, and Turkish through WebSocket connections.

**Core Pattern**: State Machine-driven conversation flow with circular service dependencies between CallOrchestrator, TwilioService, OpenAIService, and CallSessionManager.

## Key Commands

### Development
```bash
# Start Django development server
cd django-backend
python manage.py runserver 8000

# Start production ASGI server
cd django-backend
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# Test locally without phone calls
python mock_twilio_client/mock_twilio_client.py

# Install dependencies
pip install -r requirements.txt
```

### Testing
```bash
# Run Django tests
cd django-backend
python manage.py test

# Mock Twilio client for local testing
python mock_twilio_client/mock_twilio_client.py --host localhost:8000
```

### Database
```bash
# Apply migrations
cd django-backend
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

## Project Structure

**`django-backend/`** - Main Django application
- **`voice_assistant/`** - Core voice processing with state machine in `state_machine/`
- **`ai_core/`** - LLM operations and RAG functionality
- **`integrations/`** - External service integrations (restaurant systems)
- **`db/`** - Custom database operations

**`mock_twilio_client/`** - Local testing without Twilio charges
- Complete Twilio MediaStream simulation with μ-law audio encoding
- Use for development instead of actual phone calls

## Configuration

**Environment Variables** (`.env` in `django-backend/`):
- `OPENAI_API_KEY` - OpenAI Realtime API access
- `TWILIO_ACCOUNT_SID` - Twilio credentials
- `TWILIO_AUTH_TOKEN` - Twilio authentication

**Key Files**:
- `django-backend/backend/settings.py` - Main Django config with API keys
- `django-backend/backend/asgi.py` - WebSocket routing configuration
- `django-backend/voice_assistant/routing.py` - WebSocket endpoint routing

## State Machine Flow

Conversation states: `ENTRY → PICKUP_OR_DELIVERY → ASK_ADDRESS → ASK_ITEM → ASK_SIZE → CONFIRM_ORDER → END_CALL`

States are managed in `voice_assistant/state_machine/states.py` with language-specific prompts and context preservation across WebSocket connections.

## WebSocket Architecture

- Django Channels with ASGI deployment
- Real-time bidirectional audio streaming
- Twilio MediaStream integration on `/ws/media-stream/`
- OpenAI Realtime API connection for voice processing

## Multi-Language Support

Language detection and switching handled in conversation flow with localized prompts for English, Dutch, and Turkish markets in `state_machine/` directory.