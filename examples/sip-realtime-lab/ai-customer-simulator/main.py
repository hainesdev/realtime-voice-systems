"""CLI entry point for a dedicated test extension that either places an
outbound call or listens for inbound calls, bridging audio to an OpenAI
Realtime buyer persona until hangup.

Usage:
    python main.py --list-personas
    python main.py --persona property_ops
    python main.py --listen [--persona property_ops]
"""

import argparse
import logging
import os
import queue
import sys
import threading
import time
import uuid
from typing import Optional

from dotenv import load_dotenv

from personas import PERSONAS, get_persona, system_prompt_for
from pyVoIP.VoIP.VoIP import CallState, VoIPCall
from realtime_bridge import RealtimeBridge
from sip_phone import SipPhone
from transcript_logger import CallTranscriptLogger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

REQUIRED_ENV_VARS = [
    "PBX_HOST",
    "EXTENSION_101_NUMBER",
    "EXTENSION_101_SECRET",
    "OPENAI_API_KEY",
]


def parse_args():
    parser = argparse.ArgumentParser(description="AI buyer-persona practice caller")
    parser.add_argument("--persona", choices=sorted(PERSONAS), help="Which persona to simulate")
    parser.add_argument("--prompt-file", help="Use this file's text as the system prompt instead of a persona (for receptionist E2E tests)")
    parser.add_argument("--target", help="Authorized number or extension to dial (overrides TARGET_EXTENSION)")
    parser.add_argument("--max-seconds", type=int, default=0, help="Auto-hang-up after N seconds (0 = wait for the far end)")
    parser.add_argument("--dtmf", help="Send these DTMF digits shortly after the call connects (e.g. 9 to test the decline path)")
    parser.add_argument("--list-personas", action="store_true", help="List available personas and exit")
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Register and wait for inbound calls instead of dialing out",
    )
    return parser.parse_args()


def prompt_persona_choice() -> str:
    """Interactively asks which persona should handle inbound calls this run."""
    slugs = sorted(PERSONAS)
    print("No --persona given. Select a persona for inbound calls:")
    for i, slug in enumerate(slugs, 1):
        p = PERSONAS[slug]
        print(f"  {i}. {slug:20s} {p.label} ({p.character_name}, {p.company})")
    while True:
        choice = input("Persona [number or name]: ").strip()
        if choice in PERSONAS:
            return choice
        if choice.isdigit() and 1 <= int(choice) <= len(slugs):
            return slugs[int(choice) - 1]
        print(f"Invalid choice: {choice!r}")


def check_env() -> None:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print(f"Missing required .env values: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill these in first.", file=sys.stderr)
        sys.exit(1)


def run_audio_loop(
    phone: SipPhone, bridge: RealtimeBridge, sip_to_ai: "queue.Queue", ai_to_sip: "queue.Queue"
) -> None:
    """Runs on the calling thread: pumps SIP audio -> sip_to_ai, and drains
    ai_to_sip -> the call, until the call ends or the bridge crashes.

    Without the bridge.crashed check, a dead bridge (e.g. OpenAI rejecting
    the connection for insufficient_quota -- confirmed live) left the call
    connected with dead air on both ends until whoever was on the phone gave
    up and hung up manually, since read_ulaw() keeps returning real audio
    frames from the SIP side even though nothing is consuming them anymore.
    """
    stop = threading.Event()
    # u-law silence, one 20 ms frame. When the persona isn't talking we still
    # emit these so pyVoIP keeps transmitting RTP at a steady 50 fps -- else
    # Asterisk's symmetric-RTP (comedia) binding to our LAN address goes stale
    # within a few seconds and the receptionist's audio stops reaching us.
    SILENCE = b"\xff" * 160
    FRAME = 160

    def writer():
        buf = bytearray()
        next_tick = time.monotonic()
        while not stop.is_set():
            # Pull whatever the bridge has produced without blocking the cadence.
            try:
                while True:
                    buf.extend(ai_to_sip.get_nowait())
            except queue.Empty:
                pass
            frame = bytes(buf[:FRAME]) if len(buf) >= FRAME else SILENCE
            if len(buf) >= FRAME:
                del buf[:FRAME]
            try:
                phone.write_ulaw(frame)
            except Exception:
                logger.exception("Failed writing audio to call")
                break
            next_tick += 0.02
            sleep = next_tick - time.monotonic()
            if sleep > 0:
                time.sleep(sleep)
            elif sleep < -0.2:            # fell far behind; resync
                next_tick = time.monotonic()

    writer_thread = threading.Thread(target=writer, name="ai-to-sip-writer", daemon=True)
    writer_thread.start()

    # Read at a steady 50 fps, non-blocking: feed the AI a continuous real-time
    # stream (silence included) rather than stalling its input buffer whenever
    # the line goes quiet -- a stalled input wrecks the far-end VAD's sense of
    # timing and it stops taking its turn.
    try:
        next_tick = time.monotonic()
        while phone.state == CallState.ANSWERED and bridge.crashed is None:
            chunk = phone.read_ulaw(blocking=False)
            sip_to_ai.put(chunk if chunk else SILENCE)
            next_tick += 0.02
            slp = next_tick - time.monotonic()
            if slp > 0:
                time.sleep(slp)
            elif slp < -0.2:
                next_tick = time.monotonic()
    finally:
        stop.set()
        writer_thread.join(timeout=2)


