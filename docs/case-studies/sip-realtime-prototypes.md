# Case study: controlled SIP Realtime prototypes

## Problem

Voice-agent ideas are easier to evaluate when they can participate in an
actual SIP call, not merely a browser microphone demo. The test environment
also needs to remain bounded: no public dialer, no customer calls, and a clear
record of what happened during each practice session.

## Approach

Daniel Haines built two scenario variants on one controlled PBX/SIP pattern:

- A buyer-persona simulator for discovery-call practice.
- An interview simulator for phone-based mock interviews.

Each variant registers as a PBX extension, either calls a designated internal
extension or waits for an inbound extension-to-extension call, bridges audio
to an OpenAI Realtime session, and writes structured and human-readable call
transcripts.

## Engineering choices

- SIP registration and call media handled through `pyVoIP`.
- G.711 mu-law retained across PBX and realtime boundaries where practical.
- Server-side voice activity detection for turn handling.
- Explicit single-call concurrency and answer-timeout behavior.
- Persona/scenario prompts separated from the SIP/media implementation.

## Honest limits

The projects are controlled lab tools. An extension can have only one active
registration, concurrent calls are not supported, and the inbound path needs
the same ongoing PBX-side trace/testing discipline as any new SIP answer flow.

## What this demonstrates

Hands-on SIP signaling, RTP/audio handling, codec-boundary reasoning, Realtime
voice integration, and reproducible conversational practice environments.
