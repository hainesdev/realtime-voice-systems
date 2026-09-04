"""Thin wrapper around pyVoIP's VoIPPhone/VoIPCall.

pyVoIP registers as a SIP extension and speaks G.711 (PCMU) RTP directly, but
its public read_audio()/write_audio() API works in an 8-bit "biased linear"
PCM representation, not raw u-law -- see pyVoIP.RTP.RTPClient.parse_pcmu /
encode_pcmu:

    receive: audioop.ulaw2lin(payload, 1) -> audioop.bias(data, 1, 128)
    send:    audioop.bias(data, 1, -128) -> audioop.lin2ulaw(data, 1)

This wrapper undoes/redoes that same transform so the rest of this project
only ever deals in real G.711 u-law bytes -- the format both Asterisk and
OpenAI's Realtime API speak natively, avoiding any extra resampling.
"""

import audioop
import logging
import time
import uuid
from typing import Callable, Optional

import pyVoIP
from pyVoIP.VoIP.VoIP import CallState, VoIPCall, VoIPPhone  # noqa: F401 (import order matters: this loads pyVoIP.SIP safely before we touch it below -- see gen_ack patch)
import pyVoIP.SIP

logger = logging.getLogger("sip_phone")

# pyVoIP 1.6.8 only knows how to parse INVITE/ACK/BYE/CANCEL
# (pyVoIP.SIPCompatibleMethods). Asterisk sends periodic OPTIONS keepalive
# ("qualify") pings to every registered extension, independent of whatever
# else is happening on the connection. SIPClient.invite()'s blocking read
# has no guard for an unrecognized method arriving mid-transaction (unlike
# the background recv loop, which silently swallows the same parse error),
# so an OPTIONS ping landing during call setup crashes the whole call with
# SIPParseError -- confirmed live: this is exactly what happened on the
# first real test call. Registering OPTIONS as a known method routes it
# through the generic message parser instead, which handles it fine (no
# body, ordinary headers) -- the client still doesn't reply to it, but that
# only risks Asterisk transiently marking the AOR "unreachable" between
# qualify probes, which doesn't affect this bot's registration (kept alive
# by REGISTER, not by answering OPTIONS) or a call already in progress.
if "OPTIONS" not in pyVoIP.SIPCompatibleMethods:
    pyVoIP.SIPCompatibleMethods.append("OPTIONS")


def _fixed_gen_ack(self, request: "pyVoIP.SIP.SIPMessage") -> str:
    """Correct version of pyVoIP.SIP.SIPClient.gen_ack.

    Confirmed live via a real answered call + PBX-side SIP trace: pyVoIP's
    stock gen_ack() fabricates a brand-new random tag for the ACK's To
    header (`self.gen_tag()`) instead of echoing the tag Asterisk actually
    assigned in its 200 OK. Per RFC 3261 the ACK to a 2xx response MUST
    reuse that exact tag so the far end can match it to the dialog it
    created -- with a mismatched tag, Asterisk never recognizes the ACK as
    satisfying the transaction and keeps retransmitting the 200 OK (Timer G)
    until it gives up around Timer H and tears the whole call down. That
    retransmit-then-hangup sequence is exactly what showed up in
    /var/log/asterisk/full for the call that rang, was answered, and then
    played hold music instead of connecting. Every other generator in this
    file that echoes To/From tags (e.g. gen_bye) does this correctly
    already; gen_ack was just missed.
    """
    to_tag = request.headers["To"]["tag"]
    if not to_tag:
        to_tag = self.gen_tag()

    ack_message = f"ACK {request.headers['To']['raw'].strip('<').strip('>')} SIP/2.0\r\n"
    ack_message += self._gen_response_via_header(request)
    ack_message += "Max-Forwards: 70\r\n"
    ack_message += f"To: {request.headers['To']['raw']};tag={to_tag}\r\n"
    ack_message += (
        f"From: {request.headers['From']['raw']};tag="
        f"{self.tagLibrary[request.headers['Call-ID']]}\r\n"
    )
    ack_message += f"Call-ID: {request.headers['Call-ID']}\r\n"
    ack_message += f"CSeq: {request.headers['CSeq']['check']} ACK\r\n"
    ack_message += f"User-Agent: pyVoIP {pyVoIP.__version__}\r\n"
    ack_message += "Content-Length: 0\r\n\r\n"
    return ack_message


