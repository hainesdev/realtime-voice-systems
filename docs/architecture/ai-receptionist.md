# AI receptionist architecture

## Goal

This design gives an inbound caller a clear path to a person, a disclosed AI
experience when automation is used, and a dependable fallback when it cannot
be used. It is documented here as a sanitized architecture, not as a public
production deployment guide.

## Call path

```text
Inbound call
  -> Asterisk / FreePBX routing
  -> ring human softphone for a defined window
  -> AI and recording notice, with opt-out route
  -> AI receptionist session OR voicemail fallback
  -> call summary / validation artifact / operational view
```

The initial human ring is important: the system assists coverage rather than
pretending to be the only available channel. If the human does not answer, the
PBX plays the notice before automated processing begins. A caller who chooses
the opt-out route is sent to voicemail without AI handling.

## Components

| Component | Responsibility |
| --- | --- |
| Asterisk/FreePBX | Inbound routing, extension ringing, dialplan controls, and voicemail fallback. |
| ARI external media | Connects the selected call to the application media path. |
| RTP bridge | Exchanges native telephony audio with the application. |
| Realtime voice session | Turn-taking, speech recognition, response generation, and voice output. |
| Conversation core | Maintains the structured intake state and determines the next safe action. |
| Live-call view | Provides read-only operational visibility into call state and sanitized transcript data. |

## Key design choices

- **Human first:** The automation path begins only after a defined human-answer
  opportunity.
- **Notice before automation:** The call flow places AI/recording disclosure
  before the session takes call audio.
- **Explicit failure behavior:** When the AI provider is unavailable, the
  caller reaches voicemail instead of an incomplete or silent session.
- **Separation of concerns:** Telephony/media transport and conversation
  decisions are separate, allowing the conversation core to be regression
  tested from event histories.

## Deliberately omitted

No production dialplan, host addresses, credentials, recording paths, tenant
content, phone numbers, or call artifacts are published here.
