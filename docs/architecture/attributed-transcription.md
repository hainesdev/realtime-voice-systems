# Speaker-attributed transcription architecture

## The attribution problem

A mixed call recording does not inherently identify who spoke each word.
Model-based diarization can be useful, but it is an inference and may become
unreliable around transfers, overlap, handoff, or changing acoustic conditions.

This design makes attribution a PBX media-routing property: each labeled call
leg receives its own capture and transcription pipeline.

```text
Caller call leg -> ARI Snoop -> external media -> RTP gateway -> transcript: caller
Agent call leg  -> ARI Snoop -> external media -> RTP gateway -> transcript: agent
```

## Real-time path

For each known call leg, the application creates a Snoop channel and an
external-media channel. The PBX sends one RTP stream per labeled leg to the
gateway. Each gateway session feeds an independent transcription session and
emits labeled partial and final transcript events.

The important boundary is one pipeline per leg—not a single mixed bridge
stream after a human joins the call.

## Post-call path

The complementary post-call option uses Asterisk MixMonitor receive and
transmit tracks. Once both tracks are complete, a utility packages them into a
time-aligned stereo WAV plus labels metadata:

- left channel: caller (or another declared leg)
- right channel: agent (or another declared leg)
- shorter channel: silence padded to retain alignment

## Evidence and implementation

The reference implementation is published separately:
[asterisk-call-leg-transcription](https://github.com/Operlane-Systems/asterisk-call-leg-transcription).
It includes a controlled E2E harness, RTP/audio tests, transcript tests, and a
FreePBX-safe custom-context example.

## Scope

This pattern improves technical speaker attribution. It does not independently
solve call-recording disclosure, consent, retention, or jurisdiction-specific
legal obligations.
