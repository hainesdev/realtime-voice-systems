# Real-Time Voice Systems

Practical, trustworthy voice infrastructure by Daniel Haines: human-first
AI reception, speaker-attributed transcription, and controlled SIP/Realtime
systems.

This is a public engineering portfolio and technical reference—not a hosted
telephony product. It documents the decisions behind real systems while keeping
customer data, recordings, endpoints, and operational configuration private.

## Start here

- **Want to see how call attribution can be reliable?** Read the
  [speaker-attributed transcription case study](docs/case-studies/asterisk-call-leg-transcription.md)
  and its [reference implementation](https://github.com/Operlane-Systems/asterisk-call-leg-transcription).
- **Interested in responsible AI call handling?** Start with the
  [AI receptionist case study](docs/case-studies/operlane-receptionist.md).
- **Exploring SIP/RTP and low-latency AI?** See the
  [SIP Realtime lab](docs/case-studies/sip-realtime-prototypes.md) and its
  [public examples](examples/sip-realtime-lab/).
- **Interested in live speech translation under hostile acoustics?** See
  [ChurchBridge](https://github.com/hainesdev/churchbridge), a separate project
  covered below.

## What Daniel builds

- **AI reception systems** that preserve human-first call handling and provide
  explicit fallback paths.
- **Speaker-attributed transcription** built from PBX media topology rather
  than speaker-label guesses from a mixed recording.
- **SIP and Realtime prototypes** that exercise signaling, RTP media, G.711
  audio, turn detection, and operational logging end to end.
- **Live speech translation and captioning** for rooms where the audio is
  hostile and the speaker cannot be asked to change how they talk.

## Featured work

### AI receptionist for Asterisk/FreePBX

A production-oriented inbound-call design that rings a human first, presents
the AI/recording notice before automated processing, supports an opt-out route,
and sends callers to voicemail if the AI service is unavailable.

[Read the case study](docs/case-studies/operlane-receptionist.md) ·
[View the architecture](docs/architecture/ai-receptionist.md)

![AI receptionist call flow](assets/diagrams/ai-receptionist-flow.svg)

### Speaker-attributed call transcription

Real-time and post-call transcription patterns that preserve a separate media
path per call leg. The result is attributable by PBX topology, not inferred
from mixed audio.

[Read the case study](docs/case-studies/asterisk-call-leg-transcription.md) ·
[View the architecture](docs/architecture/attributed-transcription.md) ·
[Reference implementation](https://github.com/Operlane-Systems/asterisk-call-leg-transcription)

![Call-leg transcription topology](assets/diagrams/call-leg-transcription.svg)

### SIP Realtime lab

Controlled extension-to-extension simulators for buyer-persona and interview
practice. They connect SIP/RTP media to an OpenAI Realtime session while
retaining native G.711 mu-law where practical.

[Read the case study](docs/case-studies/sip-realtime-prototypes.md) ·
[View the architecture](docs/architecture/sip-realtime-lab.md) ·
[Browse the examples](examples/sip-realtime-lab/)

### ChurchBridge — live sermon translation

A separate project, and the largest of these: ChurchBridge captures live Spanish
preaching, treats it as *discourse* rather than a stream of sentences, and
delivers English captions to a sanctuary display and to phones in the pews.

The interesting engineering is downstream of recognition. A discourse-aware
buffer waits for a complete thought instead of a complete sentence. A fast
machine-translation path and a slower LLM path run at different speeds so
immediacy and quality stop competing. One deterministic gate decides what
reaches the screen. Head-anchored caption merges mean text never jumps position
when fragments are absorbed. And on the iPhone capture path, a streaming
DeepFilterNet3 implementation runs on device — with a mix chosen by listening
rather than by a metric, after full-strength suppression measured beautifully
and made the captions worse.

It carries its own license: source-available under PolyForm Noncommercial,
rather than the Apache-2.0 terms of this repository.

[Product overview and architecture](https://github.com/hainesdev/churchbridge) ·
[Platform](https://github.com/hainesdev/churchbridge-platform) ·
[iPhone app](https://github.com/hainesdev/churchbridge-ios) ·
[Benchmark harness](https://github.com/hainesdev/churchbridge-audio-bench)

## Engineering approach

Daniel designs voice systems around observable media paths, explicit failure
behavior, testable conversation state, and careful handling of sensitive call
data. The supporting notes describe the approach:

- [Audio and media paths](docs/engineering/audio-and-media-paths.md)
- [Reliability and fallback behavior](docs/engineering/reliability-and-fallbacks.md)
- [Privacy and recording considerations](docs/engineering/privacy-and-call-recording.md)
- [Testing strategy](docs/engineering/testing-strategy.md)

## Demonstration

A synthetic call-leg-transcription demonstration is in production. It will show
separate caller and agent streams, labeled transcript events, and the resulting
attributed output—without using a real call recording. See
[the demo brief](assets/demo/README.md).

## Public-scope note

This repository intentionally contains no credentials, production endpoints,
phone numbers, recordings, raw call transcripts, customer data, or PBX
configuration. Private systems are represented through sanitized technical
case studies and architecture material only.

## Contact

Daniel Haines · [GitHub](https://github.com/hainesdev) ·
[Portfolio](https://dhaines.dev)

I welcome conversations about real-time audio, speech systems, mobile audio,
telephony infrastructure, and applied AI engineering.
