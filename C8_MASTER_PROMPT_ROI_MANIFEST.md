# C8 MASTER PROMPT — INDEPENDENT ROI MANIFEST AUTHORING (sandbox vacuum)

Date: 2026-08-26 · Issued by: master engineer · Performer: C88, independent evaluator

## 0. Your role in this task

You are an independent measurement-region author. You work ONLY from the 11 original
images. You are deliberately given **no information about attribution results, grade
outcomes, sentinel assignments, pipeline behavior, or any prior analysis**. Your boxes
must be defensible from image content alone.

Hard rules:
1. Do not open `/corpus`, `/relab`, attribution reports, pilot reports, or any outputs.
   Originals only.
2. Do not modify, rename, or re-save any image. Read-only.
3. No operational actions of any kind. This task produces exactly one JSON file.
4. Every box must be axis-aligned and inside the image (normalized coordinates).

## 1. Input: verified originals

Folder: `retrieval-checkpoints/corpus-originals/`

| File | Dimensions | SHA-256 (verify before starting) |
|---|---|---|
| IMG-1.jpg | 1024² | `442a1ccd4338d777b9a1bc7bfedb21aeb3846ae6f4f9f8ee761b9ef38d3b0dc8` |
| IMG-2.jpg | 1024² | `90b8cc8a257454b39bb67d3f8065b01ec3e17b29a3f6e1ebb80e620f02d38e91` |
| IMG-3.png | 1024² | `357d9aa522ea4d12ba3583f86477472b526168747c682cdc828ac073ce5af6a6` |
| IMG-4.png | 1024² | `9f4cfa27845ffb49f595f90c332c43b4db2bbcde6ce30633b7dcea2396fe8e1a` |
| IMG-5.png | 2048² | `91fffe56122550743c9c18da0bed78c89ca702cabb08ce125e626a89a67b0d6b` |
| IMG-6.png | 800²  | `57db03058e1ce49e15aff4a7b95f0d6d6e1e23660732aa1c54f991bec1ea567f` |
| IMG-7.png | 1080² | `dd6b9afc1cc79c2a6dcd6a4e5fb9592e9838614876754e72f9bccbcd21f7a69b` |
| IMG-8.png | 1080² | `bb1325d84ba3dd2ac8162b5c9f3607932ae6d50a7b245c467024599ad4d2319c` |
| IMG-9.png | 1600² | `70df003ece40710c00ae4173237322e88125baa4993aa8a79a69b2beccee9b70` |
| IMG-10.png | 2048² | `96379ecb1b1b5fa97ec5ef3c3149765eb9a0d4162e038db1fe882e3f7aea8de3` |
| IMG-11.jpg | 2048² | `dc9bdc02806d2391a22f092f4539be875b06c0fdf049d67b4cc3ea843da0a8c8` |

Step 0: run `shasum -a 256` on every file and confirm all 11 hashes match the table.
Any mismatch → STOP and report; do not guess.

## 2. What to author

For each image, exactly three role lists. Boxes are `[x0, y0, x1, y1]`, normalized 0–1
with (0,0) top-left. Coordinates may be given to 2 decimal places.

- **`protected`** — 1–2 boxes on the image's PRIMARY subject or architecture/product
  contours: crisp edges that a viewer cares about and that must not be damaged.
  Choose the most representative edges (subject silhouette, product seam, text, face
  features). Avoid pure background.
- **`smooth`** — 1–2 boxes in genuinely FLAT or slowly varying areas: sky, blank wall,
  smooth paint, gradient, bokeh, defocused background. If the image has no flat area,
  use `[]` and add a second texture box instead.
- **`texture`** — 1–2 boxes in fine-detail areas: foliage, gravel, fabric weave, hair,
  brick, timber grain, fine text. If no fine texture exists, use `[]` and add a second
  protected box.

Constraints:
- A box must be at least 10% and at most 60% of the image width, and at least 10% and
  at most 60% of the image height.
- Boxes of different roles must not overlap by more than ~5% of a box's area.
- Each box must be pure background OR pure subject where possible — do not straddle a
  hard edge between subject and background with the box boundary.
- Prefer centered, persistent regions (regions that survive crops/resamples).

## 3. Deliverable

Write the complete manifest to `round-4d-cam-1/roi-manifest.json` (overwrite the
skeleton), keeping the existing `object_sha256` values unchanged, filling the three
lists per image, and setting `"FINAL": true`. Format:

```json
{
  "FINAL": true,
  "round": "4D-CAM-1",
  "note": "Authored independently from originals only; freeze-before-first-light rule applies.",
  "images": {
    "IMG-1": {"object_sha256": "…unchanged…", "protected": [[0.2,0.2,0.5,0.5]], "smooth": [[…]], "texture": [[…]]},
    "…": {}
  },
  "roi_format": "boxes as [x0,y0,x1,y1] normalized 0-1"
}
```

Then report back with: (1) the 11 hash checks (pass/fail), (2) one line per image
summarizing in your own words why each protected/smooth/texture box was chosen,
(3) the new manifest sha256. No other changes anywhere in the workspace.

## 4. What happens next (not yours)

The master engineer verifies the manifest schema, hash table, and box constraints, then
records the manifest sha256 in the round ledger. The authoring is deliberately blind —
do not ask for, and do not infer, which images matter to the experiment.
