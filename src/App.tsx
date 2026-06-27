import {
  ArrowRight,
  Check,
  ChevronDown,
  Cloud,
  Cpu,
  Download,
  Fingerprint,
  Gauge,
  ImageOff,
  Loader2,
  Lock,
  Moon,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Sun,
  Upload,
  Wallet
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { config, hasSupabaseConfig } from "./lib/config";
import {
  grantLocalPrivacyCredits,
  readLocalCredits,
  spendLocalPrivacyCredit,
  type CreditSnapshot
} from "./lib/localCredits";
import {
  runPrivacyMax,
  type OutputFormat,
  type OutputSizeMode,
  type PrivacyMaxResult
} from "./lib/privacyWorker";
import { sha256Hex } from "./lib/hash";
import {
  cancelDeepCleanJob,
  createDeepCleanJob,
  dispatchDeepCleanJob,
  getDeepCleanJob,
  uploadDeepCleanInput,
  type DeepCleanJob,
  type DeepCleanOutputMode,
  type DeepCleanProfile
} from "./lib/deepcleanClient";
import {
  getAdminRunpodEndpoint,
  updateAdminRunpodEndpoint,
  type AdminRunpodEndpoint
} from "./lib/adminRunpodClient";
import { supabase } from "./lib/supabase";

type ProcessingState = "idle" | "processing" | "done" | "error";
type Theme = "light" | "dark";
type AuthMode = "signin" | "signup";

function initialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const saved = localStorage.getItem("resmarke:theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [dragging, setDragging] = useState(false);
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
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("jpeg");
  const [sizeMode, setSizeMode] = useState<OutputSizeMode>("original");
  const [inputDims, setInputDims] = useState<{ w: number; h: number } | null>(null);
  const [customWidth, setCustomWidth] = useState(0);
  const [customHeight, setCustomHeight] = useState(0);
  const [credits, setCredits] = useState<CreditSnapshot>(() => readLocalCredits());
  const [deepCleanProfile, setDeepCleanProfile] = useState<DeepCleanProfile>("standard");
  const [deepCleanMicroTextureJitter, setDeepCleanMicroTextureJitter] = useState(false);
  const [deepCleanOutputMode, setDeepCleanOutputMode] =
    useState<DeepCleanOutputMode>("sealed");
  const [deepCleanStatus, setDeepCleanStatus] = useState("");
  const [deepCleanJob, setDeepCleanJob] = useState<DeepCleanJob | null>(null);
  const deepCleanPollRef = useRef<number | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [userId, setUserId] = useState<string>("");
  const [userEmail, setUserEmail] = useState<string>("");
  const [authStatus, setAuthStatus] = useState("");
  const [adminEndpoint, setAdminEndpoint] = useState<AdminRunpodEndpoint | null>(null);
  const [adminIdleTimeout, setAdminIdleTimeout] = useState(300);
  const [adminWorkersMin, setAdminWorkersMin] = useState(0);
  const [adminWorkersMax, setAdminWorkersMax] = useState(1);
  const [adminStatus, setAdminStatus] = useState("");
  const [adminBusy, setAdminBusy] = useState(false);

  // Privacy-Max can run locally in demo mode. Sign-in upgrades to Supabase credits.
  const canProcess = !!file && state !== "processing" && credits.privacyCredits > 0;
  const isAdminUi =
    !!userEmail &&
    config.adminEmails.length > 0 &&
    config.adminEmails.includes(userEmail.toLowerCase());

  const outputName = useMemo(() => {
    const ext = outputFormat === "png" ? "png" : outputFormat === "webp" ? "webp" : "jpg";
    if (!file) return `resmarke-output.${ext}`;
    const base = file.name.replace(/\.[^.]+$/, "");
    return `${base}-resmarke.${ext}`;
  }, [file, outputFormat]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("resmarke:theme", theme);
  }, [theme]);

  useEffect(() => {
    return () => {
      if (deepCleanPollRef.current) window.clearInterval(deepCleanPollRef.current);
    };
  }, []);

  useEffect(() => {
    if (!supabase) return;

    supabase.auth.getSession().then(({ data }) => {
      const user = data.session?.user;
      setUserId(user?.id ?? "");
      setUserEmail(user?.email ?? "");
      if (user) void refreshSupabaseCredits(user.id);
    });

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      const user = session?.user;
      setUserId(user?.id ?? "");
      setUserEmail(user?.email ?? "");
      if (user) void refreshSupabaseCredits(user.id);
    });

    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (isAdminUi) void refreshAdminEndpoint();
  }, [isAdminUi]);

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

  async function submitPasswordAuth() {
    if (!supabase) return;
    const email = authEmail.trim();
    if (!email || !authPassword) {
      setAuthStatus("Enter your email and password.");
      return;
    }
    if (authPassword.length < 6) {
      setAuthStatus("Password must be at least 6 characters.");
      return;
    }

    setAuthStatus(authMode === "signin" ? "Signing in..." : "Creating account...");
    if (authMode === "signin") {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password: authPassword
      });
      setAuthStatus(error ? error.message : "Signed in.");
      if (!error) setAuthPassword("");
      return;
    }

    const { data, error } = await supabase.auth.signUp({
      email,
      password: authPassword,
      options: { emailRedirectTo: window.location.href }
    });
    if (error) {
      setAuthStatus(error.message);
      return;
    }
    if (data.session) {
      setAuthStatus("Account created. You are signed in.");
      setAuthPassword("");
      return;
    }
    setAuthStatus("Account created. Check your email to confirm before signing in.");
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUserId("");
    setUserEmail("");
    setAdminEndpoint(null);
    setCredits(readLocalCredits());
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

    // Default output mirrors the input: same format, same dimensions.
    const nextFormat: OutputFormat = nextFile.type.includes("png")
      ? "png"
      : nextFile.type.includes("webp")
        ? "webp"
        : "jpeg";
    setOutputFormat(nextFormat);
    setSizeMode("original");
    setInputDims(null);

    createImageBitmap(nextFile)
      .then((bitmap) => {
        setInputDims({ w: bitmap.width, h: bitmap.height });
        setCustomWidth(bitmap.width);
        setCustomHeight(bitmap.height);
        bitmap.close();
      })
      .catch(() => setInputDims(null));
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
        quality: jpegQuality,
        format: outputFormat,
        sizeMode,
        squareSize: 1800,
        customWidth,
        customHeight,
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
    if (hasSupabaseConfig && !userId) {
      setDeepCleanStatus("Sign in before queueing a Remarkee Max job.");
      return;
    }

    let createdJob: DeepCleanJob | null = null;
    const requestedProfile: DeepCleanProfile =
      deepCleanProfile === "max" && deepCleanMicroTextureJitter ? "max-jitter" : deepCleanProfile;
    setDeepCleanStatus("Creating Remarkee Max job...");
    try {
      const job = await createDeepCleanJob({
        file,
        creatorId,
        profile: requestedProfile,
        outputMode: deepCleanOutputMode
      });
      createdJob = job;
      setDeepCleanJob(job);
      setDeepCleanStatus("Uploading private input...");
      await uploadDeepCleanInput(job, file);
      setDeepCleanStatus("Dispatching GPU worker...");
      await dispatchDeepCleanJob(job.id);
      setDeepCleanStatus(`Job ${job.id} is running on the GPU worker.`);
      startDeepCleanPolling(job.id);
    } catch (nextError) {
      if (createdJob) {
        await cancelDeepCleanJob(createdJob.id).catch(() => undefined);
      }
      setDeepCleanStatus(
        nextError instanceof Error ? nextError.message : "Remarkee Max is not configured yet."
      );
    }
  }

  function startDeepCleanPolling(jobId: string) {
    if (deepCleanPollRef.current) window.clearInterval(deepCleanPollRef.current);

    const tick = async () => {
      try {
        const job = await getDeepCleanJob(jobId);
        setDeepCleanJob(job);
        if (job.status === "completed") {
          if (deepCleanPollRef.current) window.clearInterval(deepCleanPollRef.current);
          deepCleanPollRef.current = null;
          setDeepCleanStatus(
            `Completed in ${job.runtimeMs ? Math.round(job.runtimeMs / 1000) : "?"}s.`
          );
        } else if (job.status === "failed") {
          if (deepCleanPollRef.current) window.clearInterval(deepCleanPollRef.current);
          deepCleanPollRef.current = null;
          setDeepCleanStatus(job.failureReason || "Remarkee Max failed and the credit was released.");
          if (userId) void refreshSupabaseCredits(userId);
        } else {
          setDeepCleanStatus(`GPU job status: ${job.status}.`);
        }
      } catch (nextError) {
        setDeepCleanStatus(
          nextError instanceof Error ? nextError.message : "Could not refresh Remarkee Max job."
        );
      }
    };

    void tick();
    deepCleanPollRef.current = window.setInterval(tick, 3500);
  }

  async function refreshAdminEndpoint() {
    if (!isAdminUi) return;
    setAdminBusy(true);
    setAdminStatus("Reading RunPod endpoint...");
    try {
      const endpoint = await getAdminRunpodEndpoint();
      setAdminEndpoint(endpoint);
      setAdminIdleTimeout(endpoint.idleTimeout);
      setAdminWorkersMin(endpoint.workersMin);
      setAdminWorkersMax(endpoint.workersMax);
      setAdminStatus("RunPod endpoint loaded.");
    } catch (nextError) {
      setAdminStatus(nextError instanceof Error ? nextError.message : "Could not load endpoint.");
    } finally {
      setAdminBusy(false);
    }
  }

  async function applyAdminPreset(preset: "sleep" | "warm-window" | "keep-warm" | "manual") {
    if (!isAdminUi) return;
    setAdminBusy(true);
    const labels = {
      sleep: "Sleep mode",
      "warm-window": "Warm window",
      "keep-warm": "Keep warm",
      manual: "Manual settings"
    };
    setAdminStatus(`Applying ${labels[preset]}...`);
    try {
      const endpoint = await updateAdminRunpodEndpoint({
        preset,
        idleTimeout: adminIdleTimeout,
        workersMin: adminWorkersMin,
        workersMax: adminWorkersMax
      });
      setAdminEndpoint(endpoint);
      setAdminIdleTimeout(endpoint.idleTimeout);
      setAdminWorkersMin(endpoint.workersMin);
      setAdminWorkersMax(endpoint.workersMax);
      setAdminStatus(
        `${labels[preset]} applied: active ${endpoint.workersMin}, max ${endpoint.workersMax}, idle ${endpoint.idleTimeout}s.`
      );
    } catch (nextError) {
      setAdminStatus(nextError instanceof Error ? nextError.message : "Could not update endpoint.");
    } finally {
      setAdminBusy(false);
    }
  }

  function resetAll() {
    onFileSelected(null);
    setDeepCleanStatus("");
    setDeepCleanJob(null);
    setCredits(userId ? credits : readLocalCredits());
  }

  const openPicker = () => fileInputRef.current?.click();

  return (
    <div className="page">
      <nav className="nav">
        <a className="brand" href="/">
          <span className="brand-mark">
            <ShieldCheck size={19} aria-hidden="true" />
          </span>
          <span>ResMarke</span>
        </a>

        <div className="nav-links">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#pricing">Pricing</a>
          <a href="#faq">FAQ</a>
        </div>

        <div className="nav-right">
          <span className="credit-pill" title="Privacy export credits">
            <Wallet size={15} aria-hidden="true" />
            <strong>{credits.privacyCredits}</strong> exports
          </span>

          {hasSupabaseConfig ? (
            userId ? (
              <button className="icon-btn" type="button" onClick={signOut} title="Sign out">
                <RotateCcw size={16} aria-hidden="true" />
              </button>
            ) : (
              <details className="auth">
                <summary>{authMode === "signin" ? "Sign in" : "Sign up"}</summary>
                <div className="auth-body">
                  <div className="auth-tabs" aria-label="Authentication mode">
                    <button
                      className={authMode === "signin" ? "active" : ""}
                      type="button"
                      onClick={() => {
                        setAuthMode("signin");
                        setAuthStatus("");
                      }}
                    >
                      Sign in
                    </button>
                    <button
                      className={authMode === "signup" ? "active" : ""}
                      type="button"
                      onClick={() => {
                        setAuthMode("signup");
                        setAuthStatus("");
                      }}
                    >
                      Sign up
                    </button>
                  </div>
                  <p>
                    {authMode === "signin"
                      ? "Enter your email and password to access your credits."
                      : "Create an account with email and password."}
                  </p>
                  <input
                    className="input"
                    value={authEmail}
                    onChange={(event) => setAuthEmail(event.target.value)}
                    placeholder="you@email.com"
                    type="email"
                    autoComplete="email"
                  />
                  <input
                    className="input"
                    value={authPassword}
                    onChange={(event) => setAuthPassword(event.target.value)}
                    placeholder="Password"
                    type="password"
                    autoComplete={authMode === "signin" ? "current-password" : "new-password"}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void submitPasswordAuth();
                    }}
                  />
                  <button className="btn btn-primary" type="button" onClick={submitPasswordAuth}>
                    {authMode === "signin" ? "Sign in" : "Create account"}
                  </button>
                  {authStatus ? <p>{authStatus}</p> : null}
                </div>
              </details>
            )
          ) : null}

          <button
            className="icon-btn"
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </nav>

      <main className="main">
        {!file ? (
          <section className="hero">
            <span className="hero-badge">
              <span className="dot" /> Privacy-first · Runs in your browser
            </span>
            <h1 className="hero-title">
              Clean your images.
              <br />
              <span className="accent">Reclaim your privacy.</span>
            </h1>
            <p className="hero-sub">
              Strip hidden metadata, remove visible AI marks, and seal your work — instantly,
              locally, and privately. Nothing ever leaves your device.
            </p>

            <Dropzone
              large
              previewUrl=""
              dragging={dragging}
              setDragging={setDragging}
              onPick={() => fileInputRef.current?.click()}
              onDropFile={onFileSelected}
            />

            <p className="hero-trust">
              <Lock size={14} aria-hidden="true" /> No uploads. Processing happens on your device.
            </p>
          </section>
        ) : (
          <section className="workspace">
            <div className="work-head">
              <h2>Workspace</h2>
              <button className="btn btn-ghost" type="button" onClick={resetAll}>
                <RotateCcw size={16} aria-hidden="true" /> Start over
              </button>
            </div>

            <div className="work-grid">
              {/* Original */}
              <div className="card">
                <div className="card-label">Original</div>
                <Dropzone
                  previewUrl={previewUrl}
                  dragging={dragging}
                  setDragging={setDragging}
                  onPick={() => fileInputRef.current?.click()}
                  onDropFile={onFileSelected}
                />
                <div className="file-meta">
                  <span className="name">{file.name}</span>
                  <span>{(file.size / 1_000_000).toFixed(2)} MB</span>
                </div>
              </div>

              {/* Cleaned */}
              <div className="card">
                <div className="card-label">Cleaned result</div>
                <div className="output-frame">
                  {resultUrl ? (
                    <img src={resultUrl} alt="Cleaned output preview" />
                  ) : (
                    <div className="output-empty">
                      <ImageOff size={26} aria-hidden="true" />
                      <span>Your cleaned 1800×1800 JPEG appears here</span>
                    </div>
                  )}
                </div>

                {report && (
                  <div className="report-grid">
                    <Metric label="Metadata" value="Stripped" />
                    <Metric
                      label="Visible cleanup"
                      value={
                        report.visibleCleanupApplied
                          ? `${report.visibleCleanupPixels} px`
                          : "None"
                      }
                    />
                    <Metric label="Seal" value="Fibonacci-88" />
                    <Metric label="Hash" value={resultHash.slice(0, 12)} />
                  </div>
                )}

                <div className="action-row">
                  <button
                    className="btn btn-primary btn-block"
                    type="button"
                    disabled={!canProcess}
                    onClick={processPrivacyMax}
                  >
                    {state === "processing" ? (
                      <>
                        <Loader2 className="spin" size={18} aria-hidden="true" /> Cleaning…
                      </>
                    ) : (
                      <>
                        <Sparkles size={18} aria-hidden="true" />
                        {resultBlob ? "Clean again" : "Clean image"}
                      </>
                    )}
                  </button>

                  {resultBlob ? (
                    <a className="btn btn-ghost btn-block" href={resultUrl} download={outputName}>
                      <Download size={18} aria-hidden="true" /> Download JPEG
                    </a>
                  ) : null}
                </div>

                {state === "error" && <p className="error-text">{error}</p>}

                {credits.privacyCredits <= 0 ? (
                  <div className="inline-warning">
                    <span>No export credits left.</span>
                    {credits.mode === "demo" ? (
                      <button type="button" onClick={() => setCredits(grantLocalPrivacyCredits(15))}>
                        Add 15 credits
                      </button>
                    ) : null}
                  </div>
                ) : null}

                <details className="options">
                  <summary>
                    Advanced options <ChevronDown className="chev" size={16} aria-hidden="true" />
                  </summary>
                  <div className="options-body">
                    <div className="opt-section">
                      <div className="opt-section-title">Output</div>

                      <div className="field">
                        <span>Format</span>
                        <div className="segmented" aria-label="Output format">
                          <button
                            className={outputFormat === "jpeg" ? "active" : ""}
                            type="button"
                            onClick={() => setOutputFormat("jpeg")}
                          >
                            JPG
                          </button>
                          <button
                            className={outputFormat === "png" ? "active" : ""}
                            type="button"
                            onClick={() => setOutputFormat("png")}
                          >
                            PNG
                          </button>
                          <button
                            className={outputFormat === "webp" ? "active" : ""}
                            type="button"
                            onClick={() => setOutputFormat("webp")}
                          >
                            WebP
                          </button>
                        </div>
                      </div>

                      <label className="field">
                        <span>Size &amp; ratio</span>
                        <select
                          className="select"
                          value={sizeMode}
                          onChange={(event) => setSizeMode(event.target.value as OutputSizeMode)}
                        >
                          <option value="original">
                            Match input{inputDims ? ` (${inputDims.w}×${inputDims.h})` : ""}
                          </option>
                          <option value="square">Square (1800×1800)</option>
                          <option value="custom">Custom…</option>
                        </select>
                      </label>

                      {sizeMode === "custom" ? (
                        <div className="dim-row">
                          <label className="field">
                            <span>Width</span>
                            <input
                              className="input"
                              type="number"
                              min={16}
                              max={8192}
                              value={customWidth || ""}
                              onChange={(event) => setCustomWidth(Number(event.target.value))}
                            />
                          </label>
                          <span className="dim-x">×</span>
                          <label className="field">
                            <span>Height</span>
                            <input
                              className="input"
                              type="number"
                              min={16}
                              max={8192}
                              value={customHeight || ""}
                              onChange={(event) => setCustomHeight(Number(event.target.value))}
                            />
                          </label>
                        </div>
                      ) : null}

                      {sizeMode !== "original" ? (
                        <div className="field">
                          <span>Fit</span>
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
                        </div>
                      ) : null}

                      {outputFormat !== "png" ? (
                        <label className="range-field">
                          <span>Quality: {Math.round(jpegQuality * 100)}%</span>
                          <input
                            type="range"
                            min="0.7"
                            max="0.94"
                            step="0.01"
                            value={jpegQuality}
                            onChange={(event) => setJpegQuality(Number(event.target.value))}
                          />
                        </label>
                      ) : null}
                    </div>

                    <div className="opt-section">
                      <div className="opt-section-title">Privacy &amp; seal</div>

                      <label className="field">
                        <span>Creator ID</span>
                        <input
                          className="input"
                          value={creatorId}
                          onChange={(event) => setCreatorId(event.target.value)}
                          placeholder="creator@example.com"
                        />
                      </label>

                      <label className="check-row">
                        <input
                          type="checkbox"
                          checked={cleanVisibleMarks}
                          onChange={(event) => setCleanVisibleMarks(event.target.checked)}
                        />
                        <span>Clean visible AI corner marks</span>
                      </label>

                      <label className="range-field">
                        <span>Fibonacci-88 strength: {markStrength}</span>
                        <input
                          type="range"
                          min="1"
                          max="8"
                          value={markStrength}
                          onChange={(event) => setMarkStrength(Number(event.target.value))}
                        />
                      </label>
                    </div>
                  </div>
                </details>
              </div>
            </div>

            {/* Remarkee Max */}
            <div className="deepclean">
              <div className="deepclean-head">
                <Cloud size={20} aria-hidden="true" />
                <h3>Remarkee Max</h3>
                <span className="tag">
                  <Cpu size={11} aria-hidden="true" /> Beta
                </span>
              </div>
              <p className="desc">
                Optional cloud regeneration for advanced hidden-watermark reduction. Use only on
                images you own or control. A credit is captured only after the GPU worker completes
                successfully.
              </p>

              <div className="deepclean-controls">
                <label className="field">
                  <span>Profile</span>
                  <select
                    className="select"
                    value={deepCleanProfile}
                    onChange={(event) => {
                      const profile = event.target.value as DeepCleanProfile;
                      setDeepCleanProfile(profile);
                      if (profile !== "max") setDeepCleanMicroTextureJitter(false);
                    }}
                  >
                    <option value="standard">Standard</option>
                    <option value="strong">Strong</option>
                    <option value="max">Max (Expert)</option>
                  </select>
                </label>
                {deepCleanProfile === "max" ? (
                  <div className="field">
                    <span>Experimental</span>
                    <label className="toggle-row">
                      <input
                        type="checkbox"
                        checked={deepCleanMicroTextureJitter}
                        onChange={(event) => setDeepCleanMicroTextureJitter(event.target.checked)}
                      />
                      <span>Micro-texture jitter</span>
                    </label>
                  </div>
                ) : null}
                <label className="field">
                  <span>Output</span>
                  <select
                    className="select"
                    value={deepCleanOutputMode}
                    onChange={(event) =>
                      setDeepCleanOutputMode(event.target.value as DeepCleanOutputMode)
                    }
                  >
                    <option value="stripped">Stripped only</option>
                    <option value="sealed">Stripped + Fibonacci-88</option>
                    <option value="sealed-stamped">Stripped + seal + stamp</option>
                  </select>
                </label>
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={startDeepCleanBeta}
                  disabled={!file}
                >
                  <Cloud size={18} aria-hidden="true" /> Queue job
                </button>
              </div>

              <p className="deepclean-status">
                {hasSupabaseConfig
                  ? deepCleanStatus || "Connected. Queue a job to run it on the GPU worker."
                  : "Set Supabase env vars to enable Remarkee Max."}
              </p>
              {deepCleanJob &&
              ["processing", "completed", "failed"].includes(deepCleanJob.status) ? (
                <div className="deepclean-result">
                  <div className="output-frame">
                    {deepCleanJob.outputUrl ? (
                      <img src={deepCleanJob.outputUrl} alt="Remarkee Max result preview" />
                    ) : deepCleanJob.status === "failed" ? (
                      <div className="output-empty">
                        <ImageOff size={26} aria-hidden="true" />
                        <span>{deepCleanJob.failureReason || "Remarkee Max failed."}</span>
                      </div>
                    ) : (
                      <div className="output-empty">
                        <Loader2 className="spin" size={26} aria-hidden="true" />
                        <span>GPU worker is regenerating your image…</span>
                      </div>
                    )}
                  </div>

                  <div className="deepclean-result-info">
                    <div className="card-label">Remarkee Max result</div>
                    {deepCleanJob.status === "completed" ? (
                      <>
                        <div className="report-grid">
                          <Metric label="Status" value="Completed" />
                          <Metric
                            label="Runtime"
                            value={
                              deepCleanJob.runtimeMs
                                ? `${(deepCleanJob.runtimeMs / 1000).toFixed(1)}s`
                                : "—"
                            }
                          />
                          <Metric label="GPU" value={deepCleanJob.gpuType || "—"} />
                          <Metric label="Output" value={deepCleanOutputMode} />
                        </div>
                        <a
                          className="btn btn-primary btn-block deepclean-download"
                          href={deepCleanJob.outputUrl}
                          download={deepCleanJob.outputName ?? "IMG_0000.JPG"}
                        >
                          <Download size={18} aria-hidden="true" /> Download result
                        </a>
                      </>
                    ) : deepCleanJob.status === "failed" ? (
                      <p className="error-text">
                        {deepCleanJob.failureReason ||
                          "Remarkee Max failed; your credit was released."}
                      </p>
                    ) : (
                      <p className="deepclean-status">Hang tight — regenerating on the GPU…</p>
                    )}
                  </div>
                </div>
              ) : null}
            </div>

            {isAdminUi ? (
              <div className="admin-panel">
                <div className="deepclean-head">
                  <Gauge size={20} aria-hidden="true" />
                  <h3>Admin GPU standby</h3>
                  <span className="tag">Private</span>
                </div>
                <p className="desc">
                  Control RunPod worker cost for your personal/admin sessions. Sleep mode shuts the
                  worker down quickly; warm window keeps it ready briefly after a job; keep warm
                  holds one active worker until you switch it off.
                </p>

                <div className="admin-metrics">
                  <Metric label="Endpoint" value={adminEndpoint?.name ?? "Not loaded"} />
                  <Metric label="Active" value={String(adminEndpoint?.workersMin ?? "—")} />
                  <Metric label="Max" value={String(adminEndpoint?.workersMax ?? "—")} />
                  <Metric
                    label="Idle timeout"
                    value={
                      typeof adminEndpoint?.idleTimeout === "number"
                        ? `${adminEndpoint.idleTimeout}s`
                        : "—"
                    }
                  />
                </div>

                <div className="deepclean-controls admin-controls">
                  <label className="field">
                    <span>Idle timeout</span>
                    <input
                      className="input"
                      type="number"
                      min={5}
                      max={3600}
                      value={adminIdleTimeout}
                      onChange={(event) => setAdminIdleTimeout(Number(event.target.value))}
                    />
                  </label>
                  <label className="field">
                    <span>Active workers</span>
                    <select
                      className="select"
                      value={adminWorkersMin}
                      onChange={(event) => setAdminWorkersMin(Number(event.target.value))}
                    >
                      <option value={0}>0 · scale to zero</option>
                      <option value={1}>1 · keep warm</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Max workers</span>
                    <select
                      className="select"
                      value={adminWorkersMax}
                      onChange={(event) => setAdminWorkersMax(Number(event.target.value))}
                    >
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                      <option value={3}>3</option>
                    </select>
                  </label>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={adminBusy}
                    onClick={refreshAdminEndpoint}
                  >
                    Refresh
                  </button>
                </div>

                <div className="admin-actions">
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={adminBusy}
                    onClick={() => applyAdminPreset("sleep")}
                  >
                    Sleep now
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={adminBusy}
                    onClick={() => applyAdminPreset("warm-window")}
                  >
                    Warm window
                  </button>
                  <button
                    className="btn btn-primary"
                    type="button"
                    disabled={adminBusy}
                    onClick={() => applyAdminPreset("keep-warm")}
                  >
                    Keep warm
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    disabled={adminBusy}
                    onClick={() => applyAdminPreset("manual")}
                  >
                    Apply manual
                  </button>
                </div>

                <p className="deepclean-status">
                  {adminStatus || "Admin controls are available for this signed-in account."}
                </p>
              </div>
            ) : null}
          </section>
        )}

        {!file && (
          <>
            {/* Features */}
            <section className="section" id="features">
              <SectionHead
                eyebrow="Why ResMarke"
                title="Privacy you can actually trust"
                subtitle="No uploads. No account required. Just clean, sealed images in seconds."
              />
              <div className="features">
                <Feature
                  icon={<Lock size={20} aria-hidden="true" />}
                  title="Local & private"
                  body="Privacy-Max runs entirely in your browser. Your images are never uploaded or stored."
                />
                <Feature
                  icon={<ImageOff size={20} aria-hidden="true" />}
                  title="Metadata stripped"
                  body="EXIF, GPS, device, and software tags are removed, plus a clean re-encode of the pixels."
                />
                <Feature
                  icon={<Fingerprint size={20} aria-hidden="true" />}
                  title="Fibonacci-88 seal"
                  body="A subtle creator mark sealed into your export — yours, and recognizably so."
                />
              </div>
            </section>

            {/* How it works */}
            <section className="section" id="how">
              <SectionHead eyebrow="How it works" title="Three steps to a clean image" />
              <div className="steps">
                <Step
                  n={1}
                  title="Drop your image"
                  body="Add a JPG, PNG, or WebP. Everything happens locally — nothing is uploaded."
                />
                <Step
                  n={2}
                  title="Clean & seal"
                  body="We strip metadata, remove visible AI marks, and seal it with your Fibonacci-88 mark."
                />
                <Step
                  n={3}
                  title="Export your way"
                  body="Download in your original format and size, or pick a custom type and ratio."
                />
              </div>
            </section>

            {/* Remarkee Max promo */}
            <section className="section">
              <div className="promo">
                <span className="tag">
                  <Cpu size={11} aria-hidden="true" /> Remarkee Max · Beta
                </span>
                <h3>Go deeper with GPU regeneration</h3>
                <p>
                  For stubborn, deeply embedded watermarks, Remarkee Max runs an optional cloud GPU
                  pass that regenerates the image — far beyond what a browser can do. You only pay
                  after a job completes successfully.
                </p>
                <button className="btn btn-primary" type="button" onClick={openPicker}>
                  <Upload size={18} aria-hidden="true" /> Start with an image
                </button>
              </div>
            </section>

            {/* Pricing */}
            <section className="section" id="pricing">
              <SectionHead
                eyebrow="Pricing"
                title="Simple, creator-friendly pricing"
                subtitle="Start free. Upgrade only when you need more volume."
              />
              <div className="pricing">
                <Tier
                  name="Free"
                  price="$0"
                  period="forever"
                  features={["3 Privacy-Max exports", "Local, private processing", "Fibonacci-88 seal"]}
                  cta="Start free"
                  onClick={openPicker}
                />
                <Tier
                  name="Trial"
                  price="$1"
                  period="7 days"
                  features={["15 exports", "All output formats & sizes", "Everything in Free"]}
                  cta="Start trial"
                  onClick={openPicker}
                />
                <Tier
                  name="Pro"
                  price="$19.99"
                  period="month"
                  featured
                  features={[
                    "200 exports / month",
                    "Priority processing",
                    "All formats, sizes & ratios"
                  ]}
                  cta="Choose Pro"
                  onClick={openPicker}
                />
                <Tier
                  name="Pro+"
                  price="$29.99"
                  period="month"
                  features={[
                    "500 exports / month",
                    "Remarkee Max credits",
                    "Everything in Pro"
                  ]}
                  cta="Choose Pro+"
                  onClick={openPicker}
                />
              </div>
              <p className="pricing-note">
                Card payments via Airwallex are launching soon — start cleaning free today, no
                account required.
              </p>
            </section>

            {/* FAQ */}
            <section className="section" id="faq">
              <SectionHead eyebrow="FAQ" title="Questions, answered" />
              <div className="faq">
                <FaqItem
                  q="Are my images uploaded anywhere?"
                  a="No. Privacy-Max runs entirely in your browser — your images never leave your device. Remarkee Max is a separate, optional cloud feature you explicitly opt into."
                />
                <FaqItem
                  q="What exactly does ResMarke remove?"
                  a="All EXIF and metadata (GPS, device, software tags), via a clean pixel re-encode — plus optional removal of visible AI corner marks."
                />
                <FaqItem
                  q="What is the Fibonacci-88 seal?"
                  a="A subtle creator mark sealed into your export so your work is recognizably yours. It's a creator mark, not a claim of original provenance."
                />
                <FaqItem
                  q="Which formats and sizes can I export?"
                  a="JPG, PNG, or WebP — at your original dimensions, a square, or any custom width and height you set."
                />
                <FaqItem
                  q="What can I use it on?"
                  a="Use ResMarke only on images you own or control."
                />
              </div>
            </section>

            {/* Final CTA */}
            <section className="section">
              <div className="cta-band">
                <h2>Clean your first image — free</h2>
                <p>No account, no uploads. It runs right here in your browser.</p>
                <button className="btn btn-primary" type="button" onClick={openPicker}>
                  <Upload size={18} aria-hidden="true" /> Drop an image
                </button>
              </div>
            </section>
          </>
        )}
      </main>

      <input
        ref={fileInputRef}
        className="sr-only"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(event) => onFileSelected(event.target.files?.item(0) ?? null)}
      />

      <footer className="footer">
        <div className="footer-inner">
          <span>
            Use only on images you own or control. Fibonacci-88 is a creator mark, not proof of
            provenance.
          </span>
          <span>© {new Date().getFullYear()} ResMarke</span>
        </div>
      </footer>
    </div>
  );
}