def describe_bridge_crash(exc: BaseException) -> str:
    text = str(exc)
    if "insufficient_quota" in text or "credit_balance_exhausted" in text:
        return (
            "OpenAI account is out of API credit/quota -- check "
            "https://platform.openai.com/settings/organization/billing"
        )
    return f"{type(exc).__name__}: {exc}"


def run_call(
    phone: SipPhone,
    persona_slug: str,
    call_id: str,
    other_extension: str,
    direction: str,
    openai_key: str,
    openai_model: str,
    prompt_override: str = "",
) -> None:
    """Bridges one already-answered call (phone.call set, state ANSWERED) to
    a persona conversation until hangup. Shared by the outbound and inbound
    (--listen) flows. prompt_override replaces the persona prompt for E2E tests."""
    if prompt_override:
        label, voice, prompt = "e2e-caller", "alloy", prompt_override
    else:
        persona = get_persona(persona_slug)
        label, voice, prompt = persona.label, persona.voice, system_prompt_for(persona_slug)
    transcript = CallTranscriptLogger(call_id, label, other_extension, direction=direction)

    sip_to_ai: "queue.Queue" = queue.Queue()
    ai_to_sip: "queue.Queue" = queue.Queue()

    bridge = RealtimeBridge(
        api_key=openai_key,
        model=openai_model,
        system_prompt=prompt,
        voice=voice,
        sip_to_ai=sip_to_ai,
        ai_to_sip=ai_to_sip,
        on_event=transcript.handle_realtime_event,
    )

    logger.info("Call live -- %s", label)
    try:
        bridge.start()
        run_audio_loop(phone, bridge, sip_to_ai, ai_to_sip)
    finally:
        bridge.stop()
        if bridge.crashed is not None:
            reason = describe_bridge_crash(bridge.crashed)
            logger.error("Realtime bridge failed -- ending call (%s)", reason)
            transcript.log_error(reason)
            if phone.state == CallState.ANSWERED:
                try:
                    phone.call.hangup()
                except Exception:
                    logger.exception("Failed to hang up after bridge crash")
        transcript.finalize()
        logger.info("Call ended. Transcript: logs/%s.txt", call_id)


def new_call_id() -> str:
    return time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]


