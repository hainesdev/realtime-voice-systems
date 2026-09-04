"""CLI entry point for a dedicated test extension that either places an
outbound call or listens for inbound calls, bridging audio to an OpenAI
Realtime buyer persona or mock interviewer until hangup.

Usage:
    python main.py --list-personas
    python main.py --persona property_ops
    python main.py --listen [--persona property_ops]
    python main.py --mode interview --list-interviews
    python main.py --mode interview --interview operations_leader --difficulty executive
"""

import argparse
import logging
import os
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from interviews import DIFFICULTY_GUIDANCE, INTERVIEWS, get_interview, interview_prompt_for
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


@dataclass
class SimulationConfig:
    slug: str
    label: str
    character_name: str
    company: str
    voice: str
    system_prompt: str
    kind: str


def parse_args():
    parser = argparse.ArgumentParser(description="AI phone practice simulator")
    parser.add_argument(
        "--mode",
        choices=["persona", "interview"],
        default="persona",
        help="Practice mode: buyer persona or job interview",
    )
    parser.add_argument("--persona", choices=sorted(PERSONAS), help="Which persona to simulate")
    parser.add_argument("--list-personas", action="store_true", help="List available personas and exit")
    parser.add_argument("--interview", choices=sorted(INTERVIEWS), help="Which mock interview to simulate")
    parser.add_argument("--list-interviews", action="store_true", help="List available interview simulations and exit")
    parser.add_argument(
        "--difficulty",
        choices=sorted(DIFFICULTY_GUIDANCE),
        default="normal",
        help="Interview difficulty/style",
    )
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


def prompt_interview_choice() -> str:
    """Interactively asks which interview should handle inbound calls this run."""
    slugs = sorted(INTERVIEWS)
    print("No --interview given. Select an interview simulation for inbound calls:")
    for i, slug in enumerate(slugs, 1):
        s = INTERVIEWS[slug]
        print(f"  {i}. {slug:20s} {s.label} ({s.interviewer_name}, {s.company})")
    while True:
        choice = input("Interview [number or name]: ").strip()
        if choice in INTERVIEWS:
            return choice
        if choice.isdigit() and 1 <= int(choice) <= len(slugs):
            return slugs[int(choice) - 1]
        print(f"Invalid choice: {choice!r}")


def persona_simulation(persona_slug: str) -> SimulationConfig:
    persona = get_persona(persona_slug)
    return SimulationConfig(
        slug=persona.slug,
        label=persona.label,
        character_name=persona.character_name,
        company=persona.company,
        voice=persona.voice,
        system_prompt=system_prompt_for(persona_slug),
        kind="persona",
    )


def interview_simulation(interview_slug: str, difficulty: str) -> SimulationConfig:
    interview = get_interview(interview_slug)
    return SimulationConfig(
        slug=interview.slug,
        label=f"{interview.label} [{difficulty}]",
        character_name=interview.interviewer_name,
        company=interview.company,
        voice=interview.voice,
        system_prompt=interview_prompt_for(interview_slug, difficulty),
        kind="interview",
    )


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

    def writer():
        while not stop.is_set():
            try:
                chunk = ai_to_sip.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                phone.write_ulaw(chunk)
            except Exception:
                logger.exception("Failed writing audio to call")
                break

    writer_thread = threading.Thread(target=writer, name="ai-to-sip-writer", daemon=True)
    writer_thread.start()

    try:
        while phone.state == CallState.ANSWERED and bridge.crashed is None:
            chunk = phone.read_ulaw(blocking=True)
            sip_to_ai.put(chunk)
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
    simulation: SimulationConfig,
    call_id: str,
    other_extension: str,
    direction: str,
    openai_key: str,
    openai_model: str,
) -> None:
    """Bridges one already-answered call (phone.call set, state ANSWERED) to
    a practice conversation until hangup. Shared by the outbound and inbound
    (--listen) flows."""
    transcript = CallTranscriptLogger(call_id, simulation.label, other_extension, direction=direction)

    sip_to_ai: "queue.Queue" = queue.Queue()
    ai_to_sip: "queue.Queue" = queue.Queue()

    bridge = RealtimeBridge(
        api_key=openai_key,
        model=openai_model,
        system_prompt=simulation.system_prompt,
        voice=simulation.voice,
        sip_to_ai=sip_to_ai,
        ai_to_sip=ai_to_sip,
        on_event=transcript.handle_realtime_event,
    )

    logger.info(
        "Call live -- %s '%s' (%s at %s)",
        simulation.kind, simulation.label, simulation.character_name, simulation.company,
    )
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
    simulation: SimulationConfig,
    openai_key: str,
    openai_model: str,
) -> None:
    """Registers and answers inbound calls one at a time until Ctrl+C."""
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
            logger.info("Incoming call from extension %s -- answering as '%s'", caller, simulation.label)
            call.answer()
            phone.call = call
            run_call(phone, simulation, new_call_id(), caller, "inbound", openai_key, openai_model)
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
            "Registered as extension %s -- waiting for inbound calls as %s '%s' (%s at %s). Press Ctrl+C to stop.",
            ext_number, simulation.kind, simulation.label, simulation.character_name, simulation.company,
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

    if args.list_interviews:
        for slug, s in INTERVIEWS.items():
            print(f"{slug:20s} {s.label} ({s.interviewer_name}, {s.company})")
        return

    if args.mode == "persona" and args.interview:
        print("Error: --interview requires --mode interview", file=sys.stderr)
        sys.exit(1)
    if args.mode == "interview" and args.persona:
        print("Error: --persona cannot be used with --mode interview", file=sys.stderr)
        sys.exit(1)

    if args.mode == "interview":
        if not args.listen and not args.interview:
            print("Error: --interview is required in interview mode (see --list-interviews)", file=sys.stderr)
            sys.exit(1)
        interview_slug = args.interview or prompt_interview_choice()
        simulation = interview_simulation(interview_slug, args.difficulty)
    else:
        if not args.listen and not args.persona:
            print("Error: --persona is required in persona mode (see --list-personas)", file=sys.stderr)
            sys.exit(1)
        persona_slug = args.persona or prompt_persona_choice()
        simulation = persona_simulation(persona_slug)

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
        run_listen_mode(
            pbx_host, sip_port, local_sip_port, ext_number, ext_secret, my_ip,
            local_rtp_low, local_rtp_high,
            simulation, openai_key, openai_model,
        )
        return

    target_extension = os.environ.get("TARGET_EXTENSION", "100")
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

        run_call(phone, simulation, new_call_id(), target_extension, "outbound", openai_key, openai_model)

    except KeyboardInterrupt:
        logger.info("Interrupted, hanging up...")
    finally:
        phone.stop()


if __name__ == "__main__":
    main()
