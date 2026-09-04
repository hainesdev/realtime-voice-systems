"""E2E listener: registers as an extension and auto-answers inbound calls,
bridging them to a (silent) OpenAI-Realtime voice. It supports controlled
extension-to-extension media-path tests.

    python listener.py
    python listener.py --ext 100 --prompt-file p.txt

Env (.env, same as main.py, plus):
    LISTEN_EXT_NUMBER / LISTEN_EXT_SECRET  (use a dedicated test extension)
"""

import argparse
import logging
import os
import queue
import threading
import time

from dotenv import load_dotenv
from pyVoIP.VoIP.VoIP import CallState, VoIPCall

from main import run_audio_loop
from realtime_bridge import RealtimeBridge
from sip_phone import SipPhone
from transcript_logger import CallTranscriptLogger

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("listener")

QUIET_PROMPT = "You are on a phone call. Stay mostly silent. If addressed, answer very briefly."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext", default=os.environ.get("LISTEN_EXT_NUMBER", "100"))
    ap.add_argument("--prompt-file")
    ap.add_argument("--max-seconds", type=int, default=180)
    ap.add_argument("--dtmf-after", type=int, default=0,
                    help="send --dtmf this many seconds after answering (founder takeover)")
    ap.add_argument("--dtmf", default="1")
    args = ap.parse_args()
    load_dotenv()

    prompt = open(args.prompt_file, encoding="utf-8").read() if args.prompt_file else QUIET_PROMPT

    secret = os.environ.get("LISTEN_EXT_SECRET") or os.environ.get("EXTENSION_100_SECRET")
    if not secret:
        raise SystemExit("set LISTEN_EXT_SECRET (or EXTENSION_100_SECRET) in .env")
    key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime")
    host = os.environ["PBX_HOST"]
    lock = threading.Lock()
    phone: SipPhone | None = None

    def on_call(call: VoIPCall) -> None:
        if not lock.acquire(blocking=False):
            call.deny()
            return
        try:
            log.info("inbound call -- answering as ext %s", args.ext)
            call.answer()
            phone.call = call
            cid = time.strftime("%Y%m%dT%H%M%S") + "-listener"
            t = CallTranscriptLogger(cid, "listener", "inbound", direction="inbound")
            s2a, a2s = queue.Queue(), queue.Queue()
            br = RealtimeBridge(api_key=key, model=model, system_prompt=prompt, voice="ash",
                                sip_to_ai=s2a, ai_to_sip=a2s, on_event=t.handle_realtime_event)
            if args.max_seconds:
                threading.Thread(target=lambda: (time.sleep(args.max_seconds),
                                 call.hangup() if call.state == CallState.ANSWERED else None),
                                 daemon=True).start()
            if args.dtmf_after:
                def _press():
                    time.sleep(args.dtmf_after)
                    if call.state == CallState.ANSWERED:
                        log.info("sending DTMF %r", args.dtmf)
                        call.send_dtmf(args.dtmf)
                threading.Thread(target=_press, daemon=True).start()
            br.start()
            run_audio_loop(phone, br, s2a, a2s)
            br.stop()
            t.finalize()
            log.info("call ended -- transcript logs/%s.txt", cid)
        except Exception:
            log.exception("call handling failed")
            try:
                call.hangup()
            except Exception:
                pass
        finally:
            lock.release()

    # distinct local bind range from main.py so the caller and listener can run together
    phone = SipPhone(host, int(os.environ.get("PBX_SIP_PORT", "5060")), args.ext, secret,
                     my_ip=os.environ.get("MY_IP", "0.0.0.0"),
                     local_sip_port=int(os.environ.get("LISTEN_SIP_PORT", "5064")),
                     rtp_port_low=int(os.environ.get("LISTEN_RTP_PORT_LOW", "22000")),
                     rtp_port_high=int(os.environ.get("LISTEN_RTP_PORT_HIGH", "23000")),
                     call_callback=on_call)
    try:
        phone.start()
        time.sleep(1)
        log.info("registered as ext %s -- waiting for inbound calls (Ctrl+C to stop)", args.ext)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        phone.stop()


if __name__ == "__main__":
    main()
