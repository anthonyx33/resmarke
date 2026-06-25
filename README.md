# Resmarke

Resmarke implements the bootstrap launch plan:

- Privacy-Max local processing in the browser.
- Metadata stripping by browser re-encode.
- Conservative visible AI corner-mark cleanup.
- Fibonacci-88 creator sealing.
- 1800 x 1800 JPEG export.
- DeepClean GPU job scaffolding for Supabase + RunPod.

## Local Development

```bash
npm install
npm run dev
```

Open the Vite URL and process an image. Without Supabase settings the app runs in demo-credit mode and never uploads images.

## Environment

Copy `.env.example` to `.env.local` and fill the public values:

```bash
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_STRIPE_TRIAL_LINK=
VITE_STRIPE_PRO_LINK=
VITE_STRIPE_PRO_PLUS_LINK=
```

## Privacy-Max

Privacy-Max is entirely client-side. The browser:

1. Decodes the image.
2. Draws it to an 1800 x 1800 canvas.
3. Optionally applies conservative corner-only visible mark cleanup.
4. Applies the Fibonacci-88 creator mark.
5. Exports a fresh JPEG, which strips ordinary metadata.

This mode does not claim invisible SynthID removal.

## DeepClean Beta

DeepClean is scaffolded as an async cloud job:

1. `create-deepclean-job` reserves a credit and returns a signed upload URL.
2. The frontend uploads the image to private storage.
3. `dispatch-deepclean-job` sends a RunPod job payload.
4. The RunPod worker processes the image and calls `deepclean-webhook`.
5. The webhook captures or releases the reserved credit.

Deploy the SQL migration and Supabase functions in `supabase/`, then build and publish the worker in `deepclean-worker/`.

For the fastest launch sequence, follow [LAUNCH.md](./LAUNCH.md).

The worker needs these runtime secrets:

```bash
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
DEEPCLEAN_OUTPUT_BUCKET=deepclean-outputs
BACKEND_WEBHOOK_SECRET=
HF_TOKEN=
```

## Product Guardrails

- Users must own or control the images they process.
- DeepClean should be sold as advanced hidden-watermark reduction, not permanent undetectability.
- Credits are captured only after successful DeepClean completion.
- Fibonacci-88 is a creator mark, not proof of original provenance.
