# SIP Realtime lab architecture

## Purpose

The SIP Realtime lab is a controlled extension-to-extension environment for
testing AI buyer-persona and interview simulations over an existing PBX. The
public examples use fictional scenarios, require a private test PBX, and are
not a public calling service or a PSTN dialer.

```text
Authorized SIP test extension
  <-> FreePBX / Asterisk
  <-> pyVoIP client registered as a dedicated lab extension
  <-> G.711 mu-law audio bridge
  <-> OpenAI Realtime session
  -> local structured call log
```

## Public examples

The code is organized as two independently runnable examples:

- [Buyer-persona simulator](../../examples/sip-realtime-lab/ai-customer-simulator/)
- [Interview-practice simulator](../../examples/sip-realtime-lab/ai-interview-simulator/)

Each provides a safe `.env.example`. Actual extension credentials, PBX hosts,
and call logs remain local and are excluded by the repository `.gitignore`.

## Modes

- **Outbound:** The simulator registers to the PBX and calls a selected lab
  extension.
- **Inbound:** The simulator registers and waits for another extension to call
  it.
- **Scenario selection:** The same media stack can load a fictional buyer
  persona or a fictional mock-interviewer scenario.

## Media handling

The PBX and Realtime service both support G.711 mu-law in the intended path,
so the lab avoids unnecessary resampling where possible. The SIP library has
an intermediate representation at one API boundary; the bridge explicitly
converts at that boundary and restores mu-law for the external media path.

## Constraints made explicit

The lab handles one call at a time. A dedicated test extension should not be
registered by another client at the same time, and inbound handling should be
treated as a controlled-test capability until it has the same operational
evidence as the outbound path.
