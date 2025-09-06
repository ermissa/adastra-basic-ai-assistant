from enum import Enum


class OpenAIEvent(Enum):
    # Sent by OpenAI → Client
    # Sent once session is successfully created
    SESSION_CREATED = "session.created"

    # Sent by Client → OpenAI
    # Used to configure the session (voice, language, tools, etc.)
    SESSION_UPDATE = "session.update"

    # Sent by Client → OpenAI
    # Starts generation of assistant’s response
    RESPONSE_CREATE = "response.create"

    # Sent by OpenAI → Client
    # Audio stream chunks from assistant (base64-encoded)
    RESPONSE_AUDIO_DELTA = "response.audio.delta"

    # Sent by OpenAI → Client
    # Emitted when there is a partial function-call arguments delta.
    # Ref: https://platform.openai.com/docs/api-reference/responses_streaming/response/function_call_arguments/delta
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA = "response.function_call_arguments.delta"

    # Sent by OpenAI → Client
    # Emitted when function-call arguments are finalized
    # Ref: https://platform.openai.com/docs/api-reference/responses_streaming/response/function_call_arguments/done
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE = "response.function_call_arguments.done"

    # Sent by OpenAI → Client
    # Indicates assistant's full response has been generated
    RESPONSE_DONE = "response.done"

    # Sent by OpenAI → Client
    # Final audio transcript of the assistant's response
    RESPONSE_AUDIO_TRANSCRIPT_DONE = "response.audio_transcript.done"

    # Sent by OpenAI → Client
    # Optional: Indicates full text is ready (before or after audio)
    RESPONSE_TEXT_DONE = "response.text.done"

    # Sent by OpenAI → Client
    # Assistant wants to call a function/tool (tool_choice: auto)
    FUNCTION_CALL = "response.function_call_arguments.done"

    # Sent by OpenAI → Client
    # Final transcription of user input using Whisper
    INPUT_TRANSCRIPTION_DONE = "conversation.item.input_audio_transcription.completed"

    # Sent by OpenAI → Client
    # Internal: Indicates audio buffer has been committed
    INPUT_AUDIO_BUFFER_COMMITTED = "input_audio_buffer.committed"

    # Sent by Client → OpenAI
    # Sent by client to stream new audio to the assistant (typically from user mic)
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"

    # Sent by OpenAI → Client
    # Indicates user has started speaking (used for interruption logic)
    INPUT_AUDIO_SPEECH_STARTED = "input_audio_buffer.speech_started"

    # Sent by OpenAI → Client
    # Indicates user has stopped speaking (assistant can now respond)
    INPUT_AUDIO_SPEECH_STOPPED = "input_audio_buffer.speech_stopped"

    # Sent by OpenAI → Client
    # Error in connection, parsing, auth, or runtime
    ERROR = "error"


class TwilioEvent(Enum):
    # Sent by Twilio → Server
    # Marks the beginning of a media stream; includes parameters (e.g., callerNumber)
    START = "start"

    # Sent by Twilio → Server
    # Audio data chunk (base64-encoded µ-law payload)
    MEDIA = "media"

    # Sent by Twilio → Server
    # Optional: Indicates progress in the stream (can be used to sync or mark)
    MARK = "mark"

    # Sent by Twilio → Server
    # Indicates the stream has ended (call may be disconnected)
    STOP = "stop"

    # Sent by Server → Twilio
    # Clears audio buffer on Twilio’s end (e.g., when user interrupts assistant)
    CLEAR = "clear"

    # Sent by Server → Twilio
    # Sends metadata marker to Twilio (used to coordinate interaction timing)
    RESPONSE_MARK = "mark"
