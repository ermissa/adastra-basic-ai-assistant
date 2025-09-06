# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Adastra Telecenter is a multi-language voice assistant application for pizza ordering and customer service. It integrates Twilio Voice API with OpenAI's Realtime API to provide phone-based AI assistance in English, Dutch, and Turkish.

## Common Development Commands

### Django Development Server
```bash
cd django-backend
python manage.py runserver 8000
```

### Database Operations
```bash
cd django-backend
python manage.py makemigrations
python manage.py migrate
```

### WebSocket/ASGI Server (for production)
```bash
cd django-backend
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

### Environment Setup
```bash
source myvenv/bin/activate
pip install -r requirements.txt
```

### Testing
```bash
cd django-backend
python manage.py test
```

## Architecture Overview

### State Machine Architecture
The voice conversation flow is managed by a sophisticated state machine in `voice_assistant/state_machine/`:

- **States**: ENTRY → PICKUP_OR_DELIVERY → ASK_ADDRESS → ASK_ITEM → ASK_SIZE → CONFIRM_ORDER → END_CALL
- **Multi-language support**: EN, NL, TR with language-specific prompts
- **Context management**: Maintains conversation state across WebSocket connections

### Core Components

#### Voice Assistant (`voice_assistant/`)
- **Call Orchestrator**: Main coordination logic for voice calls
- **Session Manager**: Manages call sessions and WebSocket connections  
- **OpenAI Service**: Interfaces with OpenAI Realtime API
- **Twilio Service**: Handles Twilio Voice API integration

#### AI Core (`ai_core/`)
- **LLM Integration**: LangChain-based AI orchestration
- **RAG System**: Vector embeddings for product information
- **Tools Provider**: OpenAI function calling capabilities

#### External Integrations (`integrations/`)
- **Foodticket Client**: Menu pulling, order placement, status checking
- **Address Validation**: Postcode and delivery area verification

### Technology Stack

- **Backend**: Django 5.2 with Django Channels for WebSocket support
- **AI**: OpenAI Realtime API, LangChain, PyTorch
- **Voice**: Twilio Voice API with Media Streams
- **Database**: SQLite (dev) / PostgreSQL with pgvector (prod)
- **Communication**: WebSocket bidirectional streaming

## Environment Configuration

Required environment variables in `django-backend/.env`:
- `OPENAI_API_KEY`: OpenAI API key
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`: Twilio credentials
- `ASSISTANT_LANGUAGE`: Language setting (en/nl/tr)
- `DROPBOX_ACCESS_TOKEN`: File storage access

## Development Workflow

### Local Development with Ngrok
```bash
# Terminal 1: Start ngrok tunnel
ngrok http 8000

# Terminal 2: Start Django server
cd django-backend
python manage.py runserver 8000
```

### Database Options
- **SQLite**: Default for development (`django-backend/db.sqlite3`)
- **PostgreSQL**: Available via Docker Compose with vector support

### Multi-language Support
Language configuration via `ASSISTANT_LANGUAGE` environment variable affects:
- Prompt templates in `state_machine/conversation_prompt_provider.py`
- Response generation in conversation flows
- Business logic adaptation per language/region

## Key Business Logic

### Conversation Flow
1. **Language Selection**: Automatic or manual language detection
2. **Intent Classification**: Order placement vs status checking  
3. **Order Type**: Pickup vs delivery with address validation
4. **Menu Interaction**: Item selection with size options
5. **Order Confirmation**: Integration with Foodticket API

### Real-time Features
- **Interrupt Handling**: Natural conversation with AI preemption
- **WebSocket Streaming**: Bidirectional audio between Twilio and OpenAI
- **Session Management**: Persistent state across conversation turns

## Code Organization

- **Service Layer**: Business logic abstraction in `services/` directories
- **State Management**: Centralized conversation state in `voice_assistant/state_machine/`
- **Integration Layer**: External API clients in `integrations/`
- **Common Utilities**: Shared enums and utilities in `common/`

## Testing Notes

Test files exist but contain minimal placeholder code. Run tests with:
```bash
cd django-backend
python manage.py test
```