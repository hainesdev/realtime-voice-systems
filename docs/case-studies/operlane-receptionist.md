# Case study: AI receptionist for a PBX environment

## Problem

A small business needs inbound coverage when a person cannot answer, without
turning an unanswered call into an opaque or frustrating automated experience.
The system must preserve a human-answer opportunity, make the automation path
clear to callers, and have a useful fallback when a real-time AI session is
not available.

## Design

Daniel Haines designed and implemented a receptionist architecture around an
existing Asterisk/FreePBX environment. The PBX first rings a human softphone.
If unanswered, it plays the AI/recording notice and provides an opt-out path.
Only then does the call move to the AI receptionist through ARI external media
and RTP.

The AI session captures a concise structured intake, while a read-only live
view exposes the current status, transcript, and collected intake fields to an
operator.

## Reliability choices

- Route to voicemail if the realtime AI service cannot be started.
- Provide a caller opt-out before AI processing.
- Keep conversation decisions separate from the telephony transport so they
  can be replayed and tested from event histories.
- Store sensitive validation artifacts outside the repository and avoid using
  them in public demonstrations.

## What this demonstrates

- PBX dialplan and application-level voice integration
- ARI, RTP, and Realtime voice-session orchestration
- Human fallback and failure-path design
- Conversation-state modeling and operational observability

## Public boundary

The deployed service, configuration, tenant data, call recordings, transcripts,
and infrastructure details remain private. The accompanying
[architecture note](../architecture/ai-receptionist.md) presents the technical
approach without exposing those assets.
