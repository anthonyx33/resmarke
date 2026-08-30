# MASTER ENGINEER REVIEW — C8_4D_1B_CONSULTATION_RESPONSE.md

Date: 2026-08-27 · Reviewer: master engineer · Status: **ACCEPTED IN FULL — with one measured addition**

C88's response is the strongest deliverable in the program so far. Every
MEASURED claim it cites reproduces against my own records (band-energy map,
denominators 0.098217/0.106025, 4D-CAM-1 numbers). Disposition:

## Accepted recommendations

1. **Candidate narrowed to OR→O2, H1-only, loss-constrained.** The synthesis
   reference is `OR_postresample` (same lattice as O2), not O1. H0 deferred to
   a separate future experiment (yield argument: H1 has 74.8% downstream
   survival vs H0's 43.4%; single-band attribution). Accepted.
2. **Restore-only is necessary but insufficient.** The owner's fingerprint
   challenge is answered correctly: component-wise paired detector
   non-amplification (median C−B ≤ 0.00, no individual > +0.02, no new
   family/verdict crossing) + fixed real-vendor eligibility are independent
   vetoes. Accepted.
3. **Agreement is NOT "by construction."** Demosaic, clipping, sharpen can
   flip polarity between OR and O2; agreement remains a support condition
   (NCC ≥0.90, orientation ≤10°, SNR ≥4, eligibility re-applied after
   smoothing). Accepted — this corrects my §6 wording.
4. **Staged evidence funnel replaces full-round commissioning:**
   mechanism feasibility on archived checkpoints → effect-size replay on the
   whole sentinel set → candidate freeze → sealed simulated screen + panel →
   real-vendor release. Accepted as the permanent process change. C88's
   post-mortem is fair: 4D-CAM-1 was partially avoidable, 4D-1a clearly
   avoidable — a checkpoint-level replay would have caught the no-op before
   any live cell.
5. **Gate table** accepted, including the new pre-cell gates (activation
   12/12; recover ≥20% of cohort OR→O2 H1 loss, no pair <10%) and the
   release-headroom tier (0.40/0.27/0.08, model estimates).
6. **No carrier-directed optimization** — real vendors are a release gate,
   never a tuning oracle. Accepted.

## My measured addition (resolves C88's open point)

C88 noted the local restore allowance must use OR→O2, not the combined
O1→O2 loss — but no cohort OR-band mean had been supplied. Computed now from
the 12 archived B cells (`round-4d-1a/or-band-split.json`):

| stage | H1 retention | loss |
|---|---:|---:|
| resample only (O1→OR) | **1.0000** | **0.0000** |
| camera ladder only (OR→O2) | **0.4568** | **0.5432** |

- The LANCZOS resample loses essentially NO H1 energy. The entire 0.454
  combined loss is the camera ladder.
- The stricter local restoration allowance is therefore **0.5432** (not
  0.454): a 25% dose = **0.1358** at O2; planned O5 result ≈ 0.362 +
  0.1358×0.748 ≈ **0.464** — above C88's gate of 0.445. The gate stays at
  0.445 (conservative); the local cap uses OR→O2.

## Next step (commissioning the funnel, not a round)

Build the **4D-1b replay candidate** (OR→O2 H1-only, loss-constrained,
C88's structural safeguards) as a pure replay harness on the 12 archived B
cells — no deployment, no live cells:

- Step 1 mechanism feasibility: activation, support coverage, cap compliance,
  quantized change at the preservation checkpoint AND at O5, determinism.
- Step 2 effect-size replay: all pre-cell + product gates in C88's table,
  computed on archived checkpoints.
- Only if steps 1–2 clear: candidate freeze → live 24-cell MOCK screen →
  panel → single-vendor Hive leg (12 calls, freeze v3 rules).

I will author the 4D-1b replay build brief for C88 (builder) on the owner's
GO. The brief will freeze: band (H1 only), dose (25% of OR→O2 positive loss,
frozen scalar), support thresholds, exclusions, reporting, and every gate from
this response — before any candidate output is inspected.
