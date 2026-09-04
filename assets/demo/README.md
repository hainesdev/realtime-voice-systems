# Demonstration brief

## Proposed video

**Title:** Speaker-attributed call transcription with Asterisk media topology

**Target length:** 60–90 seconds

**Audience:** technical hiring managers, engineering peers, and prospective
clients evaluating voice-system capability.

## Storyboard

1. State the problem: a mixed call recording cannot guarantee who said each
   word.
2. Show the two-leg topology: caller and agent each receive an independent
   media/transcription path.
3. Show a controlled SIP call starting in the E2E environment.
4. Show labeled transcript events arriving for each leg.
5. Show the final attributed output and the post-call stereo packaging option.
6. Close with the public implementation link and a concise principle:
   attribution comes from topology, not a model guess.

## Publication requirements

- Use generated or fully synthetic spoken content.
- Remove terminal user names, absolute paths, host details, browser sessions,
  API output, and environment variables.
- Add captions and publish a matching text transcript.
- Keep raw capture files outside Git; host the final reviewed video externally.
