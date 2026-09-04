"""Per-call transcript logging for practice discovery calls.

Same JSONL + human-readable TXT idea as my-ai-caller/transcript_logger.py,
simplified to synchronous file writes since this bot only ever runs one call
at a time (none of that project's concurrent-call buffering concerns apply
here).

Outputs:
  - logs/{call_id}.jsonl -- one JSON event per line
  - logs/{call_id}.txt   -- human-readable conversation summary
"""

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

LOGS_DIR = "logs"


@dataclass
class _Entry:
    ts: str
    kind: str
    text: str = ""


class CallTranscriptLogger:
    def __init__(
        self,
        call_id: str,
        persona_label: str,
        target_extension: str,
        direction: str = "outbound",
    ):
        self._call_id = call_id
        self._persona_label = persona_label
        self._target_extension = target_extension
        self._direction = direction
        self._lock = threading.Lock()
        self._entries: list[_Entry] = []
        self._start_time = time.time()
        self._finalized = False

        os.makedirs(LOGS_DIR, exist_ok=True)
        self._jsonl_path = os.path.join(LOGS_DIR, f"{call_id}.jsonl")
        self._txt_path = os.path.join(LOGS_DIR, f"{call_id}.txt")

        self._log(
            "call_start",
            f"persona={persona_label} direction={direction} ext={target_extension}",
        )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def _log(self, kind: str, text: str = "") -> None:
        entry = _Entry(ts=self._now_iso(), kind=kind, text=text)
        with self._lock:
            self._entries.append(entry)
            with open(self._jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": entry.ts, "event": kind, "text": text}) + "\n")

    def log_error(self, text: str) -> None:
        self._log("error", text)

    def log_persona_speech(self, text: str) -> None:
        self._log("persona_speech", text)

    def log_caller_speech(self, text: str) -> None:
        self._log("caller_speech", text)

    def handle_realtime_event(self, data: dict) -> None:
        """Feeds raw OpenAI Realtime API events; pulls out transcript text.

        Event names confirmed live against the GA API during development
        (see spike scripts): assistant transcript arrives on
        response.output_audio_transcript.done. Caller-side (input) audio
        transcription completion wasn't directly observed in the spike (it
        only exercised text input) so it's matched defensively by suffix in
        case the exact prefix differs from the beta-era
        conversation.item.input_audio_transcription.completed.
        """
        t = data.get("type", "")
        if t == "response.output_audio_transcript.done":
            self.log_persona_speech(data.get("transcript", ""))
        elif t.endswith("input_audio_transcription.completed"):
            self.log_caller_speech(data.get("transcript", ""))
        elif t == "error":
            self._log("error", json.dumps(data.get("error", {})))

    def finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True
        duration_s = round(time.time() - self._start_time, 1)
        self._log("call_end", f"duration_s={duration_s}")
        self._write_txt(duration_s)

    def _write_txt(self, duration_s: float) -> None:
        minutes, seconds = divmod(int(duration_s), 60)
        duration_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
        start_dt = datetime.fromtimestamp(self._start_time).strftime("%Y-%m-%d %H:%M:%S")
        party_label = "Called:  " if self._direction == "outbound" else "From:    "

        lines = [
            "=== Practice Discovery Call ===",
            f"Call ID:  {self._call_id}",
            f"Date:     {start_dt}",
            f"Duration: {duration_str}",
            f"Persona:  {self._persona_label}",
            f"{party_label} extension {self._target_extension}",
            "",
            "--- Conversation ---",
        ]
        with self._lock:
            for entry in self._entries:
                ts_short = entry.ts[11:19]
                if entry.kind == "persona_speech":
                    lines.append(f"[{ts_short}] PERSONA: {entry.text}")
                elif entry.kind == "caller_speech":
                    lines.append(f"[{ts_short}] REP:     {entry.text}")
                elif entry.kind == "error":
                    lines.append(f"    [ERROR] {entry.text}")
        lines.append("")

        with open(self._txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
