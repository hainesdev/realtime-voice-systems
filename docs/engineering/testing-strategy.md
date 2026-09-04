# Testing strategy

Voice systems need evidence at multiple boundaries. A unit test alone cannot
prove that PBX media reaches an application, and a successful manual call does
not prove that every fallback path behaves correctly.

## Test layers

| Layer | Examples | Purpose |
| --- | --- | --- |
| Unit | audio transforms, RTP parsing, state decisions, transcript formatting | Verify small deterministic behavior quickly. |
| Property / boundary | conversation-state caps, required-field order, fallback decisions | Find edge cases in deterministic rules. |
| Replay regression | sanitized event histories from prior controlled calls | Prevent recurring conversation-flow defects. |
| Integration | ARI lifecycle, provider adapter behavior, CLI output | Verify component boundaries. |
| Controlled E2E | SIP call, PBX routing, RTP media, labeled transcript output | Verify the full media path in an isolated environment. |
| Live controlled call | operator review of notice, audio, fallback, and cleanup | Confirm user-facing behavior before a release. |

## What is public

The public transcription reference implementation contains its own runnable
test suite and controlled E2E documentation. This showcase contains only
synthetic data and architecture-level evidence.

## What remains private

Production PBX tests, dialplan-specific configuration, recordings, and real
call artifacts remain private because publishing them would expose sensitive
operational or personal information.

## Release discipline

Before a voice-flow release, verify both expected behavior and failure paths:
notice timing, opt-out routing, provider unavailability, audio in both
directions, timeout behavior, transcript finalization, and resource cleanup.
