import logging
import json
import base64
import websockets
import os

import asyncio
import traceback
from collections import defaultdict
from functools import partial
from django.conf import settings
from common.utils.enums import OpenAIEvent
from integrations.foodticket_client.postcode_check import get_zipcode_info
from integrations.foodticket_client.menu_pull import find_product_by_name
from integrations.foodticket_client.order_info_retrieve import fetch_flat_orders_by_phone_last_3_days
from voice_assistant.state_machine.order_flow import order_flow_states, application_detail_prompt

logger = logging.getLogger(__name__)


INSTRUCTION_PROMPT = """
ROL: Sen "VizeDanışman Ltd." isimli bir vize danışmanlık firmasının telefon asistanısın. 
AMAÇ: Arayan müşterilere sadece aşağıdaki şirket dokümanındaki bilgilerden yararlanarak yardımcı ol. 
DAVRANIŞ: 
- Kısa, net ve nazik cevaplar ver. 
- Eğer dokümanda olmayan bir bilgi sorulursa, "Bu konuda elimde bilgi yok, danışmanlarımız size yardımcı olacaktır." de. 
- Asla tahmin yürütme veya uydurma. 
- Gerektiğinde ek bilgi için yönlendirme yapabilirsin (ör. "Detay için ofisimizle iletişime geçebilirsiniz"). 
- Cevapları konuşma diliyle ver, yazılı rapor gibi değil. 

--- ŞİRKET BİLGİ DOKÜMANI ---
VizeDanışman Ltd., 2010 yılından beri Türkiye’de öğrenci, iş ve turistik vizeler konusunda danışmanlık hizmeti vermektedir. İstanbul, Ankara ve İzmir’de ofislerimiz bulunmaktadır. Her yıl yaklaşık 5000 başvuru sürecinde danışanlarımıza destek olmaktayız.  

Misyonumuz, vize süreçlerini karmaşık ve stresli olmaktan çıkararak hızlı, güvenilir ve şeffaf bir hizmet sunmaktır.  

Çalıştığımız ülkeler:  
- Avrupa: Almanya, Hollanda, Fransa, İtalya, İspanya, Belçika  
- Kuzey Amerika: ABD, Kanada  
- Asya: Japonya, Güney Kore, Çin  
- Orta Doğu: BAE, Katar  

Hizmetlerimiz:  
1. Danışmanlık görüşmesi  
2. Belgelerin hazırlanması  
3. Başvuru takibi  
4. Dil desteği (çeviri)  
5. Ek hizmetler: seyahat sigortası, uçak/otel rezervasyonu  

Ücretler:  
- Standart Paket: 2500 TL  
- Öğrenci İndirimli Paket: 1800 TL  
- VIP Paket: 5000 TL  
(Konsolosluk harçları dahil değildir.)  

Sık Sorulan Sorular:  
- Vizeyi garanti ediyor musunuz? → Hayır, onay tamamen konsolosluk kararına bağlıdır.  
- Ortalama sonuç süresi → Avrupa: 15 iş günü, ABD: 4–6 hafta, Kanada: 6–8 hafta  
- Red alırsam ne olur? → Ret mektubu incelenir, yeni başvuru stratejisi hazırlanır.  

İletişim:  
- Telefon: +90 212 555 00 00  
- E-posta: info@vizedanisman.com  
- Adresler: İstanbul/Şişli, Ankara/Çankaya, İzmir/Konak  
- Çalışma Saatleri: Hafta içi 09:00–18:00, Cumartesi 10:00–15:00  
"""