pyVoIP.SIP.SIPClient.gen_ack = _fixed_gen_ack


def _fixed_gen_call_id(self) -> str:
    """Correct version of pyVoIP.SIP.SIPClient.gen_call_id.

    Stock pyVoIP derives the Call-ID from SHA256 of an in-process counter
    (self.callID.next()), which starts back at the same value every time a
    fresh process registers -- so every run of this short-lived,
    one-call-per-process bot generated the *identical* Call-ID as previous
    runs. Confirmed live via the PBX trace: a later run's INVITE reused a
    Call-ID Asterisk still had a stale dialog cached under from an earlier
    attempt, and got treated as a malformed retransmission (400 Bad
    Request: "Retransmission with different CSeq"), then a confused retry
    landed on the extension looking busy (486 Busy Here) instead of ever
    ringing. A UUID4 is unique regardless of process restarts, which a
    counter that resets every run can never guarantee.
    """
    return f"{uuid.uuid4().hex}@{self.myIP}:{self.myPort}"


pyVoIP.SIP.SIPClient.gen_call_id = _fixed_gen_call_id


def _fixed_callback(self, request: "pyVoIP.SIP.SIPMessage") -> None:
    """Handle SIP OPTIONS so Asterisk keepalives do not mark the extension dead."""
    if request.type == pyVoIP.SIP.SIPMessageType.MESSAGE:
        if request.method == "INVITE":
            self._callback_MSG_Invite(request)
        elif request.method == "BYE":
            self._callback_MSG_Bye(request)
        elif request.method == "OPTIONS":
            response = self.sip.gen_ok(request)
            self.sip.out.sendto(response.encode("utf8"), (self.server, self.port))
    else:
        if request.status == pyVoIP.SIP.SIPStatus.OK:
            self._callback_RESP_OK(request)
        elif request.status == pyVoIP.SIP.SIPStatus.NOT_FOUND:
            self._callback_RESP_NotFound(request)
        elif request.status == pyVoIP.SIP.SIPStatus.SERVICE_UNAVAILABLE:
            self._callback_RESP_Unavailable(request)


VoIPPhone.callback = _fixed_callback


def _fixed_callback_RESP_NotFound(self, request) -> None:
    """Correct version of pyVoIP.VoIP.VoIP.VoIPPhone._callback_RESP_NotFound.

    Confirmed live: this (and _callback_RESP_Unavailable below) check
    `if call_id not in self.calls` and log a debug message, but forget to
    return afterward -- so they fall through to `self.calls[call_id]...`
    and crash with a bare KeyError anyway. This is reachable in normal
    operation: invite()'s own blocking response loop calls this directly
    for any early response (e.g. a 503 on the first, pre-auth probe
    INVITE) that arrives *before* VoIPPhone.call() has gotten around to
    registering the call in self.calls, which only happens after
    self.sip.invite(...) returns. _callback_RESP_OK already has the
    correct `return`; these two just never got it.
    """
    from pyVoIP import debug as _debug

    _debug("Not Found recieved, invalid number called?")
    call_id = request.headers["Call-ID"]
    if call_id not in self.calls:
        _debug("Unknown/No call")
        return
    self.calls[call_id].not_found(request)
    ack = self.sip.gen_ack(request)
    self.sip.out.sendto(ack.encode("utf8"), (self.server, self.port))


def _fixed_callback_RESP_Unavailable(self, request) -> None:
    """Correct version of pyVoIP.VoIP.VoIP.VoIPPhone._callback_RESP_Unavailable.

    See _fixed_callback_RESP_NotFound above -- same missing-return bug.
    """
    from pyVoIP import debug as _debug

    _debug("Service Unavailable recieved")
    call_id = request.headers["Call-ID"]
    if call_id not in self.calls:
        _debug("Unknown/No call")
        return
    self.calls[call_id].unavailable(request)
    ack = self.sip.gen_ack(request)
    self.sip.out.sendto(ack.encode("utf8"), (self.server, self.port))


