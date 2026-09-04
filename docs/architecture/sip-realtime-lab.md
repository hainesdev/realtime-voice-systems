# SIP Realtime lab architecture

## Purpose

The SIP Realtime lab is a controlled extension-to-extension environment for
testing AI buyer-persona and interview simulations over an existing PBX. It is
not a public calling service and does not use PSTN dialing in its intended lab
flow.

```text
Softphone / SIP extension
  <-> FreePBX / Asterisk
  <-> pyVoIP client registered as a lab extension
  <-> G.711 mu-law audio bridge
  <-> OpenAI Realtime session
  -> structured call transcript
```

## Modes

- **Outbound:** The simulator registers to the PBX and calls a selected lab
  extension.
- **Inbound:** The simulator registers and waits for another extension to call
  it.
- **Scenario selection:** The same media stack can load a buyer persona or a
  mock-interviewer scenario.

## Media handling

The PBX and Realtime service both support G.711 mu-law in the intended path,
so the lab avoids unnecessary resampling where possible. The SIP library has
an intermediate representation at one API boundary; the bridge explicitly
converts at that boundary and restores mu-law for the external media path.

## Constraints made explicit

The lab handles one call at a time. A shared extension registration cannot be
used simultaneously by a normal softphone and the simulator, and inbound
handling should be treated as a controlled-test capability until it has the
same operational evidence as the outbound path.
