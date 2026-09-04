# Audio and media paths

Voice systems are easier to reason about when signaling, media, and AI-session
boundaries are named separately.

| System | Signaling / call control | Media path | AI boundary |
| --- | --- | --- | --- |
| AI receptionist | Asterisk/FreePBX dialplan and ARI | PBX RTP via external media | Realtime voice session |
| Call-leg transcription | Asterisk ARI Snoop plus external media | One RTP stream per labeled call leg | Independent transcription session per leg |
| SIP Realtime lab | SIP registration and INVITE handling | PBX RTP / G.711 mu-law | Realtime speech-to-speech session |
| Earlier Twilio prototype | Twilio call control and media stream | Twilio WebSocket audio | Realtime voice session |

## Signaling is not audio

SIP or PBX control logic decides where a call rings, answers, transfers, or
hangs up. RTP carries the call audio. ARI provides application control over
Asterisk resources, while an external-media channel makes a selected media path
available to an application.

Keeping those boundaries explicit prevents a common failure mode in voice work:
assuming that a call-control event also proves that the expected audio is
flowing.

## Codec approach

The PBX-oriented projects use G.711 mu-law where supported because it aligns
with ordinary telephony media. Avoiding needless conversion reduces moving
parts and preserves a straightforward debugging story. Conversion is still
performed deliberately when an API requires a different representation, such
as 24 kHz PCM input for a transcription session.

## Attribution boundary

For transcription, speaker attribution is established before transcription by
the separate PBX media path. A transcript provider may improve text quality,
but it is not asked to decide which call leg produced the audio.

Related architecture documents:

- [AI receptionist](../architecture/ai-receptionist.md)
- [Attributed transcription](../architecture/attributed-transcription.md)
- [SIP Realtime lab](../architecture/sip-realtime-lab.md)
