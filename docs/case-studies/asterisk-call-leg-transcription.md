# Case study: speaker-attributed call transcription

## Problem

Call transcripts are much more useful when each line has a reliable speaker
label. Mixed call recordings make that difficult: diarization is an inference,
not a fact guaranteed by the recording.

## Approach

Daniel Haines created a reference implementation that assigns attribution from
the PBX's media topology. Each labeled Asterisk call leg gets its own ARI Snoop
and external-media/RTP path, feeding an independent transcription session. The
transcript label comes from the known PBX call leg rather than a model's guess
about a mixed stream.

The project also provides a post-call path: separate MixMonitor receive and
transmit tracks are packaged into a time-aligned labeled stereo WAV.

## Engineering evidence

- Unit coverage for audio conversion, RTP parsing, transcript assembly, and
  command-line behavior.
- A controlled Asterisk/FreePBX E2E harness that exercises real SIP media.
- A documented media topology that makes assumptions and limitations visible.
- A reusable provider boundary, separating PBX/RTP lifecycle from the chosen
  transcription service.

## Why it matters

The pattern is useful wherever speaker identity affects downstream review,
quality assurance, agent assistance, or a human handoff. It prioritizes a
verifiable media path over a convenient but uncertain mixed-audio shortcut.

## Public implementation

[View the Apache-2.0 reference implementation](https://github.com/Operlane-Systems/asterisk-call-leg-transcription).
