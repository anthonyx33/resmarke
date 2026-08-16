import {
  Archive,
  ArrowRight,
  Check,
  ChevronDown,
  Download,
  Gauge,
  GripVertical,
  Images,
  Info,
  KeyRound,
  Loader2,
  LogOut,
  Mail,
  Maximize2,
  Moon,
  Play,
  Scan,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  UserRound,
  Wallet,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { config, hasSupabaseConfig } from "./lib/config";
import { readLocalCredits, spendLocalPrivacyCredit, type CreditSnapshot } from "./lib/localCredits";
import {
  cancelDeepCleanJob,
  createDeepCleanJob,
  dispatchDeepCleanJob,
  getDeepCleanJob,
  uploadDeepCleanInput,
  type CxRemintEngineMode,
  type DeepCleanJob
} from "./lib/deepcleanClient";
import { supabase } from "./lib/supabase";
import "./cmint.css";

/* ============================================================
   /CMINT — a focused console for exactly two engines:
     · DS ReMint V8.9 · Coherent Pro   (GPU remint, frozen)
     · Quality Finish · post-remint HD (CPU finisher, frozen)
   …plus the sequence that runs one into the other.

   No engine behaviour lives here. Every run goes through the
   same createDeepCleanJob payloads the existing pages use;
   this file is UI only.
   ============================================================ */

type PipelineMode = "sequence" | "remint" | "finish";
type Theme = "light" | "dark";
type AuthMode = "signin" | "signup" | "reset" | "update";
type CompareMode = "split" | "result" | "original";
type QueueStatus =
  | "ready"
  | "preparing"
  | "uploading"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

type QueueItem = {
  id: string;
  file: File;
  previewUrl: string;
  width?: number;
  height?: number;
  status: QueueStatus;
  job?: DeepCleanJob;
  error?: string;
};

type WashModel = "qwen" | "zimage" | "qwen+zimage";
type Strength = "light" | "balanced" | "deep";
type MetadataMode = "device" | "minimal";
type NameStyle = "photo-style" | "original" | "custom";
type QfPreset = "conservative" | "standard" | "strong";

const MAX_QUEUE = 20;
const MAX_BYTES = 25 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

/* Credit cost model — mirrors the existing Re-Mint Max pricing:
   V8.9 = 15 (+2 when the detector-gated adaptive engine runs),
   Quality Finish = 6 (CPU-only, no GPU wash). The sequence is a
   single job that performs both stages, so it bills the sum. */
const COST_REMINT = 15;
const COST_FINISH = 6;
const COST_ADAPTIVE = 2;

const PROFILE_FOR: Record<PipelineMode, "ds-remint-v8.9" | "quality-finish" | "ds-remint-v8.9-hd"> =
  {
    sequence: "ds-remint-v8.9-hd",
    remint: "ds-remint-v8.9",
    finish: "quality-finish"
  };

const WASH_LABEL: Record<WashModel, string> = {
  qwen: "Qwen",
  zimage: "Z-Image",
  "qwen+zimage": "Qwen ⊕ Z-Image"
};

const STRENGTH_HINT: Record<Strength, string> = {
  light:
    "Faintest optics, minimal noise, ~10% cleanup — for frames that already grade well.",
  balanced:
    "The recommended coherent model — paired inverse/forward CCM, MHC demosaic, SNR-coupled denoise, multiscale cleanup.",
  deep: "Legacy rescue: degrade 75% → low-res pass → restore. Only when Balanced cannot clear; it costs visible quality."
};

const QF_HINT: Record<QfPreset, string> = {
  conservative: "Lightest touch. Maximum fidelity to the naturalized frame, minimal cleanup.",
  standard: "The recommended finisher — compression cleanup, shadow-grain shrink, chroma repair, masked sharpen.",
  strong: "Hardest cleanup and sharpening. Watch the self-QC ringing and flatness readouts."
};

function initialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const saved = localStorage.getItem("resmarke:theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function CmintApp() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const seqRef = useRef(0);
  const queueRef = useRef<QueueItem[]>([]);

  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [activeId, setActiveId] = useState("");
  const [draggedId, setDraggedId] = useState("");
  const [dragging, setDragging] = useState(false);
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState("");
  const [notice, setNotice] = useState("");
  const [zipBusy, setZipBusy] = useState(false);
  const [downloadingId, setDownloadingId] = useState("");

  const [compare, setCompare] = useState<CompareMode>("split");
  const [splitPos, setSplitPos] = useState(50);
  const [pixelView, setPixelView] = useState(false);

  // Pipeline
  const [mode, setMode] = useState<PipelineMode>("sequence");

  // Stage 1 — DS ReMint V8.9 (identical option set to the frozen engine).
  const [washModel, setWashModel] = useState<WashModel>("qwen");
  const [strength, setStrength] = useState<Strength>("balanced");
  const [engineMode, setEngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [metadataMode, setMetadataMode] = useState<MetadataMode>("device");
  const [deviceExif, setDeviceExif] = useState(true);
  const [nameStyle, setNameStyle] = useState<NameStyle>("photo-style");
  const [nameCustom, setNameCustom] = useState("");

  // Stage 2 — Quality Finish.
  const [qfPreset, setQfPreset] = useState<QfPreset>("standard");
  const [qfScale, setQfScale] = useState(1.6);

  // Account
  const [credits, setCredits] = useState<CreditSnapshot>(() => readLocalCredits());
  const [userId, setUserId] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authStatus, setAuthStatus] = useState("");

  const runsRemint = mode !== "finish";
  const runsFinish = mode !== "remint";

  const unitCost = useMemo(() => {
    let cost = 0;
    if (runsRemint) cost += COST_REMINT + (engineMode === "adaptive" ? COST_ADAPTIVE : 0);
    if (runsFinish) cost += COST_FINISH;
    return cost;
  }, [runsRemint, runsFinish, engineMode]);

  const pending = queue.filter((item) => item.status !== "completed");
  const completed = queue.filter((item) => item.status === "completed" && item.job?.outputUrl);
  const totalCost = pending.length * unitCost;
  const active = queue.find((item) => item.id === activeId) ?? queue[0] ?? null;
  const activeBusy = Boolean(
    active && ["preparing", "uploading", "queued", "processing"].includes(active.status)
  );
  const resultUrl = active?.job?.status === "completed" ? active.job.outputUrl ?? "" : "";
  const canRun =
    pending.length > 0 &&
    !running &&
    !zipBusy &&
    (!hasSupabaseConfig || !!userId) &&
    credits.privacyCredits >= totalCost;

  const isAdmin =
    !!userEmail &&
    config.adminEmails.length > 0 &&
    config.adminEmails.includes(userEmail.toLowerCase());

  /* ---------------- effects ---------------- */

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("resmarke:theme", theme);
  }, [theme]);

  useEffect(() => {
    document.title = "/CMINT — Coherent Pro + Quality Finish";
  }, []);

  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  useEffect(() => {
    return () => queueRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
  }, []);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      const user = data.session?.user;
      setUserId(user?.id ?? "");
      setUserEmail(user?.email ?? "");
      if (user) void refreshCredits(user.id);
    });
    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      const user = session?.user;
      setUserId(user?.id ?? "");
      setUserEmail(user?.email ?? "");
      if (user) void refreshCredits(user.id);
      if (event === "PASSWORD_RECOVERY") {
        setAuthMode("update");
        setAuthStatus("Choose a new password for this account.");
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  async function refreshCredits(nextUserId: string) {
    if (!supabase) return;
    const { data, error } = await supabase
      .from("creator_profiles")
      .select("privacy_exports_remaining, deepclean_credits")
      .eq("user_id", nextUserId)
      .single();
    if (error) return;
    setCredits({
      privacyCredits: data.privacy_exports_remaining,
      deepCleanCredits: data.deepclean_credits,
      mode: "supabase"
    });
  }

  async function spendCredits(amount: number) {
    if (amount <= 0) return;
    if (!supabase || !userId) {
      let snapshot = readLocalCredits();
      for (let i = 0; i < amount; i++) snapshot = spendLocalPrivacyCredit();
      setCredits(snapshot);
      return;
    }
    const { data, error } = await supabase.functions.invoke("spend-privacy-credit", {
      body: { amount }
    });
    if (error) throw error;
    setCredits({
      privacyCredits: data.privacyCredits,
      deepCleanCredits: data.deepCleanCredits,
      mode: "supabase"
    });
  }

  /* ---------------- auth ---------------- */

  async function submitAuth() {
    if (!supabase) return;
    const email = authEmail.trim();

    if (authMode === "reset") {
      if (!email) return setAuthStatus("Enter your email to receive a reset link.");
      setAuthStatus("Sending reset link…");
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.href.split("#")[0]
      });
      setAuthStatus(error ? error.message : "Reset link sent. Check your email.");
      return;
    }
    if (!authPassword) return setAuthStatus("Enter your password.");
    if (authPassword.length < 6) return setAuthStatus("Password must be at least 6 characters.");

    if (authMode === "update") {
      setAuthStatus("Updating password…");
      const { error } = await supabase.auth.updateUser({ password: authPassword });
      setAuthStatus(error ? error.message : "Password updated.");
      if (!error) {
        setAuthPassword("");
        setAuthMode("signin");
      }
      return;
    }
    if (!email) return setAuthStatus("Enter your email.");

    setAuthStatus(authMode === "signin" ? "Signing in…" : "Creating account…");
    if (authMode === "signin") {
      const { error } = await supabase.auth.signInWithPassword({ email, password: authPassword });
      setAuthStatus(error ? error.message : "Signed in.");
      if (!error) setAuthPassword("");
      return;
    }
    const { data, error } = await supabase.auth.signUp({
      email,
      password: authPassword,
      options: { emailRedirectTo: window.location.href }
    });
    if (error) return setAuthStatus(error.message);
    if (data.session) {
      setAuthStatus("Account created. You are signed in.");
      setAuthPassword("");
      return;
    }
    setAuthStatus("Account created. Confirm via email before signing in.");
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUserId("");
    setUserEmail("");
    setCredits(readLocalCredits());
    setAuthStatus("Signed out.");
  }

  /* ---------------- queue ---------------- */

  function addFiles(files: File[]) {
    if (!files.length || running) return;
    setNotice("");

    const supported = files.filter(
      (candidate) => ACCEPTED.includes(candidate.type) && candidate.size <= MAX_BYTES
    );
    const rejected = files.length - supported.length;
    const slots = Math.max(0, MAX_QUEUE - queue.length);
    const accepted = supported.slice(0, slots);
    const overflow = supported.length - accepted.length;

    if (!accepted.length) {
      setNotice(
        slots === 0
          ? `Queue is full — remove an image first (max ${MAX_QUEUE}).`
          : "No supported images. Use JPEG, PNG or WebP up to 25 MB."
      );
      return;
    }

    const added: QueueItem[] = accepted.map((nextFile) => ({
      id: `img-${Date.now()}-${seqRef.current++}`,
      file: nextFile,
      previewUrl: URL.createObjectURL(nextFile),
      status: "ready"
    }));

    setQueue((current) => [...current, ...added]);
    if (!activeId) setActiveId(added[0].id);

    added.forEach((item) => {
      createImageBitmap(item.file)
        .then((bitmap) => {
          const dims = { width: bitmap.width, height: bitmap.height };
          bitmap.close();
          patchItem(item.id, dims);
        })
        .catch(() => undefined);
    });

    const notes = [
      rejected ? `${rejected} unsupported or oversized file${rejected === 1 ? "" : "s"} skipped.` : "",
      overflow ? `${overflow} left out to keep the ${MAX_QUEUE}-image limit.` : ""
    ].filter(Boolean);
    setNotice(notes.join(" "));
  }

  function patchItem(id: string, patch: Partial<QueueItem>) {
    setQueue((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  function removeItem(id: string) {
    if (running) return;
    const target = queue.find((item) => item.id === id);
    if (!target) return;
    URL.revokeObjectURL(target.previewUrl);
    const next = queue.filter((item) => item.id !== id);
    setQueue(next);
    if (activeId === id) setActiveId(next[0]?.id ?? "");
  }

  function moveItem(sourceId: string, targetId: string) {
    if (!sourceId || sourceId === targetId || running) return;
    setQueue((current) => {
      const from = current.findIndex((item) => item.id === sourceId);
      const to = current.findIndex((item) => item.id === targetId);
      if (from < 0 || to < 0) return current;
      const next = [...current];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  }

  function clearAll() {
    if (running || zipBusy) return;
    queue.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    setQueue([]);
    setActiveId("");
    setStatus("");
    setNotice("");
  }

  function openPicker() {
    fileInputRef.current?.click();
  }

  /* ---------------- run ---------------- */

  function remintOptions() {
    return {
      engineMode,
      washModel,
      strength,
      iphoneExif: deviceExif,
      metadataMode
    };
  }

  function finishOptions() {
    return {
      preset: qfPreset,
      // `null` is the native-size path the finisher already understands.
      scale: qfScale <= 1.001 ? null : Number(qfScale.toFixed(2))
    };
  }

  async function runQueue() {
    const items = queue.filter((item) => item.status !== "completed");
    if (!items.length) return setStatus("Add an image to the queue first.");
    if (hasSupabaseConfig && !userId) return setStatus("Sign in before running the queue.");
    if (credits.privacyCredits < items.length * unitCost) {
      return setStatus(`Not enough credits — this queue needs ${items.length * unitCost}.`);
    }

    const profile = PROFILE_FOR[mode];
    setRunning(true);
    setNotice("");
    let ok = 0;
    let failed = 0;

    for (const [index, item] of items.entries()) {
      let created: DeepCleanJob | null = null;
      setActiveId(item.id);
      patchItem(item.id, { status: "preparing", error: undefined, job: undefined });
      setStatus(`Preparing ${index + 1} of ${items.length} · ${item.file.name}`);

      try {
        const job = await createDeepCleanJob({
          file: item.file,
          creatorId: userEmail || "creator@example.com",
          profile,
          outputMode: "stripped",
          dsRemintV89: mode === "remint" ? remintOptions() : undefined,
          qualityFinish: mode === "finish" ? finishOptions() : undefined,
          dsRemintV89Hd:
            mode === "sequence"
              ? { remint: remintOptions(), finish: finishOptions() }
              : undefined,
          outputNameStyle: runsRemint ? nameStyle : undefined,
          outputNameCustom: runsRemint ? nameCustom : undefined
        });
        created = job;
        patchItem(item.id, { status: "uploading", job });

        setStatus(`Uploading ${index + 1} of ${items.length} privately…`);
        await uploadDeepCleanInput(job, item.file);

        patchItem(item.id, { status: "queued", job });
        setStatus(`Dispatching ${index + 1} of ${items.length}…`);
        await dispatchDeepCleanJob(job.id);
        await spendCredits(unitCost);

        patchItem(item.id, { status: "processing", job });
        const done = await waitForJob(job.id, item.id, index + 1, items.length);
        patchItem(item.id, { status: "completed", job: done, error: undefined });
        ok += 1;
      } catch (nextError) {
        const message =
          nextError instanceof Error ? nextError.message : "This image could not be processed.";
        if (created) await cancelDeepCleanJob(created.id).catch(() => undefined);
        patchItem(item.id, { status: "failed", job: created ?? undefined, error: message });
        setStatus(`${item.file.name}: ${message}`);
        failed += 1;
      }
    }

    setRunning(false);
    if (userId) await refreshCredits(userId);
    setStatus(
      failed
        ? `Finished · ${ok} completed · ${failed} failed. Failed images can be retried.`
        : `Complete · all ${ok} ${ok === 1 ? "image is" : "images are"} ready.`
    );
  }

  async function waitForJob(
    jobId: string,
    itemId: string,
    position: number,
    total: number
  ): Promise<DeepCleanJob> {
    for (;;) {
      const job = await getDeepCleanJob(jobId);
      if (job.status === "completed") return job;
      if (job.status === "failed") {
        throw new Error(job.failureReason || "The worker could not process this image.");
      }
      patchItem(itemId, { status: job.status === "queued" ? "queued" : "processing", job });
      setStatus(
        `Processing ${position} of ${total} · ${
          job.status === "queued" ? "waiting for a worker" : "pass in progress"
        }…`
      );
      await new Promise<void>((resolve) => window.setTimeout(resolve, 3500));
    }
  }

  /* ---------------- downloads ---------------- */

  function outputNameFor(item: QueueItem, position?: number) {
    const raw = item.file.name.replace(/\.[^.]+$/, "");
    const base = raw.replace(/[<>:"/\\|?*\u0000-\u001f\s]+/g, "-").slice(0, 90) || "image";
    const prefix = position === undefined ? "" : `${String(position + 1).padStart(2, "0")}-`;
    const suffix = mode === "finish" ? "finish" : mode === "remint" ? "remint" : "cmint";
    return `${prefix}${base}-${suffix}.jpg`;
  }

  function saveBlob(blob: Blob, name: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function freshJob(item: QueueItem) {
    if (!item.job?.id) throw new Error("This image has no completed job.");
    const job = await getDeepCleanJob(item.job.id);
    if (job.status !== "completed" || !job.outputUrl) throw new Error("Output is not ready yet.");
    patchItem(item.id, { job, status: "completed" });
    return job;
  }

  async function downloadItem(item: QueueItem) {
    if (downloadingId || zipBusy) return;
    setDownloadingId(item.id);
    setNotice("");
    try {
      const job = await freshJob(item);
      const response = await fetch(job.outputUrl as string);
      if (!response.ok) throw new Error("The secure download link could not be opened.");
      saveBlob(await response.blob(), outputNameFor(item));
    } catch (nextError) {
      setNotice(nextError instanceof Error ? nextError.message : "Download failed.");
    } finally {
      setDownloadingId("");
    }
  }

  async function downloadAll() {
    const done = queue.filter((item) => item.status === "completed" && item.job?.id);
    if (!done.length || zipBusy) return;
    setZipBusy(true);
    setNotice(`Preparing ${done.length} images…`);
    try {
      const files: Record<string, Uint8Array> = {};
      for (const [index, item] of done.entries()) {
        const job = await freshJob(item);
        const response = await fetch(job.outputUrl as string);
        if (!response.ok) throw new Error(`Could not download ${item.file.name}.`);
        files[outputNameFor(item, index)] = new Uint8Array(await response.arrayBuffer());
        setNotice(`Packaging ${index + 1} of ${done.length}…`);
      }
      const { zip } = await import("fflate");
      const zipped = await new Promise<Uint8Array>((resolve, reject) => {
        zip(files, { level: 0 }, (zipError, data) => (zipError ? reject(zipError) : resolve(data)));
      });
      const buffer = zipped.buffer.slice(
        zipped.byteOffset,
        zipped.byteOffset + zipped.byteLength
      ) as ArrayBuffer;
      saveBlob(new Blob([buffer], { type: "application/zip" }), "cmint-images.zip");
      setNotice(`${done.length} images downloaded as a ZIP.`);
    } catch (nextError) {
      setNotice(nextError instanceof Error ? nextError.message : "The ZIP could not be created.");
    } finally {
      setZipBusy(false);
    }
  }

  /* ---------------- render ---------------- */

  const showAuth = hasSupabaseConfig && (!userId || authMode === "update");
  const engineReport = active?.job?.report?.engine as Record<string, unknown> | undefined;
  const qfReport = readQfReport(engineReport);
  const rating = readRating88(active?.job?.report);

  return (
    <div className="cmint">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        onChange={(event) => {
          addFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />

      <div className="cm-shell">
        {/* ---------- topbar ---------- */}
        <header className="cm-top">
          <div className="cm-brand">
            <span className="cm-brand-mark">
              <Sparkles size={15} aria-hidden="true" />
            </span>
            <span className="cm-brand-text">
              <b>/CMINT</b>
              <span>Coherent Pro · Quality Finish</span>
            </span>
          </div>

          <div className="cm-chain" aria-label="Active pipeline">
            <span className={`cm-chain-node${runsRemint ? " is-on" : ""}`}>
              {runsRemint ? <Check size={11} aria-hidden="true" /> : null}
              V8.9 Coherent Pro
            </span>
            <span className="cm-chain-arrow" aria-hidden="true">
              <ArrowRight size={12} />
            </span>
            <span className={`cm-chain-node is-two${runsFinish ? " is-on" : ""}`}>
              {runsFinish ? <Check size={11} aria-hidden="true" /> : null}
              Quality Finish
            </span>
          </div>

          <span className="cm-top-spacer" />

          <div className="cm-top-right">
            <span className="cm-credits" title="Credit balance">
              <Wallet size={13} aria-hidden="true" />
              <b>{credits.privacyCredits}</b>
            </span>

            {showAuth ? (
              <details className="cm-pop" open={authMode === "update"}>
                <summary className="cm-pop-trigger">
                  <UserRound size={14} aria-hidden="true" /> Sign in
                </summary>
                <div className="cm-pop-panel">
                  {authMode !== "update" ? (
                    <div className="cm-seg">
                      <button
                        type="button"
                        className={authMode === "signin" ? "is-active" : ""}
                        onClick={() => {
                          setAuthMode("signin");
                          setAuthStatus("");
                        }}
                      >
                        Sign in
                      </button>
                      <button
                        type="button"
                        className={authMode === "signup" ? "is-active" : ""}
                        onClick={() => {
                          setAuthMode("signup");
                          setAuthStatus("");
                        }}
                      >
                        Sign up
                      </button>
                    </div>
                  ) : null}
                  {authMode !== "update" ? (
                    <div className="cm-input-icon">
                      <Mail size={14} aria-hidden="true" />
                      <input
                        className="cm-input"
                        type="email"
                        autoComplete="email"
                        placeholder="you@email.com"
                        value={authEmail}
                        onChange={(event) => setAuthEmail(event.target.value)}
                      />
                    </div>
                  ) : null}
                  {authMode !== "reset" ? (
                    <div className="cm-input-icon">
                      <KeyRound size={14} aria-hidden="true" />
                      <input
                        className="cm-input"
                        type="password"
                        autoComplete={authMode === "signin" ? "current-password" : "new-password"}
                        placeholder={authMode === "update" ? "New password" : "Password"}
                        value={authPassword}
                        onChange={(event) => setAuthPassword(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") void submitAuth();
                        }}
                      />
                    </div>
                  ) : null}
                  <button className="cm-btn cm-btn-primary cm-btn-block" type="button" onClick={submitAuth}>
                    {authMode === "signin"
                      ? "Sign in"
                      : authMode === "signup"
                        ? "Create account"
                        : authMode === "reset"
                          ? "Send reset link"
                          : "Update password"}
                  </button>
                  {authMode === "signin" ? (
                    <button
                      className="cm-link"
                      type="button"
                      onClick={() => {
                        setAuthMode("reset");
                        setAuthStatus("");
                      }}
                    >
                      Forgot password?
                    </button>
                  ) : authMode === "reset" ? (
                    <button
                      className="cm-link"
                      type="button"
                      onClick={() => {
                        setAuthMode("signin");
                        setAuthStatus("");
                      }}
                    >
                      Back to sign in
                    </button>
                  ) : null}
                  {authStatus ? <p className="cm-pop-status">{authStatus}</p> : null}
                </div>
              </details>
            ) : hasSupabaseConfig && userId ? (
              <details className="cm-pop">
                <summary className="cm-pop-trigger">
                  <UserRound size={14} aria-hidden="true" />
                  {userEmail || "Account"}
                </summary>
                <div className="cm-pop-panel">
                  <div className="cm-row">
                    <span>Credits</span>
                    <b>{credits.privacyCredits}</b>
                  </div>
                  <div className="cm-row">
                    <span>Re-Mint Max</span>
                    <b>{credits.deepCleanCredits}</b>
                  </div>
                  {isAdmin ? <span className="cm-tag is-on">Developer admin</span> : null}
                  <button className="cm-btn cm-btn-block" type="button" onClick={signOut}>
                    <LogOut size={14} aria-hidden="true" /> Sign out
                  </button>
                </div>
              </details>
            ) : null}

            <button
              className="cm-icon-btn"
              type="button"
              aria-label="Toggle theme"
              title={theme === "dark" ? "Switch to light" : "Switch to dark"}
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>
        </header>

        <div className="cm-work">
          {/* ---------- queue rail ---------- */}
          <section className="cm-pane cm-pane-queue" aria-label="Image queue">
            <div className="cm-rail-head">
              <span className="cm-rail-title">Queue</span>
              <span className="cm-count">
                {queue.length}/{MAX_QUEUE}
              </span>
              <span className="cm-top-spacer" />
              <button
                className="cm-btn cm-btn-sm"
                type="button"
                onClick={openPicker}
                disabled={running || queue.length >= MAX_QUEUE}
              >
                <Upload size={13} aria-hidden="true" /> Add
              </button>
            </div>

            <div className="cm-pane-scroll">
              <div
                className={`cm-drop${dragging ? " is-drag" : ""}`}
                role="button"
                tabIndex={0}
                onClick={openPicker}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") openPicker();
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  addFiles(Array.from(event.dataTransfer.files ?? []));
                }}
              >
                <Upload size={17} aria-hidden="true" />
                <b>Drop images</b>
                <span>JPEG · PNG · WebP · up to 25 MB each</span>
              </div>

              {queue.length ? (
                <div className="cm-queue">
                  {queue.map((item) => (
                    <div
                      key={item.id}
                      className={`cm-qitem${item.id === active?.id ? " is-active" : ""}${
                        item.id === draggedId ? " is-dragging" : ""
                      }`}
                      role="button"
                      tabIndex={0}
                      draggable={!running}
                      onClick={() => setActiveId(item.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") setActiveId(item.id);
                      }}
                      onDragStart={() => setDraggedId(item.id)}
                      onDragEnd={() => setDraggedId("")}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => {
                        event.preventDefault();
                        moveItem(draggedId, item.id);
                        setDraggedId("");
                      }}
                    >
                      <span className="cm-qthumb">
                        <img src={item.previewUrl} alt="" />
                      </span>
                      <span className="cm-qbody">
                        <span className="cm-qname">{item.file.name}</span>
                        <span className="cm-qmeta">
                          <i className={`cm-dot ${statusDotClass(item.status)}`} />
                          {statusLabel(item.status)}
                          {item.width ? ` · ${item.width}×${item.height}` : ""}
                        </span>
                      </span>
                      <span className="cm-qactions">
                        {item.status === "completed" ? (
                          <button
                            className="cm-qact"
                            type="button"
                            title="Download"
                            disabled={downloadingId === item.id}
                            onClick={(event) => {
                              event.stopPropagation();
                              void downloadItem(item);
                            }}
                          >
                            {downloadingId === item.id ? (
                              <Loader2 className="cm-spin" size={14} />
                            ) : (
                              <Download size={14} />
                            )}
                          </button>
                        ) : null}
                        <button
                          className="cm-qact is-danger"
                          type="button"
                          title="Remove"
                          disabled={running}
                          onClick={(event) => {
                            event.stopPropagation();
                            removeItem(item.id);
                          }}
                        >
                          <X size={14} />
                        </button>
                        <span className="cm-grip" aria-hidden="true">
                          <GripVertical size={13} />
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            {queue.length ? (
              <div className="cm-rail-foot">
                <button
                  className="cm-btn cm-btn-block"
                  type="button"
                  onClick={downloadAll}
                  disabled={!completed.length || zipBusy}
                >
                  {zipBusy ? (
                    <Loader2 className="cm-spin" size={14} />
                  ) : (
                    <Archive size={14} aria-hidden="true" />
                  )}
                  Download all ({completed.length})
                </button>
                <button
                  className="cm-btn cm-btn-block"
                  type="button"
                  onClick={clearAll}
                  disabled={running || zipBusy}
                >
                  <Trash2 size={14} aria-hidden="true" /> Clear queue
                </button>
              </div>
            ) : null}
          </section>

          {/* ---------- stage ---------- */}
          <section className="cm-pane cm-pane-stage" aria-label="Viewer">
            <div className="cm-stage-bar">
              {active ? (
                <div className="cm-stage-file">
                  <b>{active.file.name}</b>
                  <span>
                    {(active.file.size / 1_000_000).toFixed(2)} MB
                    {active.width ? ` · ${active.width}×${active.height}` : ""}
                  </span>
                </div>
              ) : (
                <span className="cm-rail-title">Viewer</span>
              )}

              <span className="cm-top-spacer" />

              {resultUrl ? (
                <div className="cm-seg" style={{ width: 210 }} role="radiogroup" aria-label="Compare mode">
                  {(["original", "split", "result"] as CompareMode[]).map((value) => (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={compare === value}
                      className={compare === value ? "is-active" : ""}
                      onClick={() => setCompare(value)}
                    >
                      {value === "original" ? "Original" : value === "split" ? "Split" : "Result"}
                    </button>
                  ))}
                </div>
              ) : null}

              <button
                className="cm-icon-btn"
                type="button"
                title={pixelView ? "Fit to view" : "View at 1:1 pixels"}
                aria-label="Toggle pixel view"
                disabled={!active}
                onClick={() => setPixelView((current) => !current)}
              >
                {pixelView ? <Scan size={15} /> : <Maximize2 size={15} />}
              </button>
            </div>

            <div className={`cm-stage-body${pixelView ? " is-pixel" : ""}`}>
              {!active ? (
                <div className="cm-empty">
                  <Images size={30} aria-hidden="true" />
                  <h2>Nothing loaded</h2>
                  <p>
                    Add images to the queue, pick a pipeline on the right, and run. Results appear
                    here with a split compare against the original.
                  </p>
                  <button className="cm-btn cm-btn-primary" type="button" onClick={openPicker}>
                    <Upload size={15} aria-hidden="true" /> Add images
                  </button>
                </div>
              ) : (
                <StageFrame
                  originalUrl={active.previewUrl}
                  resultUrl={resultUrl}
                  compare={compare}
                  splitPos={splitPos}
                  onSplit={setSplitPos}
                  busy={activeBusy}
                  busyLabel={statusLabel(active.status)}
                />
              )}
            </div>

            <div className="cm-stage-foot">
              {notice ? (
                <span style={{ color: "var(--cm-warn)" }}>{notice}</span>
              ) : active?.error ? (
                <span style={{ color: "var(--cm-danger)" }}>{active.error}</span>
              ) : (
                <span>
                  {status ||
                    (hasSupabaseConfig
                      ? "Ready. Pick a pipeline and run the queue."
                      : "Supabase env vars are not set — jobs cannot be dispatched.")}
                </span>
              )}
            </div>
          </section>

          {/* ---------- control rail ---------- */}
          <section className="cm-pane cm-pane-ctl" aria-label="Pipeline controls">
            <div className="cm-rail-head">
              <SlidersHorizontal size={13} aria-hidden="true" />
              <span className="cm-rail-title">Pipeline</span>
              <span className="cm-top-spacer" />
              <span className="cm-count">{unitCost} cr / image</span>
            </div>

            <div className="cm-pane-scroll">
              <div className="cm-ctl">
                {/* mode picker */}
                <div className="cm-modes" role="radiogroup" aria-label="Pipeline mode">
                  <ModeCard
                    active={mode === "sequence"}
                    disabled={running}
                    title="Sequence · V8.9 → Finish"
                    detail="One job: the frozen coherent remint, then the HD finisher over its delivered file."
                    cost={COST_REMINT + (engineMode === "adaptive" ? COST_ADAPTIVE : 0) + COST_FINISH}
                    onClick={() => setMode("sequence")}
                  />
                  <ModeCard
                    active={mode === "remint"}
                    disabled={running}
                    title="Re-Mint only · V8.9"
                    detail="Coherent Pro alone. Delivers the naturalized q92 file at ≤1250px."
                    cost={COST_REMINT + (engineMode === "adaptive" ? COST_ADAPTIVE : 0)}
                    onClick={() => setMode("remint")}
                  />
                  <ModeCard
                    active={mode === "finish"}
                    disabled={running}
                    title="Finish only · Quality Finish"
                    detail="Standalone pass over an already-naturalized JPEG. CPU-only, non-generative."
                    cost={COST_FINISH}
                    onClick={() => setMode("finish")}
                  />
                </div>

                {mode === "finish" ? (
                  <div className="cm-note">
                    <Info size={13} aria-hidden="true" />
                    <span>
                      Feed this an already re-minted file. Running it on a raw AI frame polishes the
                      pixels but does nothing for detector risk.
                    </span>
                  </div>
                ) : null}

                {/* ---- stage 1 ---- */}
                {runsRemint ? (
                  <div className="cm-card">
                    <div className="cm-card-head">
                      <span className="cm-card-num">1</span>
                      <span className="cm-card-title">
                        <b>DS ReMint V8.9 · Coherent Pro</b>
                        <span>Data-tuned coherent model · baseline routing</span>
                      </span>
                      <span className="cm-tag is-on">GPU</span>
                    </div>

                    <div className="cm-card-body">
                      <div className="cm-stats">
                        <Stat label="Wash" value={WASH_LABEL[washModel]} />
                        <Stat label="Camera" value={`${strength} model`} />
                        <Stat label="Resample" value="1× · ≤1250px" />
                        <Stat
                          label="Engine"
                          value={engineMode === "adaptive" ? "≤3 gated" : "1 pass"}
                        />
                      </div>

                      <div className="cm-field">
                        <span className="cm-label">Strength</span>
                        <div className="cm-seg" role="radiogroup" aria-label="V8.9 strength">
                          {(["light", "balanced", "deep"] as Strength[]).map((value) => (
                            <button
                              key={value}
                              type="button"
                              role="radio"
                              aria-checked={strength === value}
                              className={strength === value ? "is-active" : ""}
                              disabled={running}
                              onClick={() => setStrength(value)}
                            >
                              {value[0].toUpperCase() + value.slice(1)}
                            </button>
                          ))}
                        </div>
                        <p className="cm-hint">{STRENGTH_HINT[strength]}</p>
                      </div>

                      <div className="cm-field">
                        <span className="cm-label">Engine</span>
                        <div className="cm-seg" role="radiogroup" aria-label="V8.9 engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={engineMode === "adaptive"}
                            className={engineMode === "adaptive" ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setEngineMode("adaptive")}
                          >
                            Adaptive
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={engineMode === "template"}
                            className={engineMode === "template" ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setEngineMode("template")}
                          >
                            Template
                          </button>
                        </div>
                        <p className="cm-hint">
                          {engineMode === "adaptive"
                            ? `Strengths run lightest-first, each probed on the delivered bytes; the least destructive pass that clears ships. +${COST_ADAPTIVE} credits.`
                            : "One deterministic pass at the chosen strength. No detector calls."}
                        </p>
                      </div>
                    </div>

                    <details className="cm-disc">
                      <summary>
                        <SlidersHorizontal size={13} aria-hidden="true" /> Expert · wash, metadata,
                        naming
                        <ChevronDown className="cm-chev" size={14} aria-hidden="true" />
                      </summary>
                      <div className="cm-disc-body">
                        <div className="cm-field">
                          <span className="cm-label">Wash model</span>
                          <div className="cm-seg" role="radiogroup" aria-label="Wash model">
                            {(["qwen", "zimage", "qwen+zimage"] as WashModel[]).map((value) => (
                              <button
                                key={value}
                                type="button"
                                role="radio"
                                aria-checked={washModel === value}
                                className={washModel === value ? "is-active" : ""}
                                disabled={running}
                                onClick={() => setWashModel(value)}
                              >
                                {value === "qwen" ? "Qwen" : value === "zimage" ? "Z-Image" : "Both"}
                              </button>
                            ))}
                          </div>
                          <p className="cm-hint">
                            {washModel === "qwen"
                              ? "The proven SynthID breaker and the V8.9 live-test default."
                              : washModel === "zimage"
                                ? "Low-attribution family (~4–6% on graders). Re-verify SynthID removal before trusting it."
                                : "Both washes blended 50/50 — splits the source-attribution vote across families."}
                          </p>
                        </div>

                        <div className="cm-field">
                          <span className="cm-label">Metadata</span>
                          <select
                            className="cm-select"
                            value={metadataMode}
                            disabled={running}
                            onChange={(event) => setMetadataMode(event.target.value as MetadataMode)}
                          >
                            <option value="device">Device EXIF (coherent)</option>
                            <option value="minimal">Minimal (no EXIF)</option>
                          </select>
                        </div>

                        <label className="cm-switch">
                          <input
                            type="checkbox"
                            checked={deviceExif}
                            disabled={running}
                            onChange={(event) => setDeviceExif(event.target.checked)}
                          />
                          <span className="cm-switch-track" aria-hidden="true">
                            <span className="cm-switch-thumb" />
                          </span>
                          <span>Coherent device EXIF</span>
                        </label>

                        <div className="cm-field">
                          <span className="cm-label">Output filename</span>
                          <select
                            className="cm-select"
                            value={nameStyle}
                            disabled={running}
                            onChange={(event) => setNameStyle(event.target.value as NameStyle)}
                          >
                            <option value="photo-style">Photo style (IMG_####)</option>
                            <option value="original">Keep original name</option>
                            <option value="custom">Custom…</option>
                          </select>
                          {nameStyle === "custom" ? (
                            <input
                              className="cm-input"
                              value={nameCustom}
                              disabled={running}
                              placeholder="my-photo"
                              onChange={(event) => setNameCustom(event.target.value)}
                            />
                          ) : null}
                        </div>
                      </div>
                    </details>
                  </div>
                ) : null}

                {/* ---- stage 2 ---- */}
                {runsFinish ? (
                  <div className="cm-card">
                    <div className="cm-card-head">
                      <span className="cm-card-num is-two">{runsRemint ? "2" : "1"}</span>
                      <span className="cm-card-title">
                        <b>Quality Finish · post-remint HD</b>
                        <span>Non-AI selective restoration · grain kept, crispness restored</span>
                      </span>
                      <span className="cm-tag is-two">CPU</span>
                    </div>

                    <div className="cm-card-body">
                      <div className="cm-stats">
                        <Stat label="Preset" value={qfPreset} />
                        <Stat
                          label="Delivery"
                          value={qfScale <= 1.001 ? "native size" : `${qfScale.toFixed(2)}× HD`}
                        />
                        <Stat label="Encode" value="Q95 · 4:4:4 · 1×" />
                        <Stat label="Self-QC" value="ships input on fail" />
                      </div>

                      <div className="cm-field">
                        <span className="cm-label">Restoration strength</span>
                        <div className="cm-seg cm-seg-2" role="radiogroup" aria-label="Finish preset">
                          {(["conservative", "standard", "strong"] as QfPreset[]).map((value) => (
                            <button
                              key={value}
                              type="button"
                              role="radio"
                              aria-checked={qfPreset === value}
                              className={qfPreset === value ? "is-active" : ""}
                              disabled={running}
                              onClick={() => setQfPreset(value)}
                            >
                              {value[0].toUpperCase() + value.slice(1)}
                            </button>
                          ))}
                        </div>
                        <p className="cm-hint">{QF_HINT[qfPreset]}</p>
                      </div>

                      <div className="cm-field">
                        <span className="cm-label">Delivery size</span>
                        <div className="cm-seg cm-seg-2" role="radiogroup" aria-label="Delivery size">
                          {[
                            { value: 1, label: "Native" },
                            { value: 1.6, label: "1.6× HD" },
                            { value: 2, label: "2× Max" }
                          ].map((stop) => (
                            <button
                              key={stop.label}
                              type="button"
                              role="radio"
                              aria-checked={Math.abs(qfScale - stop.value) < 0.001}
                              className={Math.abs(qfScale - stop.value) < 0.001 ? "is-active" : ""}
                              disabled={running}
                              onClick={() => setQfScale(stop.value)}
                            >
                              {stop.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>

                    <details className="cm-disc">
                      <summary>
                        <Gauge size={13} aria-hidden="true" /> Expert · exact enlargement factor
                        <ChevronDown className="cm-chev" size={14} aria-hidden="true" />
                      </summary>
                      <div className="cm-disc-body">
                        <div className="cm-field">
                          <span className="cm-label">
                            Enlargement
                            <em>{qfScale <= 1.001 ? "native" : `${qfScale.toFixed(2)}×`}</em>
                          </span>
                          <input
                            className="cm-range"
                            type="range"
                            min={1}
                            max={2}
                            step={0.05}
                            value={qfScale}
                            disabled={running}
                            onChange={(event) => setQfScale(Number(event.target.value))}
                          />
                          <div className="cm-range-ends">
                            <span>Native (quality floor)</span>
                            <span>2× (~2500px)</span>
                          </div>
                          <p className="cm-hint">
                            The finisher accepts any factor from 1.00 to 2.00. Native delivery is
                            always the quality floor; enlargement is the HD path and adds perceived
                            resolution only when the finisher's self-QC passes.
                          </p>
                        </div>
                      </div>
                    </details>
                  </div>
                ) : null}

                {/* ---- result / QC ---- */}
                {active?.job?.status === "completed" ? (
                  <div className="cm-card">
                    <div className="cm-card-head">
                      <span className="cm-card-num">
                        <Check size={11} aria-hidden="true" />
                      </span>
                      <span className="cm-card-title">
                        <b>Result</b>
                        <span>{active.file.name}</span>
                      </span>
                    </div>
                    <div className="cm-card-body">
                      <div className="cm-stats">
                        <Stat
                          label="Runtime"
                          value={
                            active.job.runtimeMs
                              ? `${(active.job.runtimeMs / 1000).toFixed(1)}s`
                              : "—"
                          }
                        />
                        <Stat label="GPU" value={active.job.gpuType || "—"} />
                        {qfReport ? (
                          <>
                            <Stat
                              label="Finish"
                              value={qfReport.applied ? "applied" : "skipped (QC)"}
                            />
                            <Stat
                              label="Delivered"
                              value={
                                qfReport.outputWidth
                                  ? `${qfReport.outputWidth}×${qfReport.outputHeight}`
                                  : "—"
                              }
                            />
                          </>
                        ) : null}
                      </div>

                      {rating !== null ? (
                        <div
                          className={`cm-risk cm-risk-${
                            rating <= 29 ? "low" : rating <= 58 ? "mid" : "high"
                          }`}
                        >
                          AI-flag risk {rating}/88
                        </div>
                      ) : null}

                      {qfReport?.qc ? (
                        <div className="cm-qc">
                          <QcRow label="SSIM vs input" value={qfReport.qc.ssim} />
                          <QcRow label="Noise floor kept" value={qfReport.qc.noise_floor_ratio} />
                          <QcRow label="Ringing" value={qfReport.qc.ringing} />
                          <QcRow label="Flatness Δ" value={qfReport.qc.flatness_delta} />
                          <div className="cm-qc-row">
                            <span>Self-QC</span>
                            <b style={{ color: qfReport.applied ? "var(--cm-ok)" : "var(--cm-warn)" }}>
                              {qfReport.applied ? "passed" : "rejected — input shipped"}
                            </b>
                          </div>
                        </div>
                      ) : null}

                      <button
                        className="cm-btn cm-btn-primary cm-btn-block"
                        type="button"
                        disabled={downloadingId === active.id}
                        onClick={() => void downloadItem(active)}
                      >
                        {downloadingId === active.id ? (
                          <Loader2 className="cm-spin" size={15} />
                        ) : (
                          <Download size={15} aria-hidden="true" />
                        )}
                        Download this image
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>

            {/* ---- run bar ---- */}
            <div className="cm-run">
              {hasSupabaseConfig && !userId ? (
                <div className="cm-note is-warn">
                  <Info size={13} aria-hidden="true" />
                  <span>Sign in to dispatch jobs.</span>
                </div>
              ) : pending.length > 0 && credits.privacyCredits < totalCost ? (
                <div className="cm-note is-warn">
                  <Info size={13} aria-hidden="true" />
                  <span>
                    This queue needs {totalCost} credits; you have {credits.privacyCredits}.
                  </span>
                </div>
              ) : null}

              <div className="cm-run-meta">
                <span>
                  {pending.length} pending · {completed.length} done
                </span>
                <b>{totalCost} credits</b>
              </div>

              <button
                className="cm-btn cm-btn-primary cm-btn-lg cm-btn-block"
                type="button"
                onClick={runQueue}
                disabled={!canRun}
              >
                {running ? (
                  <>
                    <Loader2 className="cm-spin" size={16} /> Processing…
                  </>
                ) : (
                  <>
                    <Play size={16} aria-hidden="true" />
                    {pending.some((item) => item.status === "failed")
                      ? "Retry unfinished"
                      : `Run ${pending.length} ${pending.length === 1 ? "image" : "images"}`}
                  </>
                )}
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Sub-components
   ============================================================ */

function StageFrame({
  originalUrl,
  resultUrl,
  compare,
  splitPos,
  onSplit,
  busy,
  busyLabel
}: {
  originalUrl: string;
  resultUrl: string;
  compare: CompareMode;
  splitPos: number;
  onSplit: (value: number) => void;
  busy: boolean;
  busyLabel: string;
}) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);

  function positionFrom(clientX: number) {
    const box = frameRef.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    onSplit(Math.max(0, Math.min(100, ((clientX - box.left) / box.width) * 100)));
  }

  const split = Boolean(resultUrl) && compare === "split";
  const showResult = Boolean(resultUrl) && compare !== "original";

  return (
    <div
      ref={frameRef}
      className={`cm-frame${split ? " cm-compare" : ""}`}
      onPointerDown={
        split
          ? (event) => {
              draggingRef.current = true;
              event.currentTarget.setPointerCapture(event.pointerId);
              positionFrom(event.clientX);
            }
          : undefined
      }
      onPointerMove={
        split
          ? (event) => {
              if (draggingRef.current) positionFrom(event.clientX);
            }
          : undefined
      }
      onPointerUp={
        split
          ? (event) => {
              draggingRef.current = false;
              event.currentTarget.releasePointerCapture(event.pointerId);
            }
          : undefined
      }
    >
      {/* Base layer: the original when splitting or showing the original,
          otherwise the result on its own (so native size is honoured). */}
      <img
        src={split || !showResult ? originalUrl : resultUrl}
        alt={split || !showResult ? "Original image" : "Processed result"}
        draggable={false}
      />

      {split ? (
        <>
          <div className="cm-split-top" style={{ clipPath: `inset(0 0 0 ${splitPos}%)` }}>
            <img src={resultUrl} alt="Processed result" draggable={false} />
          </div>
          <div className="cm-split-handle" style={{ left: `${splitPos}%` }}>
            <span className="cm-split-knob">
              <GripVertical size={14} aria-hidden="true" />
            </span>
          </div>
          <span className="cm-split-tag is-left">Original</span>
          <span className="cm-split-tag is-right">Processed</span>
        </>
      ) : null}

      {busy ? (
        <div className="cm-veil">
          <Loader2 className="cm-spin" size={26} aria-hidden="true" />
          <span>{busyLabel}</span>
        </div>
      ) : null}
    </div>
  );
}

function ModeCard({
  active,
  disabled,
  title,
  detail,
  cost,
  onClick
}: {
  active: boolean;
  disabled: boolean;
  title: string;
  detail: string;
  cost: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      className={`cm-mode${active ? " is-active" : ""}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="cm-mode-radio" aria-hidden="true" />
      <span className="cm-mode-text">
        <b>{title}</b>
        <span>{detail}</span>
      </span>
      <span className="cm-cost">{cost} cr</span>
    </button>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span className="cm-stat">
      <em>{label}</em>
      <b>{value}</b>
    </span>
  );
}

function QcRow({ label, value }: { label: string; value: number | undefined }) {
  if (typeof value !== "number") return null;
  return (
    <div className="cm-qc-row">
      <span>{label}</span>
      <b>{value.toFixed(3)}</b>
    </div>
  );
}

/* ============================================================
   Report readers
   ============================================================ */

type QfView = {
  applied: boolean;
  outputWidth?: number;
  outputHeight?: number;
  qc?: {
    ssim?: number;
    noise_floor_ratio?: number;
    ringing?: number;
    flatness_delta?: number;
  };
};

function readQfReport(engine: Record<string, unknown> | undefined): QfView | null {
  if (!engine) return null;
  // The sequence nests the finisher report under `quality_finish`; a
  // standalone finish puts it at the engine root. Probe both rather than
  // trusting the currently-selected mode — the job may have run under a
  // different one.
  const nested = engine.quality_finish;
  const raw = isQfShape(nested)
    ? (nested as Record<string, unknown>)
    : isQfShape(engine)
      ? engine
      : undefined;
  if (!raw) return null;
  const qc = raw.qc as Record<string, unknown> | undefined;
  return {
    applied: raw.applied === true,
    outputWidth: numberOr(raw.output_width),
    outputHeight: numberOr(raw.output_height),
    qc: qc
      ? {
          ssim: numberOr(qc.ssim),
          noise_floor_ratio: numberOr(qc.noise_floor_ratio),
          ringing: numberOr(qc.ringing),
          flatness_delta: numberOr(qc.flatness_delta)
        }
      : undefined
  };
}

function isQfShape(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as Record<string, unknown>).mode === "quality-finish"
  );
}

function numberOr(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function readRating88(report: Record<string, unknown> | undefined): number | null {
  if (!report) return null;
  const engine = report.engine;
  const candidates = [
    engine && typeof engine === "object"
      ? (engine as Record<string, unknown>).rating_88
      : undefined,
    report.rating_88
  ];
  for (const value of candidates) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Math.max(0, Math.min(88, Math.round(value)));
    }
  }
  return null;
}

/* ============================================================
   Status helpers
   ============================================================ */

function statusLabel(status: QueueStatus): string {
  switch (status) {
    case "ready":
      return "Ready";
    case "preparing":
      return "Preparing…";
    case "uploading":
      return "Uploading…";
    case "queued":
      return "Waiting for a worker…";
    case "processing":
      return "Processing…";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
  }
}

function statusDotClass(status: QueueStatus): string {
  if (status === "completed") return "is-done";
  if (status === "failed") return "is-fail";
  if (status === "ready") return "";
  return "is-run";
}
