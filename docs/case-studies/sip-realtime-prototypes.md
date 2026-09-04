# Case study: controlled SIP Realtime prototypes

## Problem

Voice-agent ideas are easier to evaluate when they can participate in an
actual SIP call, not merely a browser microphone demo. The test environment
also needs to remain bounded: no public dialer, no customer calls, and a clear
record of what happened during each practice session.

## Approach

Daniel Haines built two public scenario variants on one controlled PBX/SIP
pattern:

- A buyer-persona simulator for discovery-call practice.
- An interview-practice simulator with a fictional operations-lead scenario.

Each variant registers as a PBX extension, either calls a designated internal
extension or waits for an inbound extension-to-extension call, bridges audio
to an OpenAI Realtime session, and writes structured and human-readable call
logs locally.

## Public source

The runnable examples are intentionally self-contained and use only fictional
personas and scenarios:

- [Buyer-persona simulator](../../examples/sip-realtime-lab/ai-customer-simulator/)
- [Interview-practice simulator](../../examples/sip-realtime-lab/ai-interview-simulator/)

Both require a private PBX test environment, dedicated test-extension
credentials, an authorized target extension, and an OpenAI API key. Local
`.env` files and call logs are ignored by Git and are not part of this public
portfolio.

## Engineering choices

- SIP registration and call media handled through `pyVoIP`.
- G.711 mu-law retained across PBX and realtime boundaries where practical.
- Server-side voice activity detection for turn handling.
- Explicit single-call concurrency and answer-timeout behavior.
- Persona/scenario prompts separated from the SIP/media implementation.
- Explicit configuration through `.env.example`; no endpoint or credential is
  embedded in the examples.

## Honest limits

The projects are controlled lab tools, not dialers or hosted services. Run them
only against a PBX and extensions you control or are authorized to use. An
extension can have only one active registration, concurrent calls are not
supported, and the inbound path needs the same ongoing PBX-side trace/testing
discipline as any new SIP answer flow.

## What this demonstrates

Hands-on SIP signaling, RTP/audio handling, codec-boundary reasoning, Realtime
voice integration, and reproducible conversational practice environments.