class OpenAIService:
    def __init__(self, end_call_callback=None):
        self.collected_info = {}
        self.collected_info["params"] = {"error_message": ""}
        self.end_call_key = "end_call"
        self.websocket = None
        self.twilio_service = None
        # self.get_speech_timestamps, _, self.read_audio, _, _ = self.utils
        self.call_sid = ""
        self.end_call_callback = end_call_callback
        self._connection_lock = asyncio.Lock()
        self.is_pick_up = False

    async def open_websocket(self):
        # logger.info(f'Connecting to OpenAI Realtime API with key: {settings.OPENAI_API_KEY}')
        """OpenAI Realtime API'a bağlan."""
        async with self._connection_lock:
            try:
                if self.websocket and not self.websocket.closed:
                    await self.websocket.close()

                self.websocket = await websockets.connect(
                    "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview",
                    extra_headers={
                        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                        "OpenAI-Beta": "realtime=v1",
                    },
                )
                logger.info("Connected to OpenAI realtime API")
                return self.websocket
            except Exception as e:
                logger.error(f"Failed to connect to OpenAI WebSocket: {str(e)}")
                self.websocket = None
                raise

    async def send_session_update_with_prompt(self, prompt: str, tools: list):
        await self.websocket.send(json.dumps({"type": "session.update", "session": {"instructions": prompt, "tools": tools, "tool_choice": "auto"}}))
        await self.websocket.send(json.dumps({"type": "response.create", "response": {"modalities": ["text", "audio"]}}))

    async def send_initial_config(self):
        try:
            if not self.websocket or self.websocket.closed:
                raise ConnectionError("WebSocket is not open or already closed")

            logger.info("Sending initial configuration to OpenAI")

            # Session config (basic prompt ve config)
            await self.websocket.send(
                json.dumps(
                    {
                        "type": OpenAIEvent.SESSION_UPDATE.value,
                        "session": {
                            "turn_detection": {
                                "type": "semantic_vad",
                                "eagerness": "medium",  # You can use "low", "medium", "high", or "auto"
                                "create_response": True,
                                "interrupt_response": True,
                            },
                            "temperature": 0.8,
                            "input_audio_format": "g711_ulaw",
                            "output_audio_format": "g711_ulaw",
                            "voice": "sage",
                            "modalities": ["text", "audio"],
                            "input_audio_transcription": {"model": "whisper-1"},
                            "instructions": application_detail_prompt,
                            "tool_choice": "auto",
                        },
                    }
                )
            )

            # 2. İlk kullanıcı mesajını gönder (konuşmayı başlatmak için)
            await self.websocket.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": "Merhaba, VizeDanışman Ltd.’ye hoş geldiniz. Size nasıl yardımcı olabilirim?"}
                            ],
                        },
                    }
                )
            )

            # İlk response.create gönderiyoruz ki AI sesli yanıt vermeye başlasın.
            # Sadece yukarıdaki session.update'i göndermek konuşmayı başlatmıyor.
            await self.websocket.send(
                json.dumps(
                    {
                        "type": OpenAIEvent.RESPONSE_CREATE.value,
                        "response": {"modalities": ["text", "audio"]},
                    }
                )
            )
            logger.info("Initial configuration HAS SENT to OpenAI")

        except Exception as e:
            logger.error(f"Error in send_initial_config: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Close WebSocket on critical error
            await self.force_close_websocket()
            raise

    async def send_audio(self, payload: str):
        """Twilio'dan gelen ses verisini OpenAI'a gönder."""
        # Decode the base64 audio payload
        audio_data = base64.b64decode(payload)

        # Use Silero VAD to detect speech
        wav = self.read_audio(audio_data)
        speech_timestamps = True  # self.get_speech_timestamps(wav, self.model)

        if speech_timestamps:
            await self.websocket.send(
                json.dumps({"type": OpenAIEvent.INPUT_AUDIO_BUFFER_APPEND.value, "audio": payload})  # Send the original payload if speech is detected
            )
        else:
            logger.info("No speech detected in the audio segment")

    async def forward_audio_to_openai(self, media_data):
        try:
            """Twilio’dan gelen base64 ses verisini OpenAI’a ilet."""
            # audio_payload = media_data.get("media", {}).get("payload")
            audio_payload = media_data["media"]["payload"]
            if not audio_payload:
                logger.warning("No audio payload found in media data")
                return

            payload = {
                "type": OpenAIEvent.INPUT_AUDIO_BUFFER_APPEND.value,
                "audio": audio_payload,
            }
            # logger.info(f"Forwarding audio to OpenAI: {payload}")
            await self.websocket.send(json.dumps(payload))
            # logger.info("Audio payload HAS SENT to OpenAI")

        except Exception as e:
            logger.error(f"Error while forwarding audio to OpenAI: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Close WebSocket on critical error
            await self.force_close_websocket()
            raise

    async def close_websocket(self):
        """Gracefully close the WebSocket connection."""
        async with self._connection_lock:
            try:
                if self.websocket and not self.websocket.closed:
                    await self.websocket.close()
                    logger.info("OpenAI WebSocket gracefully closed")
            except Exception as e:
                logger.error(f"Error during graceful WebSocket close: {str(e)}")
            finally:
                self.websocket = None

    async def force_close_websocket(self):
        """Force close the WebSocket connection without waiting for graceful shutdown."""
        try:
            if self.websocket:
                if not self.websocket.closed:
                    # Force close without waiting
                    await self.websocket.close(code=1000, reason="Emergency shutdown")
                self.websocket = None
                logger.warning("OpenAI WebSocket force closed")
        except Exception as e:
            logger.error(f"Error during force WebSocket close: {str(e)}")
            # Set to None regardless of errors
            self.websocket = None

    # async def end_call(self):
    #     """Twilio aramasını sonlandır."""
    #     try:
    #         await self.twilio_service.end_call()
    #     except Exception as e:
    #         logger.error(f"openai_service : Failed to end call {self.call_sid}: {str(e)}")

    async def end_call(
        self,
        message: str = "Thank you for calling. Goodbye!",
    ):
        """Kullanıcıya vedayı iletip ardından Twilio aramasını sonlandır.

        message: Konuşma bitmeden önce söylenecek metin.
        """
        try:
            # 1. Kullanıcıya mesajı söylet
            # await self.websocket.send(json.dumps({
            #     "type": "conversation.item.create",
            #     "item": {
            #         "type": "message",
            #         " ": "assistant",
            #         "content": [{"type": "text", "text": message}]
            #     }
            # }))

            # 1. Kullanıcıya mesajı söylet
            await self.websocket.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": f"Say '{message}'",
                                }
                            ],
                        },
                    }
                )
            )
            await self.websocket.send(
                json.dumps(
                    {
                        "type": OpenAIEvent.RESPONSE_CREATE.value,
                        "response": {"modalities": ["text", "audio"]},
                    }
                )
            )
            logger.info("Sent farewell message to user")

            # 2. Kısa bir süre bekle (OpenAI mesajı söylemeye başlasın)
            await asyncio.sleep(3)  # ihtiyaca göre 2–3 sn yeterli olur

            # 3. Twilio aramasını sonlandır
            await self.twilio_service.end_call()
            logger.info(f"Call {self.call_sid} ended.")

        except Exception as e:
            logger.error(f"openai_service: Failed to end call {self.call_sid}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
