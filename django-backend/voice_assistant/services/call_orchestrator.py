import logging
import json
import asyncio
import time
import traceback
import os
from voice_assistant.services.twilio_service import TwilioService
from voice_assistant.services.openai_service import OpenAIService
from voice_assistant.services.call_session_manager import CallSessionManager
from common.utils.enums import TwilioEvent, OpenAIEvent


logger = logging.getLogger(__name__)


class CallOrchestrator:
    def __init__(self, consumer, is_test=False):
        self.call_sid = ""
        self.stream_sid = ""
        # self.fsm = ConversationFSM(order_flow_states, "entry")
        self.response_start_timestamp_twilio = None
        self.consumer = consumer  # MediaStreamConsumer örneği
        self.openai_service = OpenAIService(end_call_callback=self.shutdown)
        self.twilio_service = TwilioService()
        self.openai_service.twilio_service = self.twilio_service
        self.twilio_service.openai_service = self.openai_service
        self.session_manager = CallSessionManager()
        self.openai_ws = None
        self.openai_listener_task = None
        self.mark_timestamps = []
        self.awaiting_new_deltas = True
        self.response_start_timestamp = None
        self.active_item_id = None
        self.latest_media_timestamp = None
        self.caller_number = None
        self._is_shutting_down = False
        self._shutdown_event = asyncio.Event()
        self.is_twillio_printed = False
        self.call_start_time = None
        self.call_timer_task = None
        # 2 minutes in seconds
        self.max_call_duration = 120
        self._timer_ended_call = False

    async def start(self):
        """OpenAI WS başlatılır ve session oluşturulur."""
        try:
            self.openai_ws = await self.openai_service.open_websocket()
            self.openai_listener_task = asyncio.create_task(self._listen_openai_events_with_exception_handling())
            self.session_manager.create_session(self.call_sid)
            self.session_manager.set_openai_ws(self.openai_ws)

            # Start call timer
            self.call_start_time = time.time()
            self.call_timer_task = asyncio.create_task(self._call_timer())
            logger.info(f"Call started with {self.max_call_duration} second timer")
        except Exception as e:
            logger.error(f"Error during start: {str(e)}")
            await self._emergency_cleanup()
            raise

    async def update_call_sid(self, call_sid: str):
        """Twilio'dan gelen çağrı SID'ini güncelle."""
        self.call_sid = call_sid
        self.twilio_service.call_sid = call_sid
        self.openai_service.call_sid = call_sid
        # await CallSessionManager.set_stream_sid(self.call_sid, self.stream_sid)
        # await CallSessionManager.set_caller_number(self.call_sid, self.caller_number)
        # await CallSessionManager.set_openai_ws(self.call_sid, self.openai_ws)

    async def handle_twilio_event(self, event_type: str, data: dict):
        # logger.info(f"test1 events --{(event_type, data)}--")
        """Twilio'dan gelen olayı uygun servise yönlendir."""
        try:
            if self._is_shutting_down:
                if not self.is_twillio_printed:
                    logger.warning(f"Ignoring Twilio event {event_type} during shutdown")
                    self.is_twillio_printed = True
                return

            if event_type == TwilioEvent.START.value:
                logger.info("RECEIVED TWILIO START EVENT")
                call_sid = data.get("start", {}).get("callSid")
                self.call_sid = call_sid
                logger.info(f"CURRENT_Call_SID: {call_sid}")
                # stream_sid = data.get("streamSid")

                await self.start()
                await self.update_call_sid(call_sid)

                # self.stream_sid = stream_sid
                # TODO: Twilio'dan gelen start event verisini session manager'e kaydet
                stream_sid_and_caller_number = await self.twilio_service.get_stream_sid_and_caller_number_from_start_event_payload(data)
                self.stream_sid = stream_sid_and_caller_number["stream_sid"]
                await self.openai_service.send_initial_config()

            elif event_type == TwilioEvent.MEDIA.value:
                # raise NotImplementedError("Twilio MEDIA event handling is not implemented yet.")
                # logger.info("RECEIVED TWILIO MEDIA EVENT")
                self.latest_media_timestamp = data.get("media", {}).get("timestamp")
                await self.openai_service.forward_audio_to_openai(data)

            elif event_type == TwilioEvent.MARK.value:
                # logger.info("RECEIVED MARK EVENT")
                # Eğer bir mark timestamp'ı varsa sıradan çıkar
                if self.mark_timestamps:
                    self.mark_timestamps.pop(0)

            else:
                logger.warning(f"Unhandled event type: {event_type}")

        except Exception as e:
            logger.error(f"Exception in handle_twilio_event: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Trigger emergency cleanup
            await self._emergency_cleanup()
            raise

    async def _listen_openai_events_with_exception_handling(self):
        """OpenAI'dan gelen sesli yanıtları Twilio'ya iletir with exception handling."""
        try:
            await self.listen_openai_events()
        except Exception as e:
            logger.error(f"Critical error in OpenAI listener: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self._emergency_cleanup()
            raise

    async def listen_openai_events(self):
        """OpenAI'dan gelen sesli yanıtları Twilio'ya iletir."""
        try:
            async for message in self.openai_ws:
                logger.debug(f"{message}")

                # Check if shutdown is requested
                if self._shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping OpenAI event listener")
                    break

                parsed = json.loads(message)
                event_type = parsed.get("type")
                # logger.info(f"OpenAI event received: {event_type}")

                if event_type == OpenAIEvent.RESPONSE_AUDIO_DELTA.value:
                    logger.info(f"[EVENT] RESPONSE_AUDIO_DELTA")
                    # logger.debug("NEW DELTA EVENT ARRIVED")
                    audio_payload = parsed["delta"]

                    item_id = parsed.get("item_id")
                    if self.active_item_id != item_id:
                        self.active_item_id = item_id
                        self.response_start_timestamp = self.latest_media_timestamp
                        # self.starting_time_of_current_delta = self._now_timestamp()
                        logger.debug(f"New item started: {item_id}")

                    await self.consumer.send(
                        text_data=json.dumps({"event": "media", "streamSid": self.stream_sid, "media": {"payload": audio_payload}})
                    )

                    await self.send_mark_to_twilio()  # her audio delta'dan sonra mark gönder

                elif event_type == OpenAIEvent.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA.value:
                    # This event includes partial updates, logging RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA_DONE instead.
                    pass

                elif event_type == OpenAIEvent.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE.value:
                    logger.info(f"[EVENT] RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE: {parsed}")

                elif event_type == OpenAIEvent.INPUT_TRANSCRIPTION_DONE.value:
                    logger.info(f"[EVENT] INPUT_TRANSCRIPTION_DONE : {parsed}")
                    logger.debug("!!! OpenAI input transcription done !!!")
                    transcript = parsed.get("transcript", "")
                    logger.debug(f"Input transcript: {transcript}")

                    # Log to EventLog table
                    from db.models import EventLog

                    await EventLog.objects.acreate(
                        call_session_id=self.call_sid, event_name=OpenAIEvent.INPUT_TRANSCRIPTION_DONE.value, event_data=parsed
                    )

                elif event_type == OpenAIEvent.RESPONSE_AUDIO_TRANSCRIPT_DONE.value:
                    logger.info(f"[EVENT] RESPONSE_AUDIO_TRANSCRIPT_DONE")
                    logger.debug("!!! OpenAI response audio transcript done !!!")
                    transcript = parsed.get("transcript", "")
                    logger.debug(f"Response audio transcript: {transcript}")

                    # Log to EventLog table
                    from db.models import EventLog

                    await EventLog.objects.acreate(
                        call_session_id=self.call_sid, event_name=OpenAIEvent.RESPONSE_AUDIO_TRANSCRIPT_DONE.value, event_data=parsed
                    )

                elif event_type == OpenAIEvent.RESPONSE_DONE.value:
                    logger.info(f"[EVENT] RESPONSE_DONE: {parsed}")
                    self.awaiting_new_deltas = True

                elif event_type == OpenAIEvent.RESPONSE_TEXT_DONE.value:
                    logger.info(f"[EVENT] RESPONSE_TEXT_DONE")
                    self.response_start_timestamp = None

                elif event_type == OpenAIEvent.INPUT_AUDIO_SPEECH_STARTED.value:
                    logger.info(f"[EVENT] INPUT_AUDIO_SPEECH_STARTED")
                    # logger.info(f'AWAITING_RESPONSE: {self.awaiting_response} , LAST_ASSISTANT_ITEM_ID: {self.last_assistant_item_id}')
                    # await self._handle_interruption()
                    # time.sleep(0.5)  # biraz beklesin daha insan vari oluyor
                # elif event_type == OpenAIEvent.FUNCTION_CALL.value:
                #     logger.info(f"[EVENT] FUNCTION_CALL")
                #     await self.openai_service.handle_function_call(parsed)

        except Exception as e:
            logger.error(f"Error in listen_openai_events: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def _handle_interruption(self):
        logger.debug("Start _handle_interruption")
        logger.info("User interrupted, cancelling assistant response")

        # 2. Clear Twilio buffer
        await self.consumer.send(text_data=json.dumps({"event": "clear", "streamSid": self.stream_sid}))
        logger.debug("Sent clear event to Twilio")

        logger.debug("End _handle_interruption")

    def _now_timestamp(self) -> int:
        """
        Returns the current UTC timestamp in milliseconds.
        Used for measuring audio timing for truncation etc.
        """
        return int(time.time() * 1000)

    async def _call_timer(self):
        """Timer task that ends the call after max_call_duration seconds."""
        try:
            await asyncio.sleep(self.max_call_duration)

            if not self._is_shutting_down:
                call_duration = time.time() - self.call_start_time if self.call_start_time else 0
                logger.warning(f"Call exceeded maximum duration of {self.max_call_duration} seconds (actual: {call_duration:.1f}s). Ending call.")
                self._timer_ended_call = True
                await self.shutdown()
        except asyncio.CancelledError:
            logger.info("Call timer cancelled (call ended normally)")
        except Exception as e:
            logger.error(f"Error in call timer: {str(e)}")
            if not self._is_shutting_down:
                await self._emergency_cleanup()

    async def send_mark_to_twilio(self):
        """Twilio'ya bir mark event'i gönder ve zamanını sıraya al."""
        if not self.stream_sid:
            return

        await self.consumer.send(text_data=json.dumps({"event": "mark", "streamSid": self.stream_sid, "mark": {"name": "responsePart"}}))

        # Mark gönderildiği anın timestamp'ini sıraya al
        self.mark_timestamps.append(self._now_timestamp())

    def set_caller_number(self, caller_number):
        self.caller_number = caller_number
        self.openai_service.collected_info_update("caller_number", caller_number)

    async def shutdown(self):
        logger.warning("shutdown is called")
        """Çağrı kapatıldığında cleanup işlemleri."""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        self._shutdown_event.set()

        try:
            # Log call duration
            if self.call_start_time:
                call_duration = time.time() - self.call_start_time
                if self._timer_ended_call:
                    logger.warning(f"Call {self.call_sid} ended by timer after {call_duration:.1f} seconds (max: {self.max_call_duration}s)")
                else:
                    logger.info(f"Call {self.call_sid} ended normally after {call_duration:.1f} seconds")

            # Cancel call timer task
            if self.call_timer_task and not self.call_timer_task.done():
                self.call_timer_task.cancel()
                try:
                    await asyncio.wait_for(self.call_timer_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.debug("Call timer task cancelled during shutdown")

            # Cancel OpenAI listener task
            if self.openai_listener_task and not self.openai_listener_task.done():
                self.openai_listener_task.cancel()
                try:
                    await asyncio.wait_for(self.openai_listener_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.warning("OpenAI listener task cancelled or timed out during shutdown")

            # Close OpenAI WebSocket
            await self.openai_service.close_websocket()

            # Clean up session
            self.session_manager.delete_session()

            logger.info(f"Shutdown completed for call {self.call_sid}")

        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            # Ensure critical cleanup even if some operations fail
            await self._emergency_cleanup()

        # Close consumer connection after cleanup
        time.sleep(5)
        await self.consumer.close()

    async def _emergency_cleanup(self):
        logger.warning("Emergency cleanup is called")
        """Emergency cleanup to ensure WebSockets are closed even if regular shutdown fails."""
        if self._is_shutting_down:
            return

        logger.warning("Performing emergency cleanup")
        self._is_shutting_down = True
        self._shutdown_event.set()

        cleanup_tasks = []

        # Force close OpenAI WebSocket
        if hasattr(self, "openai_service") and self.openai_service:
            cleanup_tasks.append(self.openai_service.force_close_websocket())

        # Cancel OpenAI listener task
        if hasattr(self, "openai_listener_task") and self.openai_listener_task and not self.openai_listener_task.done():
            self.openai_listener_task.cancel()

        # Cancel call timer task
        if hasattr(self, "call_timer_task") and self.call_timer_task and not self.call_timer_task.done():
            self.call_timer_task.cancel()

        # Clean up session
        if hasattr(self, "session_manager") and self.session_manager:
            self.session_manager.delete_session()

        # Execute all cleanup tasks with timeout
        if cleanup_tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*cleanup_tasks, return_exceptions=True), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("Emergency cleanup timed out")
            except Exception as e:
                logger.error(f"Error during emergency cleanup: {str(e)}")

        logger.info("Emergency cleanup completed")