function Dropzone({
  large = false,
  previewUrl,
  dragging,
  setDragging,
  onPick,
  onDropFile
}: {
  large?: boolean;
  previewUrl: string;
  dragging: boolean;
  setDragging: (next: boolean) => void;
  onPick: () => void;
  onDropFile: (file: File | null) => void;
}) {
  return (
    <div
      className={[
        "dropzone",
        large ? "large" : "",
        previewUrl ? "has-image" : "",
        dragging ? "dragging" : ""
      ]
        .filter(Boolean)
        .join(" ")}
      role="button"
      tabIndex={0}
      onClick={onPick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onPick();
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        onDropFile(event.dataTransfer.files.item(0));
      }}
    >
      {previewUrl ? (
        <img src={previewUrl} alt="Selected image preview" />
      ) : (
        <div className="dz-inner">
          <div className="dz-icon">
            <Upload size={26} aria-hidden="true" />
          </div>
          <div className="dz-title">Drop your image here</div>
          <div className="dz-sub">
            or <span className="dz-browse">browse files</span> · JPEG, PNG, WebP up to 25MB
          </div>
        </div>
      )}
    </div>
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

function Feature({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="feature">
      <div className="f-icon">{icon}</div>
      <h4>{title}</h4>
      <p>{body}</p>
    </div>
  );
}

function SectionHead({
  eyebrow,
  title,
  subtitle
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="section-head">
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
    </div>
  );
}

function Step({ n, title, body }: { n: number; title: string; body: string }) {
  return (
    <div className="step">
      <span className="step-n">{n}</span>
      <h4>{title}</h4>
      <p>{body}</p>
    </div>
  );
}

function Tier({
  name,
  price,
  period,
  features,
  cta,
  featured = false,
  onClick
}: {
  name: string;
  price: string;
  period: string;
  features: string[];
  cta: string;
  featured?: boolean;
  onClick: () => void;
}) {
  return (
    <div className={featured ? "tier featured" : "tier"}>
      {featured ? (
        <span className="tier-badge">
          <Sparkles size={12} aria-hidden="true" /> Most popular
        </span>
      ) : null}
      <div className="tier-name">{name}</div>
      <div className="tier-price">
        <strong>{price}</strong>
        <span>/ {period}</span>
      </div>
      <ul className="tier-features">
        {features.map((feature) => (
          <li key={feature}>
            <Check size={15} aria-hidden="true" /> {feature}
          </li>
        ))}
      </ul>
      <button
        className={featured ? "btn btn-primary btn-block" : "btn btn-ghost btn-block"}
        type="button"
        onClick={onClick}
      >
        {cta} <ArrowRight size={16} aria-hidden="true" />
      </button>
    </div>
  );
}

function FaqItem({ q, a }: { q: string; a: string }) {
  return (
    <details className="faq-item">
      <summary>
        {q}
        <ChevronDown className="chev" size={18} aria-hidden="true" />
      </summary>
      <p>{a}</p>
    </details>
  );
}
