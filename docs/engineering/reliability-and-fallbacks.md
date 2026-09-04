# Reliability and fallback behavior

In a phone interaction, a graceful fallback is part of the product. The
systems represented here favor a clearly resolved outcome over an opaque
failure.

| Condition | Intended behavior |
| --- | --- |
| Human does not answer | Continue to the disclosed AI-receptionist path. |
| Caller declines AI path | Send the caller to voicemail without AI processing. |
| Realtime provider unavailable | Send the caller to voicemail rather than start an unusable session. |
| Caller is silent after an intake close | A transport-owned timer concludes the call cleanly. |
| Second call reaches a single-call lab simulator | Reject or signal busy instead of mixing sessions. |
| Outbound lab call is not answered | End the attempt after a defined answer timeout. |
| One transcript leg ends | Finalize the labeled leg without relabeling another stream. |

## Design principles

- Prefer a human, voicemail, or clean conclusion over silence or a half-started
  AI interaction.
- Treat provider availability and media lifecycle as first-class states.
- Separate deterministic call-state rules from model interpretation where the
  failure behavior must be predictable.
- Make the fallback path observable in tests and operational logs.

The table describes intended behavior, not a general availability guarantee.
Production behavior must be verified in the actual PBX, carrier, and provider
environment where it is deployed.
