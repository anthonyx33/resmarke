# 4D-AR1 Amendment 1 — Privacy-Redaction Integrity Check (frozen)

Author: master engineer (D). Date: 2026-08-29.
Applies to `C8_MASTER_PROMPT_4D_AR1_MASTER_FREEZE.md` §7.1 ("Integrity"),
whose privacy-redaction clause was underspecified. The freeze document itself
is not modified; its byte pin remains valid. This amendment is binding on M2
metric computation and on the panel protocol.

## 1. Builder flag acknowledged

The builder correctly reported that the pinned ROI manifest
(`round-4d-cam-1/roi-manifest.json`) defines `protected`, `smooth`, and
`texture` boxes only — there is no privacy-redaction ROI field. The builder was
right not to invent one. No defect is attributed to the build.

## 2. Frozen resolution

The generative wash performs the privacy redaction upstream, before any
factorial factor. Every arm consumes the exact same pinned O0/O1/OR/O2 bytes,
so redaction cannot differ between arms at the input boundary. Downstream
factors (tone-lock, one JPEG encode, QF) are tone/filter operations that
cannot resurrect removed content. The §7.1 integrity requirement is therefore
implemented, without new ROI fields and without harness code changes, as:

1. **Upstream identity** — the existing 291 input checks already pin every
   consumed upstream byte. Any arm that does not consume the exact pinned
   bytes hard-stops. (Passes by construction; recorded per arm in M2.)
2. **Protected-ROI envelope** — per cell: protected EATR ≥ 0.98 × A0, and
   zero candidate-created second peaks in protected ROIs (frozen §7.2 checks,
   computed by the master engineer in M2).
3. **Panel integrity item I1 (mandatory, binding on the panel protocol)** —
   "No visible re-appearance of redacted or identity detail relative to the
   shared upstream reference." The panel protocol must display the O0 source
   as the reference image for integrity items. Any arm receiving a
   yes-answer on any image is terminated from the funnel, regardless of all
   other scores.

## 3. Scope

No harness or test changes. The amendment is added to the artifact record
(its SHA-256 is recorded in the M2 results document) and is treated as part
of the frozen commission for all subsequent decisions.
