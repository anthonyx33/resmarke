import {
  BadgeCheck,
  Check,
  Cloud,
  Download,
  FileImage,
  KeyRound,
  Loader2,
  Lock,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Upload,
  WalletCards
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { config, hasSupabaseConfig } from "./lib/config";
import {
  grantLocalPrivacyCredits,
  readLocalCredits,
  spendLocalPrivacyCredit,
  type CreditSnapshot
} from "./lib/localCredits";
import { runPrivacyMax, type PrivacyMaxResult } from "./lib/privacyWorker";
import { sha256Hex } from "./lib/hash";
import {
  createDeepCleanJob,
  dispatchDeepCleanJob,
  uploadDeepCleanInput,
  type DeepCleanOutputMode,
  type DeepCleanProfile
} from "./lib/deepcleanClient";
import { supabase } from "./lib/supabase";

type ProcessingState = "idle" | "processing" | "done" | "error";

export default function App() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [resultUrl, setResultUrl] = useState<string>("");
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [resultHash, setResultHash] = useState<string>("");
  const [report, setReport] = useState<PrivacyMaxResult["report"] | null>(null);
  const [state, setState] = useState<ProcessingState>("idle");
  const [error, setError] = useState<string>("");
  const [creatorId, setCreatorId] = useState("creator@example.com");
  const [cleanVisibleMarks, setCleanVisibleMarks] = useState(true);
  const [fit, setFit] = useState<"contain" | "cover">("contain");
  const [jpegQuality, setJpegQuality] = useState(0.86);
  const [markStrength, setMarkStrength] = useState(3);
  const [credits, setCredits] = useState<CreditSnapshot>(() => readLocalCredits());
  const [deepCleanProfile, setDeepCleanProfile] = useState<DeepCleanProfile>("standard");
  const [deepCleanOutputMode, setDeepCleanOutputMode] =
    useState<DeepCleanOutputMode>("sealed");
  const [deepCleanStatus, setDeepCleanStatus] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [userId, setUserId] = useState<string>("");
  const [authStatus, setAuthStatus] = useState("");

  const canProcess =
    file &&
    state !== "processing" &&
    credits.privacyCredits > 0 &&
    (!hasSupabaseConfig || userId);
  const outputName = useMemo(() => {
    if (!file) return "resmarke-output.jpg";
    const base = file.name.replace(/\.[^.]+$/, "");
    return `${base}-resmarke.jpg`;
  }, [file]);

  useEffect(() => {
    if (!supabase) return;

    supabase.auth.getSession().then(({ data }) => {
      const user = data.session?.user;
      setUserId(user?.id ?? "");
      if (user) void refreshSupabaseCredits(user.id);
    });

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      const user = session?.user;
      setUserId(user?.id ?? "");
      if (user) void refreshSupabaseCredits(user.id);
    });

    return () => data.subscription.unsubscribe();
  }, []);

  async function refreshSupabaseCredits(nextUserId: string) {
    if (!supabase) return;
    const { data, error } = await supabase
      .from("creator_profiles")
      .select("privacy_exports_remaining, deepclean_credits")
      .eq("user_id", nextUserId)
      .single();

    if (error) {
      setAuthStatus("Signed in. Profile credits are not available yet.");
      return;
    }

    setCredits({
      privacyCredits: data.privacy_exports_remaining,
      deepCleanCredits: data.deepclean_credits,
      mode: "supabase"
    });
  }

  async function sendMagicLink() {
    if (!supabase || !authEmail.trim()) return;
    setAuthStatus("Sending sign-in link...");
    const { error } = await supabase.auth.signInWithOtp({
      email: authEmail.trim(),
      options: {
        emailRedirectTo: window.location.href
      }
    });
    setAuthStatus(error ? error.message : "Check your email for the sign-in link.");
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUserId("");
    setAuthStatus("Signed out.");
  }

  async function spendPrivacyCredit() {
    if (!supabase || !userId) {
      setCredits(spendLocalPrivacyCredit());
      return;
    }

    const { data, error } = await supabase.functions.invoke("spend-privacy-credit", {
      body: { amount: 1 }
    });
    if (error) throw error;
    setCredits({
      privacyCredits: data.privacyCredits,
      deepCleanCredits: data.deepCleanCredits,
      mode: "supabase"
    });
  }

  function onFileSelected(nextFile: File | null) {
    setError("");
    setState("idle");
    setReport(null);
    setResultHash("");
    setResultBlob(null);
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    setResultUrl("");

    if (!nextFile) {
      setFile(null);
      setPreviewUrl("");
      return;
    }

    if (!nextFile.type.startsWith("image/")) {
      setError("Choose a JPEG, PNG, or WebP image.");
      return;
    }

    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));
  }

  async function processPrivacyMax() {
    if (!file || credits.privacyCredits <= 0) return;
    setState("processing");
    setError("");
    setReport(null);
    setResultHash("");

    try {
      const result = await runPrivacyMax({
        file,
        creatorId,
        cleanVisibleMarks,
        markStrength,
        jpegQuality,
        targetSize: 1800,
        fit
      });

      const buffer = await result.blob.arrayBuffer();
      const hash = await sha256Hex(buffer);
      const nextUrl = URL.createObjectURL(result.blob);

      if (resultUrl) URL.revokeObjectURL(resultUrl);
      setResultUrl(nextUrl);
      setResultBlob(result.blob);
      setResultHash(hash);
      setReport(result.report);
      await spendPrivacyCredit();
      setState("done");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Processing failed.");
      setState("error");
    }
  }

  async function startDeepCleanBeta() {
    if (!file) {
      setDeepCleanStatus("Choose an image first.");
      return;
    }

    setDeepCleanStatus("Creating DeepClean job...");
    try {
      const job = await createDeepCleanJob({
        file,
        profile: deepCleanProfile,
        outputMode: deepCleanOutputMode
      });
      setDeepCleanStatus("Uploading private input...");
      await uploadDeepCleanInput(job, file);
      setDeepCleanStatus("Dispatching GPU worker...");
      await dispatchDeepCleanJob(job.id);
      setDeepCleanStatus(`Job ${job.id} is queued. Watch Supabase job status for progress.`);
    } catch (nextError) {
      setDeepCleanStatus(
        nextError instanceof Error ? nextError.message : "DeepClean is not configured."
      );
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand-row">
            <ShieldCheck size={28} aria-hidden="true" />
            <h1>Resmarke</h1>
          </div>
          <p>Privacy-first creator cleanup and creator sealing.</p>
        </div>
        <div className="credit-pill" title="Privacy-Max demo credits">
          <WalletCards size={18} aria-hidden="true" />
          <span>
            {credits.privacyCredits} Privacy-Max exports
            {credits.mode === "demo" ? " demo" : ""}
          </span>
        </div>
      </header>

      <section className="account-band">
        <div>
          <div className="panel-header">
            <KeyRound size={20} aria-hidden="true" />
            <h2>Account</h2>
          </div>
          <p>
            {hasSupabaseConfig
              ? userId
                ? "Signed in. Credits are tracked in Supabase."
                : "Sign in to use real Supabase credits."
              : "Demo mode is active because Supabase is not configured."}
          </p>
        </div>
        {hasSupabaseConfig ? (
          userId ? (
            <button type="button" onClick={signOut}>
              Sign out
            </button>
          ) : (
            <div className="auth-controls">
              <input
                value={authEmail}
                onChange={(event) => setAuthEmail(event.target.value)}
                placeholder="email@example.com"
                type="email"
              />
              <button type="button" onClick={sendMagicLink}>
                Send link
              </button>
            </div>
          )
        ) : null}
        {authStatus ? <p className="account-status">{authStatus}</p> : null}
      </section>

      <section className="notice-band">
        <Lock size={20} aria-hidden="true" />
        <p>
          Privacy-Max runs locally in your browser. Images are not uploaded. DeepClean is a
          separate cloud GPU beta for advanced hidden watermark reduction and is charged only
          after successful processing.
        </p>
      </section>

      <section className="workspace-grid">
        <div className="tool-panel">
          <div className="panel-header">
            <FileImage size={20} aria-hidden="true" />
            <h2>Input</h2>
          </div>

          <button
            className="drop-zone"
            type="button"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              onFileSelected(event.dataTransfer.files.item(0));
            }}
          >
            {previewUrl ? (
              <img src={previewUrl} alt="Selected image preview" />
            ) : (
              <span>
                <Upload size={26} aria-hidden="true" />
                Drop an image or choose a file
              </span>
            )}
          </button>
          <input
            ref={fileInputRef}
            className="sr-only"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(event) => onFileSelected(event.target.files?.item(0) ?? null)}
          />

          <div className="file-meta">
            <span>{file ? file.name : "No image selected"}</span>
            <span>{file ? `${(file.size / 1_000_000).toFixed(2)} MB` : "JPEG, PNG, WebP"}</span>
          </div>
        </div>

        <div className="tool-panel settings-panel">
          <div className="panel-header">
            <KeyRound size={20} aria-hidden="true" />
            <h2>Privacy-Max</h2>
          </div>

          <label className="field">
            <span>Creator ID</span>
            <input
              value={creatorId}
              onChange={(event) => setCreatorId(event.target.value)}
              placeholder="creator@example.com"
            />
          </label>

          <div className="segmented" aria-label="Image fit">
            <button
              className={fit === "contain" ? "active" : ""}
              type="button"
              onClick={() => setFit("contain")}
            >
              Contain
            </button>
            <button
              className={fit === "cover" ? "active" : ""}
              type="button"
              onClick={() => setFit("cover")}
            >
              Cover
            </button>
          </div>

          <label className="check-row">
            <input
              type="checkbox"
              checked={cleanVisibleMarks}
              onChange={(event) => setCleanVisibleMarks(event.target.checked)}
            />
            <span>Clean reliable visible AI corner marks</span>
          </label>

          <label className="field range-field">
            <span>Fibonacci-88 strength: {markStrength}</span>
            <input
              type="range"
              min="1"
              max="8"
              value={markStrength}
              onChange={(event) => setMarkStrength(Number(event.target.value))}
            />
          </label>

          <label className="field range-field">
            <span>JPEG quality: {Math.round(jpegQuality * 100)}%</span>
            <input
              type="range"
              min="0.7"
              max="0.94"
              step="0.01"
              value={jpegQuality}
              onChange={(event) => setJpegQuality(Number(event.target.value))}
            />
          </label>

          <button
            className="primary-action"
            type="button"
            disabled={!canProcess}
            onClick={processPrivacyMax}
          >
            {state === "processing" ? (
              <Loader2 className="spin" size={20} aria-hidden="true" />
            ) : (
              <Sparkles size={20} aria-hidden="true" />
            )}
            Process locally
          </button>

          {hasSupabaseConfig && !userId ? (
            <div className="inline-warning">Sign in before processing with production credits.</div>
          ) : null}

          {credits.privacyCredits <= 0 ? (
            <div className="inline-warning">
              No demo credits left.
              {credits.mode === "demo" ? (
                <button type="button" onClick={() => setCredits(grantLocalPrivacyCredits(15))}>
                  Add 15 demo credits
                </button>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="tool-panel">
          <div className="panel-header">
            <Download size={20} aria-hidden="true" />
            <h2>Output</h2>
          </div>

          <div className="output-frame">
            {resultUrl ? (
              <img src={resultUrl} alt="Processed output preview" />
            ) : (
              <span>Processed 1800 x 1800 JPEG appears here</span>
            )}
          </div>

          {state === "error" && <p className="error-text">{error}</p>}

          {report && (
            <div className="report-grid">
              <Metric label="Metadata" value="Stripped" />
              <Metric
                label="Visible cleanup"
                value={report.visibleCleanupApplied ? `${report.visibleCleanupPixels} px` : "None"}
              />
              <Metric label="Seal" value="Fibonacci-88" />
              <Metric label="Hash" value={resultHash.slice(0, 12)} />
            </div>
          )}

          <a
            className={`download-button ${resultBlob ? "" : "disabled"}`}
            href={resultUrl || undefined}
            download={outputName}
            aria-disabled={!resultBlob}
          >
            <Download size={20} aria-hidden="true" />
            Download JPEG
          </a>
        </div>
      </section>

      <section className="deepclean-band">
        <div className="deepclean-copy">
          <div className="panel-header">
            <Cloud size={20} aria-hidden="true" />
            <h2>DeepClean GPU Beta</h2>
          </div>
          <p>
            Optional cloud regeneration for advanced hidden watermark reduction. Use only for
            images you own or control. A credit is captured only after the worker completes
            successfully.
          </p>
        </div>

        <div className="deepclean-controls">
          <select
            value={deepCleanProfile}
            onChange={(event) => setDeepCleanProfile(event.target.value as DeepCleanProfile)}
            aria-label="DeepClean profile"
          >
            <option value="standard">Standard</option>
            <option value="strong">Strong</option>
            <option value="max">Max</option>
          </select>
          <select
            value={deepCleanOutputMode}
            onChange={(event) =>
              setDeepCleanOutputMode(event.target.value as DeepCleanOutputMode)
            }
            aria-label="DeepClean output mode"
          >
            <option value="stripped">Stripped only</option>
            <option value="sealed">Stripped + Fibonacci-88</option>
            <option value="sealed-stamped">Stripped + seal + stamp</option>
          </select>
          <button type="button" onClick={startDeepCleanBeta} disabled={!file}>
            <Cloud size={18} aria-hidden="true" />
            Queue beta job
          </button>
        </div>

        <p className="deepclean-status">
          {hasSupabaseConfig
            ? deepCleanStatus || "Supabase is configured. DeepClean jobs can be queued."
            : "Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to enable DeepClean job creation."}
        </p>
      </section>

      <section className="pricing-grid">
        <Plan title="Free" price="$0" detail="3 Privacy-Max exports" link="" />
        <Plan title="Trial" price="$1" detail="15 exports for 7 days" link={config.stripeTrialLink} />
        <Plan title="Pro" price="$19.99" detail="200 monthly exports" link={config.stripeProLink} />
        <Plan
          title="Pro+"
          price="$29.99"
          detail="500 monthly exports, DeepClean add-ons"
          link={config.stripeProPlusLink}
        />
      </section>

      <footer className="footer">
        <span>
          Use only on images you own or control. Fibonacci-88 is a creator mark, not proof of
          original provenance.
        </span>
        <button
          type="button"
          onClick={() => {
            onFileSelected(null);
            setCredits(readLocalCredits());
          }}
        >
          <RotateCcw size={16} aria-hidden="true" />
          Reset
        </button>
      </footer>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Plan({
  title,
  price,
  detail,
  link
}: {
  title: string;
  price: string;
  detail: string;
  link: string;
}) {
  return (
    <div className="plan-card">
      <div>
        <h3>{title}</h3>
        <strong>{price}</strong>
        <p>{detail}</p>
      </div>
      {link ? (
        <a href={link}>
          <Check size={18} aria-hidden="true" />
          Choose
        </a>
      ) : (
        <span>
          <BadgeCheck size={18} aria-hidden="true" />
          Included
        </span>
      )}
    </div>
  );
}
