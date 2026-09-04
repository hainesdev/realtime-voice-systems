# Buyer-persona simulator

A controlled SIP/RTP practice lab that uses an OpenAI Realtime session to
role-play a buyer persona over a private PBX extension. It is a technical
example for native G.711 mu-law media, turn detection, call control, and
post-call logging—not a production dialer.

## Safety boundary

Run this only against a PBX and extensions you control or are explicitly
authorized to use. Configure a dedicated test extension, use fictional
personas, and keep generated call logs outside version control. This example
does not place PSTN calls by default.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env
```

Set the PBX host, a dedicated test extension's credentials, an authorized
target extension, and an OpenAI API key in `.env`.

## Run

```bash
python main.py --list-personas
python main.py --persona property_ops
python main.py --listen --persona facility_ops
```

The lab preserves G.711 mu-law end to end where practical. Transcript logs are
written locally to `logs/`, which is ignored by the parent repository.

## Limits

This is a controlled prototype: one call at a time, a private test PBX, and no
production reliability or compliance claim. Review the repository's
[privacy notes](../../../docs/engineering/privacy-and-call-recording.md) before
capturing any call content.
