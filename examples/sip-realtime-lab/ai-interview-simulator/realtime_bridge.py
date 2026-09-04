"""OpenAI Realtime API bridge: runs the websocket session on its own asyncio
event loop (in a background thread), exchanging raw G.711 u-law audio with
the SIP side via two thread-safe queues.

Schema confirmed live against the GA API (Aug 2026) -- see the two spike
scripts run during development. Key points that aren't obvious from memory
of the older beta API:
  - Connect: wss://api.openai.com/v1/realtime?model=<model>, plain
    `Authorization: Bearer <key>` header (no separate beta header needed).
  - session.update uses a nested `session.audio.input/output.format` object,
    not the old flat `input_audio_format`/`output_audio_format` fields.
  - The G.711 u-law format string is "audio/pcmu" (not "g711_ulaw").
  - Assistant audio/transcript events are `response.output_audio.delta` /
    `response.output_audio_transcript.delta` (renamed from the old
    `response.audio.delta` / `response.audio_transcript.delta`).
"""

import asyncio
import base64
import json
import logging
import queue
import threading
from typing import Callable, Optional

import websockets

logger = logging.getLogger("realtime_bridge")

REALTIME_URL_TMPL = "wss://api.openai.com/v1/realtime?model={model}"


class RealtimeBridge:
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        voice: str,
        sip_to_ai: "queue.Queue[Optional[bytes]]",
        ai_to_sip: "queue.Queue[bytes]",
        on_event: Optional[Callable[[dict], None]] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.voice = voice
        self.sip_to_ai = sip_to_ai
        self.ai_to_sip = ai_to_sip
        self.on_event = on_event or (lambda e: None)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._ws = None
        self.crashed: Optional[BaseException] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="realtime-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.sip_to_ai.put(None)  # unblock the sip->ai pump promptly
        # If _main() raised (e.g. the websocket was rejected/closed by the
        # server -- confirmed live via an "insufficient_quota" close during
        # a real call), _run()'s finally already closed self._loop before
        # we ever get here. Scheduling onto a closed loop raises
        # "RuntimeError: Event loop is closed", which -- since stop() is
        # itself called from a finally block in main.py -- was masking the
        # real error and skipping transcript.finalize() entirely.
        if self._loop is not None and self._ws is not None and not self._loop.is_closed():
            fut = asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            try:
                fut.result(timeout=5)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception as e:
            logger.exception("Realtime bridge crashed")
            self.crashed = e
        finally:
            self._loop.close()

    async def _main(self) -> None:
        url = REALTIME_URL_TMPL.format(model=self.model)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        logger.info("Connecting to OpenAI Realtime API (%s)...", self.model)
        async with websockets.connect(url, additional_headers=headers) as ws:
            self._ws = ws
            await ws.recv()  # session.created
            await ws.send(json.dumps(self._session_update()))
            await asyncio.gather(
                self._pump_sip_to_ai(ws),
                self._pump_ai_events(ws),
            )

    def _session_update(self) -> dict:
        return {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "instructions": self.system_prompt,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "transcription": {"model": "whisper-1"},
                        "turn_detection": {"type": "server_vad"},
                    },
                    "output": {
                        "format": {"type": "audio/pcmu"},
                        "voice": self.voice,
                    },
                },
            },
        }

    async def _pump_sip_to_ai(self, ws) -> None:
        loop = asyncio.get_event_loop()
        while not self._stop_event.is_set():
            try:
                chunk = await loop.run_in_executor(None, self.sip_to_ai.get, True, 0.5)
            except queue.Empty:
                continue
            if chunk is None:
                break
            try:
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(chunk).decode("ascii"),
                }))
            except websockets.exceptions.ConnectionClosed:
                break

    async def _pump_ai_events(self, ws) -> None:
        try:
            async for raw in ws:
                data = json.loads(raw)
                self.on_event(data)
                t = data.get("type")
                if t == "response.output_audio.delta":
                    self.ai_to_sip.put(base64.b64decode(data["delta"]))
                elif t == "error":
                    logger.error("Realtime API error: %s", data)
                if self._stop_event.is_set():
                    break
        except websockets.exceptions.ConnectionClosed:
            pass
