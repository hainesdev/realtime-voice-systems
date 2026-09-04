# Interview-practice simulator

A controlled SIP/RTP practice lab that connects a private test extension to an
OpenAI Realtime interviewer. It demonstrates the same media bridge as the
buyer-persona simulator, with a generic operations-lead interview scenario.

## Safety boundary

Use only a PBX and extensions you control or are explicitly authorized to use.
The included scenario is fictional and generic. Do not model a real person,
employer, or non-public interview process without permission.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env
```

Configure a private PBX test extension, an authorized target extension, and an
OpenAI API key in `.env`.

## Run

```bash
python main.py --list-interviews
python main.py --mode interview --interview operations_leader
python main.py --listen --mode interview --interview operations_leader --difficulty executive
```

Local transcript logs are written to `logs/` and are ignored by the parent
repository. This is a controlled prototype, not a production interviewing
service.
