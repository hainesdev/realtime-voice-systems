# Privacy and call-recording considerations

This portfolio documents engineering considerations, not legal advice. Call
recording, AI processing, notice, consent, retention, and data-access duties
vary by jurisdiction, call path, and organization.

## Engineering practices represented here

- Make AI/recording notice part of the call flow before automated processing.
- Provide an opt-out route where the call design requires one.
- Keep sensitive recordings and validation artifacts outside source control.
- Store only the data needed for the intended operational purpose.
- Use sanitized fixtures and synthetic examples in public materials.
- Separate production configuration and credentials from application code and
  public documentation.

## Public repository policy

This repository must not contain:

- API keys, passwords, certificates, or `.env` files
- host addresses, PBX extension secrets, or production endpoints
- real phone numbers, customer names, or caller identifiers
- audio recordings, raw call transcripts, packet captures, or call logs
- screenshots or videos that expose any of the above

## Review rule

Every artifact is reviewed for visible and embedded sensitive information
before publication. When a useful artifact cannot be safely sanitized, the
repository describes the outcome and method without publishing the artifact.