def run_listen_mode(
    pbx_host: str,
    sip_port: int,
    local_sip_port: int,
    ext_number: str,
    ext_secret: str,
    my_ip: str,
    rtp_low: int,
    rtp_high: int,
    persona_slug: str,
    openai_key: str,
    openai_model: str,
) -> None:
    """Registers and answers inbound calls one at a time until Ctrl+C."""
    persona = get_persona(persona_slug)
    busy_lock = threading.Lock()
    phone: Optional[SipPhone] = None  # assigned below; read by on_incoming_call at call time

    def on_incoming_call(call: VoIPCall) -> None:
        if not busy_lock.acquire(blocking=False):
            logger.warning("Inbound call arrived while already on a call -- rejecting")
            try:
                call.deny()
            except Exception:
                logger.exception("Failed to reject busy inbound call")
            return
        try:
            try:
                caller = call.request.headers["From"]["number"]
            except Exception:
                caller = "unknown"
            logger.info("Incoming call from extension %s -- answering as '%s'", caller, persona.label)
            call.answer()
            phone.call = call
            run_call(phone, persona_slug, new_call_id(), caller, "inbound", openai_key, openai_model)
        except Exception:
            logger.exception("Inbound call handling failed")
            try:
                call.hangup()
            except Exception:
                pass
        finally:
            busy_lock.release()

    phone = SipPhone(
        pbx_host, sip_port, ext_number, ext_secret,
        my_ip=my_ip, local_sip_port=local_sip_port,
        rtp_port_low=rtp_low, rtp_port_high=rtp_high,
        call_callback=on_incoming_call,
    )

    try:
        phone.start()
        time.sleep(1)  # give registration a moment to complete
        logger.info(
            "Registered as extension %s -- waiting for inbound calls as persona '%s' (%s at %s). Press Ctrl+C to stop.",
            ext_number, persona.label, persona.character_name, persona.company,
        )
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down...")
    finally:
        phone.stop()


def main() -> None:
    args = parse_args()

    if args.list_personas:
        for slug, p in PERSONAS.items():
            print(f"{slug:20s} {p.label} ({p.character_name}, {p.company})")
        return

    prompt_override = ""
    if args.prompt_file:
        prompt_override = open(args.prompt_file, encoding="utf-8").read()

    if not args.listen and not args.persona and not prompt_override:
        print("Error: --persona or --prompt-file is required (see --list-personas)", file=sys.stderr)
        sys.exit(1)

    load_dotenv()
    check_env()

    pbx_host = os.environ["PBX_HOST"]
    sip_port = int(os.environ.get("PBX_SIP_PORT", "5060"))
    local_sip_port = int(os.environ.get("LOCAL_SIP_PORT", str(sip_port)))
    rtp_low = int(os.environ.get("PBX_RTP_PORT_LOW", "10000"))
    rtp_high = int(os.environ.get("PBX_RTP_PORT_HIGH", "20000"))
    local_rtp_low = int(os.environ.get("LOCAL_RTP_PORT_LOW", str(rtp_low)))
    local_rtp_high = int(os.environ.get("LOCAL_RTP_PORT_HIGH", str(rtp_high)))
    my_ip = os.environ.get("MY_IP", "0.0.0.0")
    ext_number = os.environ["EXTENSION_101_NUMBER"]
    ext_secret = os.environ["EXTENSION_101_SECRET"]
    openai_key = os.environ["OPENAI_API_KEY"]
    openai_model = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime")

    if args.listen:
        persona_slug = args.persona or prompt_persona_choice()
        run_listen_mode(
            pbx_host, sip_port, local_sip_port, ext_number, ext_secret, my_ip,
            local_rtp_low, local_rtp_high,
            persona_slug, openai_key, openai_model,
        )
        return

    target_extension = args.target or os.environ.get("TARGET_EXTENSION", "100")
    phone = SipPhone(
        pbx_host, sip_port, ext_number, ext_secret,
        my_ip=my_ip, local_sip_port=local_sip_port,
        rtp_port_low=local_rtp_low, rtp_port_high=local_rtp_high,
    )

    try:
        phone.start()
        time.sleep(1)  # give registration a moment to complete

        answered = phone.dial(target_extension)
        if not answered:
            logger.error("Call to extension %s was not answered (busy, rejected, or timed out)", target_extension)
            return

        if args.max_seconds:
            def _autohang():
                time.sleep(args.max_seconds)
                logger.info("--max-seconds reached; hanging up")
                try:
                    phone.call.hangup()
                except Exception:
                    pass
            threading.Thread(target=_autohang, name="autohang", daemon=True).start()

        if args.dtmf:
            logger.warning("--dtmf ignored: pyVoIP has no DTMF sender; dial extension 8009 "
                           "to reach the receptionist decline path instead")

        run_call(phone, args.persona, new_call_id(), target_extension, "outbound",
                 openai_key, openai_model, prompt_override=prompt_override)

    except KeyboardInterrupt:
        logger.info("Interrupted, hanging up...")
    finally:
        phone.stop()


if __name__ == "__main__":
    main()
