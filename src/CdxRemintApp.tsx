import {
  Archive,
  ArrowRight,
  Check,
  ChevronDown,
  Download,
  GripVertical,
  Image as ImageIcon,
  KeyRound,
  LoaderCircle,
  LogOut,
  Mail,
  Menu,
  Moon,
  Play,
  RefreshCw,
  RotateCcw,
  Settings2,
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
import {
  cancelDeepCleanJob,
  createDeepCleanJob,
  dispatchDeepCleanJob,
  getDeepCleanJob,
  uploadDeepCleanInput,
  type CxRemintEngineMode,
  type DeepCleanJob,
  type DsRemintV8_8Options,
  type DsRemintV8_9HdOptions,
  type QualityFinishOptions
} from "./lib/deepcleanClient";
import {
  readLocalCredits,
  spendLocalPrivacyCredit,
  type CreditSnapshot
} from "./lib/localCredits";
import { buildSettingsCode } from "./lib/settingsCode";
import { supabase } from "./lib/supabase";
import "./cdx-remint.css";

type PipelineMode = "sequence" | "remint" | "finish";
type Theme = "light" | "dark";
type AuthMode = "signin" | "signup" | "reset" | "update";
type QueueStatus =
  | "ready"
  | "preparing"
  | "uploading"
  | "queued"
  | "processing"
  | "completed"
  | "failed";
type WashModel = "qwen" | "zimage" | "qwen+zimage";
type Strength = "light" | "balanced" | "deep";
type MetadataMode = "device" | "minimal";
type NameStyle = "photo-style" | "original" | "custom" | "settings-code";
type QfPreset = "conservative" | "standard" | "strong" | "fidelity";
type FinishRouting = "adaptive" | "template";

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

const MAX_QUEUE = 20;
const MAX_BYTES = 25 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const COST_REMINT = 15;
const COST_ADAPTIVE = 2;
const COST_FINISH = 6;

const PROFILE_FOR: Record<
  PipelineMode,
  "ds-remint-v8.9" | "quality-finish" | "ds-remint-v8.9-hd"
> = {
  sequence: "ds-remint-v8.9-hd",
  remint: "ds-remint-v8.9",
  finish: "quality-finish"
};

function initialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const saved = localStorage.getItem("resmarke:theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function CdxRemintApp() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const sequenceRef = useRef(0);
  const queueRef = useRef<QueueItem[]>([]);

  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [activeId, setActiveId] = useState("");
  const [draggedId, setDraggedId] = useState("");
  const [dropActive, setDropActive] = useState(false);
  const [running, setRunning] = useState(false);
  const [zipBusy, setZipBusy] = useState(false);
  const [downloadingId, setDownloadingId] = useState("");
  const [status, setStatus] = useState("");
  const [notice, setNotice] = useState("");
  const [resultsOpen, setResultsOpen] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  // Config A · Proven is the exact first-load state.
  const [mode, setMode] = useState<PipelineMode>("sequence");
  const [washModel, setWashModel] = useState<WashModel>("qwen");
  const [strength, setStrength] = useState<Strength>("deep");
  const [engineMode, setEngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [metadataMode, setMetadataMode] = useState<MetadataMode>("device");
  const [iphoneExif, setIphoneExif] = useState(true);
  const [qfPreset, setQfPreset] = useState<QfPreset>("strong");
  const [qfScale, setQfScale] = useState(1);
  const [wallClean, setWallClean] = useState(true);
  const [finishMode, setFinishMode] = useState<FinishRouting>("adaptive");
  const [tuneDither, setTuneDither] = useState(1);
  const [tuneSmooth, setTuneSmooth] = useState(1.25);
  const [tuneSharpen, setTuneSharpen] = useState(1);
  const [nameStyle, setNameStyle] = useState<NameStyle>("settings-code");
  const [nameCustom, setNameCustom] = useState("");

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
  }, [engineMode, runsFinish, runsRemint]);

  const pending = queue.filter((item) => item.status !== "completed");
  const completed = queue.filter((item) => item.status === "completed" && item.job?.outputUrl);
  const totalCost = pending.length * unitCost;
  const active = queue.find((item) => item.id === activeId) ?? queue[0] ?? null;
  const activeReport = active?.job?.report;
  const activeResultUrl =
    active?.status === "completed" && active.job?.outputUrl ? active.job.outputUrl : "";
  const engineReport = activeReport?.engine as Record<string, unknown> | undefined;
  const qfReport = readQfReport(engineReport);
  const rating = readRating88(activeReport);
  const canRun =
    pending.length > 0 &&
    !running &&
    !zipBusy &&
    (!hasSupabaseConfig || Boolean(userId)) &&
    credits.privacyCredits >= totalCost;

  const remintOptions: DsRemintV8_8Options = {
    engineMode,
    washModel,
    strength,
    iphoneExif,
    metadataMode
  };
  const finishOptions: QualityFinishOptions = {
    preset: qfPreset,
    scale: qfScale <= 1.001 ? null : Number(qfScale.toFixed(2)),
    overrides: {
      dither: tuneDither,
      smoothness: tuneSmooth,
      sharpen: tuneSharpen
    },
    materialClean: wallClean
  };
  const settingsCode = buildSettingsCode({
    mode,
    remint: remintOptions,
    finish: { ...finishOptions, finishMode }
  });
  const configAActive =
    mode === "sequence" &&
    washModel === "qwen" &&
    strength === "deep" &&
    engineMode === "adaptive" &&
    qfPreset === "strong" &&
    qfScale <= 1.001 &&
    Math.abs(tuneDither - 1) < 0.001 &&
    Math.abs(tuneSmooth - 1.25) < 0.001 &&
    Math.abs(tuneSharpen - 1) < 0.001 &&
    wallClean &&
    finishMode === "adaptive";

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("resmarke:theme", theme);
  }, [theme]);

  useEffect(() => {
    document.title = "/CDX-REMINT — Remint Console";
  }, []);

  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  useEffect(() => {
    return () => {
      queueRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    };
  }, []);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
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
        setDrawerOpen(true);
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
      for (let index = 0; index < amount; index += 1) {
        snapshot = spendLocalPrivacyCredit();
      }
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
    setAuthStatus(
      data.session
        ? "Account created. You are signed in."
        : "Account created. Confirm via email before signing in."
    );
    if (data.session) setAuthPassword("");
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUserId("");
    setUserEmail("");
    setCredits(readLocalCredits());
    setAuthStatus("Signed out.");
  }

  function patchItem(id: string, patch: Partial<QueueItem>) {
    setQueue((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item))
    );
  }

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

    const added: QueueItem[] = accepted.map((file) => ({
      id: `rx-${Date.now()}-${sequenceRef.current++}`,
      file,
      previewUrl: URL.createObjectURL(file),
      status: "ready"
    }));
    setQueue((current) => [...current, ...added]);
    if (!activeId) setActiveId(added[0].id);

    added.forEach((item) => {
      createImageBitmap(item.file)
        .then((bitmap) => {
          patchItem(item.id, { width: bitmap.width, height: bitmap.height });
          bitmap.close();
        })
        .catch(() => undefined);
    });

    const messages = [
      rejected ? `${rejected} unsupported or oversized file${rejected === 1 ? "" : "s"} skipped.` : "",
      overflow ? `${overflow} left out to keep the ${MAX_QUEUE}-image limit.` : ""
    ].filter(Boolean);
    setNotice(messages.join(" "));
  }

  function removeItem(id: string) {
    if (running) return;
    const target = queue.find((item) => item.id === id);
    if (!target) return;
    URL.revokeObjectURL(target.previewUrl);
    const next = queue.filter((item) => item.id !== id);
    setQueue(next);
    if (activeId === id) {
      setActiveId(next[0]?.id ?? "");
      setResultsOpen(false);
      setShowOriginal(false);
    }
  }

  function clearQueue() {
    if (running || zipBusy) return;
    queue.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    setQueue([]);
    setActiveId("");
    setStatus("");
    setNotice("");
    setResultsOpen(false);
    setShowOriginal(false);
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

  function resetConfigA() {
    setMode("sequence");
    setWashModel("qwen");
    setStrength("deep");
    setEngineMode("adaptive");
    setQfPreset("strong");
    setQfScale(1);
    setTuneDither(1);
    setTuneSmooth(1.25);
    setTuneSharpen(1);
    setWallClean(true);
    setFinishMode("adaptive");
  }

  function deliveredNameFor(position: number) {
    if (!runsRemint) return { style: nameStyle, custom: nameCustom };
    if (nameStyle === "custom") {
      const base = nameCustom.trim() || "image";
      return { style: "custom" as const, custom: position > 1 ? `${base}-${position}` : base };
    }
    if (nameStyle === "settings-code") {
      return {
        style: "settings-code" as const,
        custom: position > 1 ? `${settingsCode}-${position}` : settingsCode
      };
    }
    return { style: nameStyle, custom: nameCustom };
  }

  async function processItem(item: QueueItem, position: number, total: number) {
    let created: DeepCleanJob | null = null;
    setActiveId(item.id);
    setResultsOpen(false);
    setShowOriginal(false);
    patchItem(item.id, { status: "preparing", error: undefined, job: undefined });
    setStatus(`Preparing ${position} of ${total} · ${item.file.name}`);
    try {
      const naming = deliveredNameFor(position);
      const sequenceOptions: DsRemintV8_9HdOptions = {
        remint: remintOptions,
        finish: finishOptions,
        finishMode
      };
      const job = await createDeepCleanJob({
        file: item.file,
        creatorId: userEmail || "creator@example.com",
        profile: PROFILE_FOR[mode],
        outputMode: "stripped",
        dsRemintV89: mode === "remint" ? remintOptions : undefined,
        qualityFinish: mode === "finish" ? finishOptions : undefined,
        dsRemintV89Hd: mode === "sequence" ? sequenceOptions : undefined,
        outputNameStyle: naming.style,
        outputNameCustom: naming.custom
      });
      created = job;
      patchItem(item.id, { status: "uploading", job });
      setStatus(`Uploading ${position} of ${total} privately…`);
      await uploadDeepCleanInput(job, item.file);
      patchItem(item.id, { status: "queued", job });
      setStatus(`Dispatching ${position} of ${total}…`);
      await dispatchDeepCleanJob(job.id);
      await spendCredits(unitCost);
      patchItem(item.id, { status: "processing", job });
      const done = await waitForJob(job.id, item.id, position, total);
      patchItem(item.id, { status: "completed", job: done, error: undefined });
    } catch (error) {
      const message = error instanceof Error ? error.message : "This image could not be processed.";
      if (created) await cancelDeepCleanJob(created.id).catch(() => undefined);
      patchItem(item.id, { status: "failed", job: created ?? undefined, error: message });
      setStatus(`${item.file.name}: ${message}`);
      throw error;
    }
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

  async function processBatch(items: QueueItem[], completionLabel: string) {
    if (running || zipBusy) return;
    if (!items.length) return setStatus("Add an image to the queue first.");
    if (hasSupabaseConfig && !userId) return setStatus("Sign in before processing images.");
    const required = items.length * unitCost;
    if (credits.privacyCredits < required) {
      return setStatus(`Not enough credits — this action needs ${required}.`);
    }
    setRunning(true);
    setNotice("");
    let completeCount = 0;
    let failedCount = 0;
    for (const [index, item] of items.entries()) {
      try {
        await processItem(item, index + 1, items.length);
        completeCount += 1;
      } catch {
        failedCount += 1;
      }
    }
    setRunning(false);
    if (userId) await refreshCredits(userId);
    setStatus(
      failedCount
        ? `Finished · ${completeCount} completed · ${failedCount} failed.`
        : `${completionLabel} · ${completeCount} ${completeCount === 1 ? "image" : "images"} ready.`
    );
  }

  async function rerunItem(item: QueueItem) {
    if (running || zipBusy) return;
    await processBatch([item], "Re-run complete");
  }

  function outputNameFor(item: QueueItem, position?: number) {
    const suffix = position && position > 1 ? `-${position}` : "";
    if (nameStyle === "custom") return `${nameCustom.trim() || "image"}${suffix}.jpg`;
    if (nameStyle === "settings-code") return `${settingsCode}${suffix}.jpg`;
    const raw = item.file.name.replace(/\.[^.]+$/, "");
    const base = raw.replace(/[<>:"/\\|?*\u0000-\u001f\s]+/g, "-").slice(0, 90) || "image";
    const prefix = position ? `${String(position).padStart(2, "0")}-` : "";
    const segment = mode === "finish" ? "finish" : mode === "remint" ? "remint" : "cdx-remint";
    return `${prefix}${base}-${segment}.jpg`;
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
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Download failed.");
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
        files[outputNameFor(item, index + 1)] = new Uint8Array(await response.arrayBuffer());
        setNotice(`Packaging ${index + 1} of ${done.length}…`);
      }
      const { zip } = await import("fflate");
      const zipped = await new Promise<Uint8Array>((resolve, reject) => {
        zip(files, { level: 0 }, (error, data) => (error ? reject(error) : resolve(data)));
      });
      const buffer = zipped.buffer.slice(
        zipped.byteOffset,
        zipped.byteOffset + zipped.byteLength
      ) as ArrayBuffer;
      saveBlob(new Blob([buffer], { type: "application/zip" }), "remint-images.zip");
      setNotice(`${done.length} images downloaded as a ZIP.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "The ZIP could not be created.");
    } finally {
      setZipBusy(false);
    }
  }

  const showAuth = hasSupabaseConfig && (!userId || authMode === "update");
  const isAdmin =
    Boolean(userEmail) && config.adminEmails.includes(userEmail.toLowerCase());

  return (
    <div className="remint">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        onChange={(event) => {
          addFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />

      <div className="rx-shell">
        <header className="rx-topbar">
          <div className="rx-brand">
            <span className="rx-brand-mark" aria-hidden="true">
              <Sparkles size={15} strokeWidth={1.6} />
            </span>
            <span className="rx-brand-copy">
              <b>CDX-REMINT</b>
              <span>Image restoration console</span>
            </span>
          </div>
          <div className="rx-pipeline-chain" aria-label="Active pipeline">
            <span className={runsRemint ? "is-active" : ""}>
              {runsRemint ? <Check size={11} /> : null} Remint
            </span>
            <ArrowRight size={12} aria-hidden="true" />
            <span className={runsFinish ? "is-active" : ""}>
              {runsFinish ? <Check size={11} /> : null} Quality Finish
            </span>
          </div>
          <span className="rx-top-spacer" />
          <span className={`rx-proven${configAActive ? " is-active" : ""}`}>
            {configAActive ? <Check size={12} aria-hidden="true" /> : null}
            Config A · Proven
          </span>
          <button
            className="rx-icon-button"
            type="button"
            aria-label="Open settings"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <Menu size={19} strokeWidth={1.6} />
          </button>
        </header>

        <main className="rx-main">
          <section className="rx-card rx-queue-card" aria-labelledby="rx-queue-title">
            <div className="rx-queue-head">
              <span>
                <b>Queue</b>
                <small>{queue.length}/{MAX_QUEUE}</small>
              </span>
              <button
                className="rx-button rx-button-subtle"
                type="button"
                disabled={running || queue.length >= MAX_QUEUE}
                onClick={() => inputRef.current?.click()}
              >
                <Upload size={13} /> Add
              </button>
            </div>

            <div
              className={`rx-rail-drop${dropActive ? " is-active" : ""}`}
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setDropActive(true);
              }}
              onDragLeave={() => setDropActive(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDropActive(false);
                addFiles(Array.from(event.dataTransfer.files ?? []));
              }}
            >
              <Upload size={16} aria-hidden="true" />
              <span><b>Drop images</b><small>JPEG · PNG · WebP · 25 MB</small></span>
            </div>

            <div className="rx-section-head rx-studio-head">
              <div>
                <span className="rx-eyebrow">Workspace</span>
                <h1 id="rx-queue-title">{active ? active.file.name : "New Remint"}</h1>
              </div>
              <div className="rx-studio-actions">
                <span className="rx-count">{queue.length} / {MAX_QUEUE}</span>
                <button
                  className="rx-button rx-button-subtle"
                  type="button"
                  disabled={running || queue.length >= MAX_QUEUE}
                  onClick={() => inputRef.current?.click()}
                >
                  <Upload size={14} /> Add images
                </button>
              </div>
            </div>

            {active ? (
              <div
                className={`rx-canvas${dropActive ? " is-drop" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDropActive(true);
                }}
                onDragLeave={() => setDropActive(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDropActive(false);
                  addFiles(Array.from(event.dataTransfer.files ?? []));
                }}
              >
                <div className="rx-canvas-bar">
                  <span className={`rx-canvas-status ${statusDotClass(active.status)}`}>
                    <i /> {statusLabel(active.status)}
                  </span>
                  <span className="rx-canvas-meta">
                    {(active.file.size / 1_000_000).toFixed(2)} MB
                    {active.width ? ` · ${active.width}×${active.height}` : ""}
                  </span>
                  <span className="rx-top-spacer" />
                  {activeResultUrl ? (
                    <div className="rx-view-toggle" role="radiogroup" aria-label="Canvas view">
                      <button
                        type="button"
                        role="radio"
                        aria-checked={showOriginal}
                        className={showOriginal ? "is-active" : ""}
                        onClick={() => setShowOriginal(true)}
                      >
                        Original
                      </button>
                      <button
                        type="button"
                        role="radio"
                        aria-checked={!showOriginal}
                        className={!showOriginal ? "is-active" : ""}
                        onClick={() => setShowOriginal(false)}
                      >
                        Result
                      </button>
                    </div>
                  ) : null}
                </div>
                <div className="rx-canvas-image">
                  <img
                    src={showOriginal || !activeResultUrl ? active.previewUrl : activeResultUrl}
                    alt={showOriginal || !activeResultUrl ? active.file.name : `Processed ${active.file.name}`}
                  />
                  {["preparing", "uploading", "queued", "processing"].includes(active.status) ? (
                    <div className="rx-canvas-veil">
                      <LoaderCircle className="rx-spin" size={25} />
                      <span>{statusLabel(active.status)}</span>
                    </div>
                  ) : null}
                  {dropActive ? <div className="rx-canvas-drop"><Upload size={22} /> Drop to add</div> : null}
                </div>
              </div>
            ) : (
              <div
                className={`rx-dropzone${dropActive ? " is-active" : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => inputRef.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDropActive(true);
                }}
                onDragLeave={() => setDropActive(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDropActive(false);
                  addFiles(Array.from(event.dataTransfer.files ?? []));
                }}
              >
                <span className="rx-drop-orbit" aria-hidden="true">
                  <span className="rx-drop-icon"><Upload size={23} strokeWidth={1.4} /></span>
                </span>
                <span className="rx-drop-copy">
                  <b>Begin with an image</b>
                  <small>Drop JPEG, PNG or WebP here · up to 25 MB</small>
                </span>
                <span className="rx-add-label">Choose images</span>
              </div>
            )}

            <div className="rx-viewer-status" aria-live="polite">
              {notice ? (
                <span className="is-warning">{notice}</span>
              ) : active?.error ? (
                <span className="is-error">{active.error}</span>
              ) : (
                <span>{status || (hasSupabaseConfig ? "Ready to process." : "Supabase environment variables are required to dispatch jobs.")}</span>
              )}
            </div>

            {queue.length ? (
              <div className="rx-queue" aria-label="Queued images">
                {queue.map((item, index) => (
                  <article
                    key={item.id}
                    className={`rx-queue-item${active?.id === item.id ? " is-selected" : ""}${
                      draggedId === item.id ? " is-dragging" : ""
                    }`}
                    draggable={!running}
                    onClick={() => {
                      setActiveId(item.id);
                      setResultsOpen(false);
                      setShowOriginal(false);
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
                    <span className="rx-order">{String(index + 1).padStart(2, "0")}</span>
                    <img className="rx-thumb" src={item.previewUrl} alt="" />
                    <span className="rx-item-copy">
                      <b>{item.file.name}</b>
                      <small>
                        <i className={`rx-status-dot ${statusDotClass(item.status)}`} />
                        {statusLabel(item.status)}
                        {item.width ? ` · ${item.width}×${item.height}` : ""}
                      </small>
                      {item.error ? <em>{item.error}</em> : null}
                    </span>
                    <span className="rx-item-actions">
                      {item.status === "completed" ? (
                        <>
                          <IconAction
                            label={`Re-run ${item.file.name}`}
                            disabled={running || zipBusy}
                            onClick={() => void rerunItem(item)}
                          >
                            <RefreshCw size={15} />
                          </IconAction>
                          <IconAction
                            label={`Download ${item.file.name}`}
                            disabled={Boolean(downloadingId) || zipBusy}
                            onClick={() => void downloadItem(item)}
                          >
                            {downloadingId === item.id ? (
                              <LoaderCircle className="rx-spin" size={15} />
                            ) : (
                              <Download size={15} />
                            )}
                          </IconAction>
                        </>
                      ) : null}
                      <IconAction
                        label={`Remove ${item.file.name}`}
                        danger
                        disabled={running}
                        onClick={() => removeItem(item.id)}
                      >
                        <X size={15} />
                      </IconAction>
                      <GripVertical className="rx-grip" size={15} aria-hidden="true" />
                    </span>
                  </article>
                ))}
              </div>
            ) : (
              <div className="rx-empty-queue">
                <ImageIcon size={20} strokeWidth={1.4} aria-hidden="true" />
                Your queue is empty.
              </div>
            )}

            {queue.length ? (
              <div className="rx-queue-tools">
                <button
                  className="rx-button rx-button-subtle"
                  type="button"
                  disabled={!completed.length || zipBusy}
                  onClick={() => void downloadAll()}
                >
                  {zipBusy ? <LoaderCircle className="rx-spin" size={15} /> : <Archive size={15} />}
                  Download all
                </button>
                <button
                  className="rx-button rx-button-subtle"
                  type="button"
                  disabled={running || zipBusy || !queue.length}
                  onClick={() => void processBatch(queue, "Re-run all complete")}
                >
                  <RefreshCw size={15} />
                  Re-run all
                </button>
                <button
                  className="rx-button rx-button-quiet"
                  type="button"
                  disabled={running || zipBusy}
                  onClick={clearQueue}
                >
                  <Trash2 size={15} />
                  Clear
                </button>
              </div>
            ) : null}
          </section>

          <section className="rx-controls" aria-label="Process settings">
            <div className="rx-card rx-action-card">
              <div className="rx-section-head">
                <div>
                  <span className="rx-eyebrow">Process</span>
                  <h2>Remint settings</h2>
                </div>
                <span className="rx-cost">{unitCost} credits / image</span>
              </div>

              {runsRemint ? (
                <ControlGroup title="Strength" hint="Choose how assertively Remint rebuilds the image.">
                  <Segmented
                    label="Strength"
                    value={strength}
                    disabled={running}
                    options={[
                      ["light", "Light"],
                      ["balanced", "Balanced"],
                      ["deep", "Deep"]
                    ]}
                    onChange={(value) => setStrength(value as Strength)}
                  />
                </ControlGroup>
              ) : null}

              {runsFinish ? (
                <>
                  <ControlGroup title="Restoration" hint="Fidelity HD preserves the lightest grain and runs at delivery resolution.">
                    <Segmented
                      label="Restoration strength"
                      value={qfPreset}
                      disabled={running}
                      options={[
                        ["conservative", "Conservative"],
                        ["standard", "Standard"],
                        ["strong", "Strong"],
                        ["fidelity", "Fidelity HD"]
                      ]}
                      onChange={(value) => setQfPreset(value as QfPreset)}
                    />
                  </ControlGroup>

                  <ControlGroup title="Delivery size" hint="Native sends null to the finisher and preserves the source dimensions.">
                    <Segmented
                      label="Delivery size"
                      value={String(qfScale)}
                      disabled={running}
                      options={[
                        ["1", "Native"],
                        ["1.6", "1.6× HD"],
                        ["2", "2× Max"]
                      ]}
                      onChange={(value) => setQfScale(Number(value))}
                    />
                  </ControlGroup>

                  <label className="rx-switch-row">
                    <span>
                      <b>Wall smoothing</b>
                      <small>Mobile Clean</small>
                    </span>
                    <input
                      type="checkbox"
                      checked={wallClean}
                      disabled={running}
                      onChange={(event) => setWallClean(event.target.checked)}
                    />
                    <span className="rx-switch" aria-hidden="true"><i /></span>
                  </label>
                </>
              ) : null}

              <div className="rx-code-row">
                <span>
                  <small>Settings code</small>
                  <code>{settingsCode}</code>
                </span>
                <button
                  type="button"
                  className="rx-reset-link"
                  disabled={running || configAActive}
                  onClick={resetConfigA}
                >
                  <RotateCcw size={13} /> Reset to Config A
                </button>
              </div>

              <div className="rx-run-block">
                <div className="rx-run-meta">
                  <span>{pending.length} pending · {completed.length} complete</span>
                  <b>{totalCost} credits</b>
                </div>
                {hasSupabaseConfig && !userId ? (
                  <p className="rx-warning">Sign in from settings before processing.</p>
                ) : pending.length > 0 && credits.privacyCredits < totalCost ? (
                  <p className="rx-warning">This queue needs {totalCost} credits; you have {credits.privacyCredits}.</p>
                ) : null}
                <button
                  className="rx-button rx-button-primary rx-run-button"
                  type="button"
                  disabled={!canRun}
                  onClick={() => void processBatch(pending, "Process complete")}
                >
                  {running ? (
                    <><LoaderCircle className="rx-spin" size={17} /> Processing…</>
                  ) : (
                    <><Play size={17} fill="currentColor" /> Process {pending.length || "queue"}</>
                  )}
                </button>
                <p className="rx-live" aria-live="polite">
                  {notice || status || (hasSupabaseConfig ? "Ready." : "Backend configuration is required to dispatch jobs.")}
                </p>
              </div>
            </div>

            <section className={`rx-card rx-results${resultsOpen ? " is-open" : ""}`}>
              <button
                className="rx-results-trigger"
                type="button"
                aria-expanded={resultsOpen}
                onClick={() => setResultsOpen((current) => !current)}
              >
                <span>
                  <b>Results</b>
                  <small>
                    {active?.status === "completed" ? active.file.name : "Select a completed image"}
                  </small>
                </span>
                <ChevronDown size={17} aria-hidden="true" />
              </button>
              {resultsOpen ? (
                <div className="rx-results-body">
                  {active?.status === "completed" && active.job?.outputUrl ? (
                    <>
                      <div className="rx-result-preview">
                        <img src={active.job.outputUrl} alt={`Processed ${active.file.name}`} />
                      </div>
                      <div className="rx-stat-grid">
                        <Stat label="Runtime" value={active.job.runtimeMs ? `${(active.job.runtimeMs / 1000).toFixed(1)}s` : "—"} />
                        <Stat label="GPU" value={active.job.gpuType || "—"} />
                        <Stat label="Delivered" value={deliveryLabel(qfReport)} />
                        <Stat label="Encode" value={encodeLabel(qfReport)} />
                        {qfReport ? (
                          <>
                            <Stat label="Finish" value={qfReport.applied ? "Applied" : "Skipped (QC)"} />
                            <Stat label="Preset" value={qfReport.preset || "—"} />
                            <Stat label="Scale" value={qfReport.scale ? `${qfReport.scale.toFixed(2)}×` : "Native"} />
                            <Stat label="Dither" value={multiplier(qfReport.overrides?.dither)} />
                            <Stat label="Smoothing" value={multiplier(qfReport.overrides?.smoothness)} />
                            <Stat label="Sharpen" value={multiplier(qfReport.overrides?.sharpen)} />
                          </>
                        ) : null}
                      </div>
                      {rating !== null ? (
                        <div className="rx-quality-index">
                          <span>Quality index</span><b>{rating}<small>/88</small></b>
                        </div>
                      ) : null}
                      {qfReport?.qc ? (
                        <div className="rx-qc">
                          <QcRow label="SSIM" value={qfReport.qc.ssim} />
                          <QcRow label="Noise-floor ratio" value={qfReport.qc.noise_floor_ratio} />
                          <QcRow label="ρ₁" value={qfReport.qc.rho1} />
                          <QcRow label="Residual RMS" value={qfReport.qc.residual_rms} />
                          <QcRow label="H1/H0" value={qfReport.qc.h1h0_ratio} />
                          <QcRow label="Ringing" value={qfReport.qc.ringing} />
                          <QcRow label="Flatness Δ" value={qfReport.qc.flatness_delta} />
                          <QcRow label="Staircase index" value={qfReport.qc.staircase_index_jpeg} />
                          <InfoRow label="Banding origin" value={bandingOrigin(qfReport.qc.banding_origin)} />
                          <InfoRow label="Delivery check" value={deliveryCheck(qfReport)} />
                        </div>
                      ) : null}
                      {qfReport?.qc?.gradient_rois?.length ? (
                        <div className="rx-rois">
                          <div><span>Tile</span><span>Cover</span><span>ρ₁</span><span>RMS</span><span>Band</span></div>
                          {qfReport.qc.gradient_rois.slice(0, 6).map((roi) => (
                            <div key={roi.tile}>
                              <b>{roi.tile}</b><span>{fixed(roi.coverage, 2)}</span><span>{fixed(roi.rho1, 3)}</span><span>{fixed(roi.residual_rms, 2)}</span><span>{fixed(roi.banding, 2)}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div className="rx-result-actions">
                        <button className="rx-button rx-button-primary" type="button" disabled={Boolean(downloadingId)} onClick={() => void downloadItem(active)}>
                          <Download size={15} /> Download
                        </button>
                        <button className="rx-button rx-button-subtle" type="button" disabled={running || zipBusy} onClick={() => void rerunItem(active)}>
                          <RefreshCw size={15} /> Re-run · {unitCost} cr
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="rx-results-empty">
                      <ImageIcon size={20} strokeWidth={1.4} />
                      Completed image details will appear here.
                    </div>
                  )}
                </div>
              ) : null}
            </section>
          </section>
        </main>
      </div>

      <div
        className={`rx-drawer-shade${drawerOpen ? " is-open" : ""}`}
        aria-hidden={!drawerOpen}
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) setDrawerOpen(false);
        }}
      >
        <aside className="rx-drawer" aria-label="Expert settings" aria-hidden={!drawerOpen}>
          <div className="rx-drawer-head">
            <span><Settings2 size={17} /><b>Settings</b></span>
            <button className="rx-icon-button" type="button" aria-label="Close settings" onClick={() => setDrawerOpen(false)}>
              <X size={18} />
            </button>
          </div>
          <div className="rx-drawer-scroll">
            <DrawerSection title="Pipeline" open>
              <Segmented
                label="Pipeline mode"
                value={mode}
                disabled={running}
                options={[["sequence", "Remint + Finish"], ["remint", "Remint"], ["finish", "Finish"]]}
                onChange={(value) => setMode(value as PipelineMode)}
              />
              <p className="rx-drawer-note">One job end to end in sequence mode. No run-mode marketing labels.</p>
            </DrawerSection>

            <DrawerSection title="Remint engine" open>
              <Field label="Wash model">
                <Segmented label="Wash model" value={washModel} disabled={running || !runsRemint} options={[["qwen", "Qwen"], ["zimage", "Z-Image"], ["qwen+zimage", "Both"]]} onChange={(value) => setWashModel(value as WashModel)} />
              </Field>
              <Field label="Engine mode">
                <Segmented label="Engine mode" value={engineMode} disabled={running || !runsRemint} options={[["adaptive", "Adaptive"], ["template", "Template"]]} onChange={(value) => setEngineMode(value as CxRemintEngineMode)} />
              </Field>
              <Field label="Metadata">
                <Segmented label="Metadata" value={metadataMode} disabled={running || !runsRemint} options={[["device", "Device"], ["minimal", "Minimal"]]} onChange={(value) => setMetadataMode(value as MetadataMode)} />
              </Field>
              <SwitchSetting label="iPhone EXIF" detail="Write coherent device metadata" checked={iphoneExif} disabled={running || !runsRemint} onChange={setIphoneExif} />
            </DrawerSection>

            <DrawerSection title="Finish routing & tuning">
              {mode === "sequence" ? (
                <Field label="Finish routing">
                  <Segmented label="Finish routing" value={finishMode} disabled={running} options={[["adaptive", "Adaptive"], ["template", "Template"]]} onChange={(value) => setFinishMode(value as FinishRouting)} />
                </Field>
              ) : null}
              <TuneRow label="Dither" min={0} max={1.5} value={tuneDither} disabled={running || !runsFinish} onChange={setTuneDither} />
              <TuneRow label="Smoothing" min={0.5} max={1.5} value={tuneSmooth} disabled={running || !runsFinish} onChange={setTuneSmooth} />
              <TuneRow label="Sharpen" min={0} max={1.5} value={tuneSharpen} disabled={running || !runsFinish} onChange={setTuneSharpen} />
              <TuneRow label="Delivery scale" min={1} max={2} value={qfScale} disabled={running || !runsFinish} onChange={setQfScale} suffix="×" />
            </DrawerSection>

            <DrawerSection title="Naming">
              <label className="rx-field">
                <span>Output filename</span>
                <select value={nameStyle} disabled={running} onChange={(event) => setNameStyle(event.target.value as NameStyle)}>
                  <option value="settings-code">Settings code</option>
                  <option value="photo-style">Photo style</option>
                  <option value="original">Original</option>
                  <option value="custom">Custom</option>
                </select>
              </label>
              {nameStyle === "custom" ? (
                <label className="rx-field"><span>Custom name</span><input value={nameCustom} disabled={running} placeholder="my-image" onChange={(event) => setNameCustom(event.target.value)} /></label>
              ) : null}
              <code className="rx-drawer-code">{settingsCode}.jpg</code>
            </DrawerSection>

            <DrawerSection title="Appearance">
              <div className="rx-theme-row">
                <span>{theme === "dark" ? <Moon size={15} /> : <Sun size={15} />} Theme</span>
                <Segmented label="Theme" value={theme} options={[["light", "Light"], ["dark", "Dark"]]} onChange={(value) => setTheme(value as Theme)} />
              </div>
            </DrawerSection>

            <DrawerSection title="Account" open>
              <div className="rx-credit-card">
                <Wallet size={16} />
                <span><small>Available credits</small><b>{credits.privacyCredits}</b></span>
              </div>
              {showAuth ? (
                <div className="rx-auth">
                  {authMode !== "update" ? (
                    <Segmented label="Account action" value={authMode} options={[["signin", "Sign in"], ["signup", "Sign up"]]} onChange={(value) => { setAuthMode(value as AuthMode); setAuthStatus(""); }} />
                  ) : null}
                  {authMode !== "update" ? (
                    <label className="rx-input-icon"><Mail size={14} /><input type="email" autoComplete="email" value={authEmail} placeholder="you@email.com" onChange={(event) => setAuthEmail(event.target.value)} /></label>
                  ) : null}
                  {authMode !== "reset" ? (
                    <label className="rx-input-icon"><KeyRound size={14} /><input type="password" autoComplete={authMode === "signin" ? "current-password" : "new-password"} value={authPassword} placeholder={authMode === "update" ? "New password" : "Password"} onChange={(event) => setAuthPassword(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void submitAuth(); }} /></label>
                  ) : null}
                  <button className="rx-button rx-button-primary" type="button" onClick={() => void submitAuth()}>
                    <UserRound size={15} />{authMode === "signin" ? "Sign in" : authMode === "signup" ? "Create account" : authMode === "reset" ? "Send reset link" : "Update password"}
                  </button>
                  {authMode === "signin" ? <button className="rx-text-button" type="button" onClick={() => { setAuthMode("reset"); setAuthStatus(""); }}>Forgot password?</button> : null}
                  {authMode === "reset" ? <button className="rx-text-button" type="button" onClick={() => { setAuthMode("signin"); setAuthStatus(""); }}>Back to sign in</button> : null}
                  {authStatus ? <p className="rx-auth-status">{authStatus}</p> : null}
                </div>
              ) : hasSupabaseConfig && userId ? (
                <div className="rx-account-row">
                  <span><b>{userEmail || "Signed in"}</b>{isAdmin ? <small>Developer admin</small> : null}</span>
                  <button className="rx-button rx-button-subtle" type="button" onClick={() => void signOut()}><LogOut size={14} /> Sign out</button>
                </div>
              ) : (
                <p className="rx-drawer-note">Local demo credit mode. Add Supabase environment variables to enable jobs and sign-in.</p>
              )}
            </DrawerSection>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Segmented({
  label,
  value,
  options,
  disabled = false,
  onChange
}: {
  label: string;
  value: string;
  options: Array<[string, string]>;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className="rx-segmented" role="radiogroup" aria-label={label}>
      {options.map(([optionValue, optionLabel]) => (
        <button
          key={optionValue}
          type="button"
          role="radio"
          aria-checked={value === optionValue}
          className={value === optionValue ? "is-active" : ""}
          disabled={disabled}
          onClick={() => onChange(optionValue)}
        >
          {optionLabel}
        </button>
      ))}
    </div>
  );
}

function ControlGroup({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return <div className="rx-control-group"><div className="rx-control-label"><b>{title}</b><span>{hint}</span></div>{children}</div>;
}

function IconAction({ label, danger = false, disabled = false, onClick, children }: { label: string; danger?: boolean; disabled?: boolean; onClick: () => void; children: ReactNode }) {
  return <button className={`rx-item-action${danger ? " is-danger" : ""}`} type="button" aria-label={label} title={label} disabled={disabled} onClick={(event) => { event.stopPropagation(); onClick(); }}>{children}</button>;
}

function DrawerSection({ title, open = false, children }: { title: string; open?: boolean; children: ReactNode }) {
  return <details className="rx-drawer-section" open={open}><summary><b>{title}</b><ChevronDown size={15} /></summary><div className="rx-drawer-section-body">{children}</div></details>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="rx-field"><span>{label}</span>{children}</div>;
}

function SwitchSetting({ label, detail, checked, disabled, onChange }: { label: string; detail: string; checked: boolean; disabled: boolean; onChange: (checked: boolean) => void }) {
  return <label className="rx-switch-row rx-switch-row-compact"><span><b>{label}</b><small>{detail}</small></span><input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /><span className="rx-switch" aria-hidden="true"><i /></span></label>;
}

function TuneRow({ label, min, max, value, disabled, onChange, suffix = "×" }: { label: string; min: number; max: number; value: number; disabled: boolean; onChange: (value: number) => void; suffix?: string }) {
  return <label className="rx-tune"><span>{label}</span><input type="range" min={min} max={max} step={0.05} value={value} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} /><b>{value.toFixed(2)}{suffix}</b></label>;
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return <span className="rx-stat"><small>{label}</small><b>{value}</b></span>;
}

function QcRow({ label, value }: { label: string; value: number | undefined }) {
  if (value === undefined) return null;
  return <div><span>{label}</span><b>{value.toFixed(3)}</b></div>;
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return <div><span>{label}</span><b>{value}</b></div>;
}

type GradientRoi = {
  tile: string;
  coverage?: number;
  rho1?: number;
  residual_rms?: number;
  banding?: number;
};

type QfView = {
  applied: boolean;
  preset?: string;
  scale?: number | null;
  outputWidth?: number;
  outputHeight?: number;
  overrides?: { dither?: number; smoothness?: number; sharpen?: number };
  encode?: { quality?: number; subsampling?: string };
  delivery?: { width?: number; height?: number; sampling?: string };
  qc?: {
    ssim?: number;
    noise_floor_ratio?: number;
    rho1?: number;
    residual_rms?: number;
    h1h0_ratio?: number;
    ringing?: number;
    flatness_delta?: number;
    banding_origin?: string;
    staircase_index_jpeg?: number;
    gradient_rois?: GradientRoi[];
  };
};

function readQfReport(engine: Record<string, unknown> | undefined): QfView | null {
  if (!engine) return null;
  const nested = engine.quality_finish;
  const raw = isRecord(nested) ? nested : isQfShape(engine) ? engine : undefined;
  if (!raw) return null;
  const qc = isRecord(raw.qc) ? raw.qc : undefined;
  const overrides = isRecord(raw.overrides) ? raw.overrides : undefined;
  const encode = isRecord(raw.encode) ? raw.encode : undefined;
  const delivery = isRecord(raw.delivery_check) ? raw.delivery_check : undefined;
  return {
    applied: raw.applied === true,
    preset: typeof raw.preset === "string" ? raw.preset : undefined,
    scale: raw.scale === null ? null : numberOr(raw.scale),
    outputWidth: numberOr(raw.output_width),
    outputHeight: numberOr(raw.output_height),
    overrides: overrides ? { dither: numberOr(overrides.dither), smoothness: numberOr(overrides.smoothness), sharpen: numberOr(overrides.sharpen) } : undefined,
    encode: encode ? { quality: numberOr(encode.quality), subsampling: typeof encode.subsampling === "string" ? encode.subsampling : undefined } : undefined,
    delivery: delivery ? { width: numberOr(delivery.width), height: numberOr(delivery.height), sampling: typeof delivery.sampling === "string" ? delivery.sampling : undefined } : undefined,
    qc: qc ? {
      ssim: numberOr(qc.ssim),
      noise_floor_ratio: numberOr(qc.noise_floor_ratio),
      rho1: numberOr(qc.rho1),
      residual_rms: numberOr(qc.residual_rms),
      h1h0_ratio: numberOr(qc.h1h0_ratio),
      ringing: numberOr(qc.ringing),
      flatness_delta: numberOr(qc.flatness_delta),
      banding_origin: typeof qc.banding_origin === "string" ? qc.banding_origin : undefined,
      staircase_index_jpeg: numberOr(qc.staircase_index_jpeg),
      gradient_rois: readRois(qc.gradient_rois)
    } : undefined
  };
}

function readRois(value: unknown): GradientRoi[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const rows = value.filter(isRecord).map((roi) => ({
    tile: typeof roi.tile === "string" ? roi.tile : "—",
    coverage: numberOr(roi.coverage),
    rho1: numberOr(roi.rho1),
    residual_rms: numberOr(roi.residual_rms),
    banding: numberOr(roi.banding)
  }));
  return rows.length ? rows : undefined;
}

function readRating88(report: Record<string, unknown> | undefined): number | null {
  if (!report) return null;
  const engine = report.engine;
  const candidates = [isRecord(engine) ? engine.rating_88 : undefined, report.rating_88];
  for (const value of candidates) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Math.max(0, Math.min(88, Math.round(value)));
    }
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isQfShape(value: unknown): boolean {
  return isRecord(value) && value.mode === "quality-finish";
}

function numberOr(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function fixed(value: number | undefined, digits: number) {
  return value === undefined ? "—" : value.toFixed(digits);
}

function multiplier(value: number | undefined) {
  return value === undefined ? "—" : `${value.toFixed(2)}×`;
}

function encodeLabel(report: QfView | null) {
  if (!report?.encode) return "—";
  return [report.encode.quality !== undefined ? `Q${report.encode.quality}` : null, report.encode.subsampling]
    .filter(Boolean)
    .join(" · ") || "—";
}

function deliveryLabel(report: QfView | null) {
  const width = report?.delivery?.width ?? report?.outputWidth;
  const height = report?.delivery?.height ?? report?.outputHeight;
  return width && height ? `${width}×${height}` : "—";
}

function deliveryCheck(report: QfView) {
  if (!report.delivery?.width || !report.delivery.height) return null;
  return `${report.delivery.width}×${report.delivery.height}${report.delivery.sampling ? ` · ${report.delivery.sampling}` : ""}`;
}

function bandingOrigin(value: string | undefined) {
  if (!value) return null;
  return ({ pre_existing_float: "Pre-existing (source)", quantization: "Quantization", jpeg: "JPEG encode", none: "None" } as Record<string, string>)[value] ?? value;
}

function statusLabel(status: QueueStatus) {
  switch (status) {
    case "ready": return "Ready";
    case "preparing": return "Preparing…";
    case "uploading": return "Uploading…";
    case "queued": return "Queued…";
    case "processing": return "Processing…";
    case "completed": return "Completed";
    case "failed": return "Failed";
  }
}

function statusDotClass(status: QueueStatus) {
  if (status === "completed") return "is-complete";
  if (status === "failed") return "is-failed";
  if (status !== "ready") return "is-running";
  return "";
}