VoIPPhone._callback_RESP_NotFound = _fixed_callback_RESP_NotFound
VoIPPhone._callback_RESP_Unavailable = _fixed_callback_RESP_Unavailable

FRAME_BYTES = 160  # 20ms @ 8kHz, 1 byte/sample in pyVoIP's linear format


def _detect_local_ip(target_host: str) -> str:
    """Finds this machine's outbound-facing IP without any external service.

    Standard no-external-dependency trick: connecting a UDP socket doesn't
    actually send packets, but the OS still picks a real local source
    address for the route, which getsockname() then reveals.
    """
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_host, 80))
        return s.getsockname()[0]
    finally:
        s.close()


class SipPhone:
    def __init__(
        self,
        server: str,
        sip_port: int,
        username: str,
        password: str,
        my_ip: str = "0.0.0.0",
        local_sip_port: Optional[int] = None,
        rtp_port_low: int = 10000,
        rtp_port_high: int = 20000,
        call_callback: Optional[Callable[[VoIPCall], None]] = None,
    ):
        if my_ip == "0.0.0.0":
            # pyVoIP puts my_ip verbatim into the SDP connection line
            # (c=IN IP4 ...). Literal 0.0.0.0 there isn't "auto" to pyVoIP
            # or Asterisk -- it's the RFC-conventional signal for "this
            # media is on hold". Confirmed live: Asterisk was starting
            # Music-on-Hold on the answering party immediately on bridge
            # join because our SDP said c=IN IP4 0.0.0.0, which is exactly
            # what produced the "rang, answered, got hold music" symptom --
            # nothing to do with call setup, which was already working.
            my_ip = _detect_local_ip(server)
            logger.info("MY_IP was 0.0.0.0 (hold sentinel) -- auto-detected %s instead", my_ip)

        self.phone = VoIPPhone(
            server,
            sip_port,
            username,
            password,
            myIP=my_ip,
            sipPort=local_sip_port or sip_port,
            rtpPortLow=rtp_port_low,
            rtpPortHigh=rtp_port_high,
            # pyVoIP auto-rejects (busy) any inbound INVITE when this is None.
            # When set, pyVoIP calls it with a VoIPCall in CallState.RINGING
            # on its own per-call thread (spawned from the SIP recv thread via
            # a Timer, not the recv thread itself), so it's safe for the
            # callback to block for the whole call duration.
            callCallback=call_callback,
        )
        self.call: Optional[VoIPCall] = None

    def start(self) -> None:
        logger.info("Registering with PBX...")
        self.phone.start()

    def stop(self) -> None:
        if self.call is not None:
            try:
                self.call.hangup()
            except Exception:
                pass
        self.phone.stop()

    def dial(self, extension: str, answer_timeout: float = 30.0) -> bool:
        """Places a call and blocks until it's answered, rejected, or times out."""
        logger.info("Dialing extension %s...", extension)
        self.call = self.phone.call(extension)
        deadline = time.monotonic() + answer_timeout
        last_state = None
        while time.monotonic() < deadline:
            state = self.call.state
            if state != last_state:
                logger.info("Call state: %s", state)
                last_state = state
            if state == CallState.ANSWERED:
                return True
            if state == CallState.ENDED:
                return False
            time.sleep(0.1)
        logger.warning("Timed out waiting for answer, hanging up")
        try:
            self.call.hangup()
        except Exception:
            pass
        return False

    @property
    def state(self) -> Optional[CallState]:
        return self.call.state if self.call else None

    def read_ulaw(self, length: int = FRAME_BYTES, blocking: bool = True) -> bytes:
        """Reads one frame of raw G.711 u-law audio from the call."""
        linear = self.call.read_audio(length=length, blocking=blocking)
        unbiased = audioop.bias(linear, 1, -128)
        return audioop.lin2ulaw(unbiased, 1)

    def write_ulaw(self, ulaw_bytes: bytes) -> None:
        """Writes raw G.711 u-law audio to the call."""
        linear = audioop.ulaw2lin(ulaw_bytes, 1)
        biased = audioop.bias(linear, 1, 128)
        self.call.write_audio(biased)

    def send_dtmf(self, digits: str) -> None:
        """Transmit RFC 2833 DTMF on the active call."""
        if self.call:
            self.call.send_dtmf(digits)
