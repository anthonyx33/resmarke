import {
  Archive,
  Check,
  ChevronDown,
  Download,
  Info,
  KeyRound,
  Loader2,
  LogOut,
  Mail,
  Menu,
  Moon,
  Play,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  Wallet,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { config, hasSupabaseConfig } from "./lib/config";
import { readLocalCredits, spendLocalPrivacyCredit, type CreditSnapshot } from "./lib/localCredits";
import { buildSettingsCode } from "./lib/settingsCode";
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
import "./remint.css";

/* ============================================================
   /REMINT — the simplified console.

   Same engines, same job payloads and the same credit rules as
   /cmint (which stays the reference implementation and is not
   touched by this file). What changes is the surface: four
   decisions stay on screen, everything else lives behind the
   drawer.

   No engine behaviour lives here — every run goes through the
   shared `createDeepCleanJob` client, unchanged.
   ============================================================ */

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
type NameStyle = "photo-style" | "original" | "custom" | "settings-code";
type QfPreset = "conservative" | "standard" | "strong" | "fidelity";
type FinishRouting = "adaptive" | "template";

const MAX_QUEUE = 20;
const MAX_BYTES = 25 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

/* Credit cost model — identical to /cmint: V8.9 = 15 (+2 when the adaptive
   engine runs its extra passes), Quality Finish = 6. */
const COST_REMINT = 15;
const COST_FINISH = 6;
const COST_ADAPTIVE = 2;

const PROFILE_FOR: Record<PipelineMode, "ds-remint-v8.9" | "quality-finish" | "ds-remint-v8.9-hd"> =
  {
    sequence: "ds-remint-v8.9-hd",
    remint: "ds-remint-v8.9",
    finish: "quality-finish"
  };

const MODE_LABEL: Record<PipelineMode, string> = {
  sequence: "Remint + Finish",
  remint: "Remint only",
  finish: "Finish only"
};

const STRENGTH_LABEL: Record<Strength, string> = {
  light: "Light",
  balanced: "Balanced",
  deep: "Deep"
};

const STRENGTH_HINT: Record<Strength, string> = {
  light: "The lightest pass — for frames that already look right.",
  balanced: "The everyday production pass.",
  deep: "The strongest pass — when Balanced isn't enough."
};

const QF_LABEL: Record<QfPreset, string> = {
  conservative: "Conservative",
  standard: "Standard",
  strong: "Strong",
  fidelity: "Fidelity HD"
};

const QF_HINT: Record<QfPreset, string> = {
  conservative: "Lightest touch. Closest to the original file.",
  standard: "The recommended finish for everyday delivery.",
  strong: "Strongest cleanup and sharpening — check the QC readouts.",
  fidelity: "Maximum fidelity at delivery resolution with the lightest grain."
};

const WASH_LABEL: Record<WashModel, string> = {
  qwen: "Qwen",
  zimage: "Z-Image",
  "qwen+zimage": "Both"
};

const WASH_HINT: Record<WashModel, string> = {
  qwen: "The proven default.",
  zimage: "An alternative family. Verify on your own material first.",
  "qwen+zimage": "Both models blended 50/50."
};

/* Delivery size — three buttons over the finisher's scale factor. `null` on
   the wire is the native-size path the finisher already understands. */
const SIZE_PRESETS: { key: string; label: string; value: number }[] = [
  { key: "native", label: "Native", value: 1 },
  { key: "hd", label: "1.6× HD", value: 1.6 },
  { key: "max", label: "2× Max", value: 2 }
];

function initialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const saved = localStorage.getItem("resmarke:theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function RemintApp() {
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
  const [drawer, setDrawer] = useState(false);

  /* ---- Config A is the state this page boots into (see applyConfigA). ---- */
  const [mode, setMode] = useState<PipelineMode>("sequence");
  const [washModel, setWashModel] = useState<WashModel>("qwen");
  const [strength, setStrength] = useState<Strength>("deep");
  const [engineMode, setEngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [metadataMode, setMetadataMode] = useState<MetadataMode>("device");
  const [deviceExif, setDeviceExif] = useState(true);
  const [nameStyle, setNameStyle] = useState<NameStyle>("settings-code");
  const [nameCustom, setNameCustom] = useState("");

  const [qfPreset, setQfPreset] = useState<QfPreset>("strong");
  const [qfScale, setQfScale] = useState(1);
  const [wallClean, setWallClean] = useState(true);
  const [finishMode, setFinishMode] = useState<FinishRouting>("adaptive");
  // Pro tuning — multipliers over the preset's calibrated gains. 1.00 is the
  // preset default; the worker clamps every value to its own accepted range.
  const [tuneDither, setTuneDither] = useState(1);
  const [tuneSmooth, setTuneSmooth] = useState(1.25);
  const [tuneSharpen, setTuneSharpen] = useState(1);

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
    document.title = "Remint — console";
  }, []);

  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  // Revoke every preview object URL on unmount. removeItem/clearAll revoke as
  // they go and revoking twice is a no-op, so StrictMode's double effect
  // invocation in dev stays harmless.
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
        setDrawer(true);
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawer(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

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

  /* Spending must throw on failure so processItem cancels the job it just
     dispatched — the same contract /cmint relies on. */
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
      rejected
        ? `${rejected} unsupported or oversized file${rejected === 1 ? "" : "s"} skipped.`
        : "",
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

  /* ---------------- settings ---------------- */

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
      scale: qfScale <= 1.001 ? null : Number(qfScale.toFixed(2)),
      overrides: { dither: tuneDither, smoothness: tuneSmooth, sharpen: tuneSharpen },
      materialClean: wallClean
    };
  }

  /* The settings-code input mirrors /cmint field for field. The hash covers
     the whole canonical object, so identical settings on either page must
     produce an identical code. */
  function settingsCodeFor() {
    return buildSettingsCode({
      mode,
      remint: remintOptions(),
      finish: { ...finishOptions(), finishMode }
    });
  }

  const settingsCode = settingsCodeFor();

  // Config A — the proven all-clear combination this page boots into.
  const configAActive =
    mode === "sequence" &&
    washModel === "qwen" &&
    strength === "deep" &&
    engineMode === "adaptive" &&
    qfPreset === "strong" &&
    qfScale <= 1.001 &&
    Math.abs(tuneSmooth - 1.25) < 0.001 &&
    Math.abs(tuneDither - 1) < 0.001 &&
    Math.abs(tuneSharpen - 1) < 0.001 &&
    wallClean &&
    finishMode === "adaptive";

  function applyConfigA() {
    setMode("sequence");
    setWashModel("qwen");
    setStrength("deep");
    setEngineMode("adaptive");
    setQfPreset("strong");
    setQfScale(1);
    setTuneSmooth(1.25);
    setTuneDither(1);
    setTuneSharpen(1);
    setWallClean(true);
    setFinishMode("adaptive");
  }

  const sizeKey =
    SIZE_PRESETS.find((preset) => Math.abs(preset.value - qfScale) < 0.001)?.key ?? "custom";

  function deliveredNameFor(position: number): { style: NameStyle; custom: string } {
    // custom = the exact name (first item) then consecutive -2, -3;
    // settings-code = the code encoding the exact settings, numbered per item
    // so identical-settings files never collide.
    if (!runsRemint) return { style: nameStyle, custom: nameCustom };
    if (nameStyle === "custom") {
      const base = nameCustom.trim() || "image";
      return { style: "custom", custom: position > 1 ? `${base}-${position}` : base };
    }
    if (nameStyle === "settings-code") {
      const code = settingsCodeFor();
      return { style: "settings-code", custom: position > 1 ? `${code}-${position}` : code };
    }
    return { style: nameStyle, custom: nameCustom };
  }

  /* ---------------- run ---------------- */

  /* Single-item processor. The batch run, Re-run all and the per-item redo
     all go through this, so every path is the same request with whatever
     settings are on screen at the moment it is pressed. */
  async function processItem(item: QueueItem, position: number, total: number) {
    let created: DeepCleanJob | null = null;
    setActiveId(item.id);
    patchItem(item.id, { status: "preparing", error: undefined, job: undefined });
    setStatus(`Preparing ${position} of ${total} · ${item.file.name}`);

    try {
      const naming = deliveredNameFor(position);
      const job = await createDeepCleanJob({
        file: item.file,
        creatorId: userEmail || "creator@example.com",
        profile: PROFILE_FOR[mode],
        outputMode: "stripped",
        dsRemintV89: mode === "remint" ? remintOptions() : undefined,
        qualityFinish: mode === "finish" ? finishOptions() : undefined,
        dsRemintV89Hd:
          mode === "sequence"
            ? { remint: remintOptions(), finish: finishOptions(), finishMode }
            : undefined,
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
    } catch (nextError) {
      const message =
        nextError instanceof Error ? nextError.message : "This image could not be processed.";
      if (created) await cancelDeepCleanJob(created.id).catch(() => undefined);
      patchItem(item.id, { status: "failed", job: created ?? undefined, error: message });
      setStatus(`${item.file.name}: ${message}`);
      throw nextError;
    }
  }

  async function waitForJob(
    jobId: string,
    itemId: string,
    position: number,
    total: number
  ): Promise<DeepCleanJob> {
    // No timeout, deliberately: a job can take minutes and stays live on the
    // server the whole time. Same as /cmint.
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

  async function runItems(items: QueueItem[], label: string) {
    if (!items.length) return setStatus("Add an image to the queue first.");
    if (hasSupabaseConfig && !userId) return setStatus("Sign in before running the queue.");
    if (credits.privacyCredits < items.length * unitCost) {
      return setStatus(`Not enough credits — this run needs ${items.length * unitCost}.`);
    }

    setRunning(true);
    setNotice("");
    let ok = 0;
    let failed = 0;

    for (const [index, item] of items.entries()) {
      try {
        await processItem(item, index + 1, items.length);
        ok += 1;
      } catch {
        failed += 1;
      }
    }

    setRunning(false);
    if (userId) await refreshCredits(userId);
    setStatus(
      failed
        ? `${label} · ${ok} completed · ${failed} failed. Failed images can be retried.`
        : `${label} · all ${ok} ${ok === 1 ? "image is" : "images are"} ready.`
    );
  }

  function runQueue() {
    if (running || zipBusy) return;
    void runItems(
      queue.filter((item) => item.status !== "completed"),
      "Complete"
    );
  }

  /* Re-run everything in the queue with the settings currently on screen.
     Each image is a brand-new job and bills a fresh unit cost. */
  function rerunAll() {
    if (running || zipBusy) return;
    void runItems(queue, "Re-ran the queue");
  }

  async function rerunItem(item: QueueItem) {
    if (running || zipBusy) return;
    if (hasSupabaseConfig && !userId) return setStatus("Sign in before running the queue.");
    if (credits.privacyCredits < unitCost) {
      return setStatus(`Not enough credits — a re-run needs ${unitCost}.`);
    }

    setRunning(true);
    setNotice("");
    try {
      await processItem(item, 1, 1);
      setStatus(`Re-ran ${item.file.name} with the current settings.`);
    } catch {
      /* processItem already recorded the failure on the item and in status. */
    } finally {
      setRunning(false);
      if (userId) await refreshCredits(userId);
    }
  }

  /* ---------------- downloads ---------------- */

  function outputNameFor(item: QueueItem, position?: number) {
    if (nameStyle === "custom") {
      const base = nameCustom.trim() || "image";
      return `${position === undefined ? base : `${base}-${position + 1}`}.jpg`;
    }
    if (nameStyle === "settings-code") {
      const code = settingsCodeFor();
      return `${position === undefined ? code : `${code}-${position + 1}`}.jpg`;
    }
    const raw = item.file.name.replace(/\.[^.]+$/, "");
    const base = raw.replace(/[<>:"/\\|?*\u0000-\u001f\s]+/g, "-").slice(0, 90) || "image";
    const prefix = position === undefined ? "" : `${String(position + 1).padStart(2, "0")}-`;
    const suffix = mode === "finish" ? "finish" : mode === "remint" ? "remint" : "remint-hd";
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
      // fflate stays out of the initial chunk — it only loads on the first ZIP.
      const { zip } = await import("fflate");
      const zipped = await new Promise<Uint8Array>((resolve, reject) => {
        zip(files, { level: 0 }, (zipError, data) => (zipError ? reject(zipError) : resolve(data)));
      });
      const buffer = zipped.buffer.slice(
        zipped.byteOffset,
        zipped.byteOffset + zipped.byteLength
      ) as ArrayBuffer;
      saveBlob(new Blob([buffer], { type: "application/zip" }), "remint-images.zip");
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
  const resultUrl = active?.job?.status === "completed" ? active.job.outputUrl ?? "" : "";

  return (
    <div className="remint">
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

      <div className="rx-shell">
        {/* ---------- top bar ---------- */}
        <header className="rx-top">
          <div className="rx-brand">
            <span className="rx-brand-mark">
              <Sparkles size={15} aria-hidden="true" />
            </span>
            <span className="rx-brand-text">
              <b>Remint</b>
              <span>{MODE_LABEL[mode]}</span>
            </span>
          </div>

          <span className="rx-spacer" />

          <div className="rx-top-right">
            {configAActive ? (
              <span className="rx-chip is-on" title="The proven all-clear configuration">
                <Check size={12} aria-hidden="true" /> Config A · Proven
              </span>
            ) : (
              <button
                className="rx-chip"
                type="button"
                onClick={applyConfigA}
                disabled={running}
                title="Reset every control to Config A"
              >
                <RotateCcw size={12} aria-hidden="true" /> Reset to Config A
              </button>
            )}

            <span className="rx-credits" title="Credit balance">
              <Wallet size={13} aria-hidden="true" />
              <b>{credits.privacyCredits}</b>
            </span>

            <button
              className="rx-icon-btn"
              type="button"
              aria-label="Open settings"
              aria-expanded={drawer}
              title="Settings"
              onClick={() => setDrawer(true)}
            >
              <Menu size={16} />
            </button>
          </div>
        </header>

        <div className="rx-work">
          {/* ---------- images ---------- */}
          <section className="rx-pane rx-pane-left" aria-label="Images">
            <div className="rx-pane-head">
              <span className="rx-pane-title">Images</span>
              <span className="rx-count">
                {queue.length}/{MAX_QUEUE}
              </span>
              <span className="rx-spacer" />
              <button
                className="rx-btn rx-btn-sm"
                type="button"
                onClick={openPicker}
                disabled={running || queue.length >= MAX_QUEUE}
              >
                <Upload size={13} aria-hidden="true" /> Add
              </button>
            </div>

            <div className="rx-scroll">
              <div
                className={`rx-drop${dragging ? " is-drag" : ""}`}
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
                <Upload className="rx-drop-icon" size={20} aria-hidden="true" />
                <b>Drop images</b>
                <span>JPEG · PNG · WebP · up to 25 MB each</span>
              </div>

              {queue.length ? (
                <div className="rx-queue">
                  {queue.map((item) => (
                    <div
                      key={item.id}
                      className={`rx-item${item.id === active?.id ? " is-active" : ""}${
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
                      <span className="rx-thumb">
                        <img src={item.previewUrl} alt="" />
                      </span>
                      <span className="rx-item-body">
                        <span className="rx-item-name">{item.file.name}</span>
                        <span className="rx-item-meta">
                          <i className={`rx-dot ${statusDotClass(item.status)}`} />
                          {statusLabel(item.status)}
                          {item.width ? ` · ${item.width}×${item.height}` : ""}
                        </span>
                        {item.error ? <span className="rx-item-err">{item.error}</span> : null}
                      </span>
                      <span className="rx-item-actions">
                        {item.status === "completed" ? (
                          <>
                            <button
                              className="rx-act"
                              type="button"
                              title={`Redo this image with the current settings (${unitCost} credits)`}
                              aria-label="Redo this image"
                              disabled={running || zipBusy}
                              onClick={(event) => {
                                event.stopPropagation();
                                void rerunItem(item);
                              }}
                            >
                              <RefreshCw size={14} />
                            </button>
                            <button
                              className="rx-act"
                              type="button"
                              title="Download"
                              aria-label="Download this image"
                              disabled={downloadingId === item.id}
                              onClick={(event) => {
                                event.stopPropagation();
                                void downloadItem(item);
                              }}
                            >
                              {downloadingId === item.id ? (
                                <Loader2 className="rx-spin" size={14} />
                              ) : (
                                <Download size={14} />
                              )}
                            </button>
                          </>
                        ) : null}
                        <button
                          className="rx-act is-danger"
                          type="button"
                          title="Remove"
                          aria-label="Remove this image"
                          disabled={running}
                          onClick={(event) => {
                            event.stopPropagation();
                            removeItem(item.id);
                          }}
                        >
                          <X size={14} />
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rx-empty">
                  Nothing queued yet. Drop images above, set the four controls on the right, and
                  run.
                </p>
              )}

              {queue.length ? (
                <div className="rx-queue-foot">
                  <button
                    className="rx-btn"
                    type="button"
                    onClick={downloadAll}
                    disabled={!completed.length || zipBusy || running}
                  >
                    {zipBusy ? (
                      <Loader2 className="rx-spin" size={14} />
                    ) : (
                      <Archive size={14} aria-hidden="true" />
                    )}
                    Download all ({completed.length})
                  </button>
                  <button
                    className="rx-btn"
                    type="button"
                    onClick={rerunAll}
                    disabled={running || zipBusy}
                    title={`Re-run every image with the current settings (${
                      queue.length * unitCost
                    } credits)`}
                  >
                    <RefreshCw size={14} aria-hidden="true" /> Re-run all
                  </button>
                  <button
                    className="rx-btn"
                    type="button"
                    onClick={clearAll}
                    disabled={running || zipBusy}
                  >
                    <Trash2 size={14} aria-hidden="true" /> Clear
                  </button>
                </div>
              ) : null}
            </div>
          </section>

          {/* ---------- controls ---------- */}
          <section className="rx-pane rx-pane-right" aria-label="Controls">
            <div className="rx-pane-head">
              <span className="rx-pane-title">Settings</span>
              <span className="rx-spacer" />
              <span className="rx-count">{unitCost} cr / image</span>
            </div>

            <div className="rx-scroll">
              <div className="rx-card">
                <div className="rx-card-body">
                  <Field label="Strength" hint={STRENGTH_HINT[strength]}>
                    <div className="rx-seg" role="radiogroup" aria-label="Strength">
                      {(["light", "balanced", "deep"] as Strength[]).map((value) => (
                        <button
                          key={value}
                          type="button"
                          role="radio"
                          aria-checked={strength === value}
                          className={strength === value ? "is-active" : ""}
                          disabled={running || !runsRemint}
                          onClick={() => setStrength(value)}
                        >
                          {STRENGTH_LABEL[value]}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <Field label="Restoration" hint={QF_HINT[qfPreset]}>
                    <div className="rx-seg" role="radiogroup" aria-label="Restoration">
                      {(["conservative", "standard", "strong", "fidelity"] as QfPreset[]).map(
                        (value) => (
                          <button
                            key={value}
                            type="button"
                            role="radio"
                            aria-checked={qfPreset === value}
                            className={qfPreset === value ? "is-active" : ""}
                            disabled={running || !runsFinish}
                            onClick={() => setQfPreset(value)}
                          >
                            {QF_LABEL[value]}
                          </button>
                        )
                      )}
                    </div>
                  </Field>

                  <Field
                    label="Delivery size"
                    detail={qfScale <= 1.001 ? "native" : `${qfScale.toFixed(2)}×`}
                    hint={
                      qfScale <= 1.001
                        ? "Native delivery is always the quality floor."
                        : "Enlargement adds perceived resolution only when the finisher's self-QC passes."
                    }
                  >
                    <div className="rx-seg" role="radiogroup" aria-label="Delivery size">
                      {SIZE_PRESETS.map((preset) => (
                        <button
                          key={preset.key}
                          type="button"
                          role="radio"
                          aria-checked={sizeKey === preset.key}
                          className={sizeKey === preset.key ? "is-active" : ""}
                          disabled={running || !runsFinish}
                          onClick={() => setQfScale(preset.value)}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <label className="rx-switch">
                    <input
                      type="checkbox"
                      checked={wallClean}
                      disabled={running || !runsFinish}
                      onChange={(event) => setWallClean(event.target.checked)}
                    />
                    <span className="rx-switch-text">
                      <b>Wall smoothing</b>
                      <span className="rx-hint">Mobile Clean — flattens wall and sky banding.</span>
                    </span>
                    <span className="rx-switch-track">
                      <span className="rx-switch-knob" />
                    </span>
                  </label>

                  <div className="rx-code" title="The delivered filename encodes these settings">
                    <code>{settingsCode}</code>
                    <button
                      className="rx-link"
                      type="button"
                      style={{ flex: "0 0 auto" }}
                      onClick={() => setDrawer(true)}
                    >
                      Naming
                    </button>
                  </div>
                </div>
              </div>

              {/* ---- results ---- */}
              <details className="rx-acc">
                <summary>
                  Results
                  <span className="rx-acc-sub">
                    {active?.job?.status === "completed"
                      ? active.file.name
                      : `${completed.length} ready`}
                  </span>
                  <ChevronDown className="rx-acc-chev" size={15} aria-hidden="true" />
                </summary>
                <div className="rx-acc-body">
                  {!active || active.job?.status !== "completed" ? (
                    <p className="rx-hint">
                      Run an image to see runtime, delivery size and the finisher's self-QC here.
                    </p>
                  ) : (
                    <>
                      {resultUrl ? (
                        <div className="rx-preview">
                          <figure>
                            <img src={active.previewUrl} alt="Original" />
                            <figcaption>Original</figcaption>
                          </figure>
                          <figure>
                            <img src={resultUrl} alt="Result" />
                            <figcaption>Result</figcaption>
                          </figure>
                        </div>
                      ) : null}

                      <div className="rx-stats">
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
                                qfReport.delivery?.width
                                  ? `${qfReport.delivery.width}×${qfReport.delivery.height}`
                                  : qfReport.outputWidth
                                    ? `${qfReport.outputWidth}×${qfReport.outputHeight}`
                                    : "—"
                              }
                            />
                            <Stat label="Encode" value={encodeLabel(qfReport)} />
                            <Stat
                              label="Preset run"
                              value={`${qfReport.preset ?? "—"} · ${
                                qfReport.scale ? `${qfReport.scale.toFixed(2)}×` : "native"
                              }`}
                            />
                          </>
                        ) : null}
                      </div>

                      {qfReport?.overrides && hasOverrides(qfReport.overrides) ? (
                        <div className="rx-stats">
                          <Stat label="Dither" value={multiplier(qfReport.overrides.dither)} />
                          <Stat
                            label="Smoothing"
                            value={multiplier(qfReport.overrides.smoothness)}
                          />
                          <Stat label="Sharpening" value={multiplier(qfReport.overrides.sharpen)} />
                          {qfReport.qc?.gradient_ladder_attempts !== undefined ||
                          qfReport.qc?.gradient_alpha !== undefined ? (
                            <Stat
                              label="Gradient ladder"
                              value={`${qfReport.qc?.gradient_ladder_attempts ?? 1}× · α${(
                                qfReport.qc?.gradient_alpha ?? 1
                              ).toFixed(2)}`}
                            />
                          ) : null}
                        </div>
                      ) : null}

                      {rating !== null ? (
                        <div
                          className={`rx-index is-${
                            rating <= 29 ? "low" : rating <= 58 ? "mid" : "high"
                          }`}
                        >
                          Quality index {rating}/88
                        </div>
                      ) : null}

                      {qfReport?.qc ? (
                        <div className="rx-qc">
                          <QcRow label="SSIM vs input" value={qfReport.qc.ssim} />
                          <QcRow label="Noise floor kept" value={qfReport.qc.noise_floor_ratio} />
                          <QcRow label="Grain correlation ρ₁" value={qfReport.qc.rho1} />
                          <QcRow label="Residual RMS (LSB)" value={qfReport.qc.residual_rms} />
                          <QcRow label="H1/H0 ratio" value={qfReport.qc.h1h0_ratio} />
                          <QcRow label="Ringing" value={qfReport.qc.ringing} />
                          <QcRow label="Flatness Δ" value={qfReport.qc.flatness_delta} />
                          <QcRow
                            label="Staircase index (JPEG)"
                            value={qfReport.qc.staircase_index_jpeg}
                          />
                          {qfReport.qc.banding_origin ? (
                            <div className="rx-qc-row">
                              <span>Banding origin</span>
                              <b>
                                {BANDING_ORIGIN_LABEL[qfReport.qc.banding_origin] ??
                                  qfReport.qc.banding_origin}
                              </b>
                            </div>
                          ) : null}
                          {qfReport.delivery ? (
                            <div className="rx-qc-row">
                              <span>Delivery check</span>
                              <b>
                                {qfReport.delivery.width}×{qfReport.delivery.height}
                                {qfReport.delivery.sampling
                                  ? ` · ${qfReport.delivery.sampling}`
                                  : ""}
                              </b>
                            </div>
                          ) : null}
                          <div className="rx-qc-row">
                            <span>Self-QC</span>
                            <b
                              style={{
                                color: qfReport.applied ? "var(--rx-ok)" : "var(--rx-warn)"
                              }}
                            >
                              {qfReport.applied ? "passed" : "rejected — input shipped"}
                            </b>
                          </div>
                        </div>
                      ) : null}

                      {qfReport?.qc?.gradient_rois?.length ? (
                        <div className="rx-rois">
                          <div className="rx-rois-head">
                            <span>Tile</span>
                            <span>Cover</span>
                            <span>ρ₁</span>
                            <span>RMS</span>
                            <span>Band</span>
                          </div>
                          {qfReport.qc.gradient_rois.slice(0, 6).map((roi) => (
                            <div className="rx-rois-row" key={roi.tile}>
                              <span>{roi.tile}</span>
                              <b>{fixed(roi.coverage, 2)}</b>
                              <b>{fixed(roi.rho1, 3)}</b>
                              <b>{fixed(roi.residual_rms, 2)}</b>
                              <b>{fixed(roi.banding, 2)}</b>
                            </div>
                          ))}
                        </div>
                      ) : null}

                      <button
                        className="rx-btn rx-btn-primary rx-btn-block"
                        type="button"
                        disabled={downloadingId === active.id}
                        onClick={() => void downloadItem(active)}
                      >
                        {downloadingId === active.id ? (
                          <Loader2 className="rx-spin" size={15} />
                        ) : (
                          <Download size={15} aria-hidden="true" />
                        )}
                        Download this image
                      </button>
                      <button
                        className="rx-btn rx-btn-block"
                        type="button"
                        disabled={running || zipBusy}
                        onClick={() => void rerunItem(active)}
                      >
                        <RefreshCw size={15} aria-hidden="true" />
                        Re-run with current settings ({unitCost} cr)
                      </button>
                    </>
                  )}
                </div>
              </details>

              <button
                className="rx-btn rx-btn-block rx-mobile-only"
                type="button"
                onClick={() => setDrawer(true)}
              >
                <Menu size={15} aria-hidden="true" /> All settings
              </button>
            </div>

            {/* ---- run bar ---- */}
            <div className="rx-run">
              {hasSupabaseConfig && !userId ? (
                <div className="rx-note is-warn">
                  <Info size={13} aria-hidden="true" />
                  <span>
                    Sign in to dispatch jobs —{" "}
                    <button className="rx-link" type="button" onClick={() => setDrawer(true)}>
                      open the account panel
                    </button>
                    .
                  </span>
                </div>
              ) : pending.length > 0 && credits.privacyCredits < totalCost ? (
                <div className="rx-note is-warn">
                  <Info size={13} aria-hidden="true" />
                  <span>
                    This run needs {totalCost} credits; you have {credits.privacyCredits}.
                  </span>
                </div>
              ) : notice ? (
                <div className="rx-note is-warn">
                  <Info size={13} aria-hidden="true" />
                  <span>{notice}</span>
                </div>
              ) : null}

              <div className="rx-run-meta">
                <span>
                  {pending.length} pending · {completed.length} done
                </span>
                <b>{totalCost} credits</b>
              </div>

              <button
                className="rx-btn rx-btn-primary rx-btn-lg rx-btn-block"
                type="button"
                onClick={runQueue}
                disabled={!canRun}
              >
                {running ? (
                  <>
                    <Loader2 className="rx-spin" size={16} /> Processing…
                  </>
                ) : (
                  <>
                    <Play size={16} aria-hidden="true" />
                    {pending.some((item) => item.status === "failed")
                      ? "Retry unfinished"
                      : `Remint ${pending.length} ${pending.length === 1 ? "image" : "images"}`}
                  </>
                )}
              </button>

              <p className="rx-status">
                {status ||
                  (hasSupabaseConfig
                    ? "Ready."
                    : "Supabase env vars are not set — jobs cannot be dispatched.")}
              </p>
            </div>
          </section>
        </div>
      </div>

      {/* ---------- drawer ---------- */}
      {drawer ? (
        <>
          <button
            className="rx-scrim"
            type="button"
            aria-label="Close settings"
            onClick={() => setDrawer(false)}
          />
          <aside className="rx-drawer" role="dialog" aria-label="All settings">
            <div className="rx-drawer-head">
              <h2>Settings</h2>
              <span className="rx-spacer" />
              <button
                className="rx-icon-btn"
                type="button"
                aria-label="Toggle theme"
                title={theme === "dark" ? "Switch to light" : "Switch to dark"}
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              >
                {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
              </button>
              <button
                className="rx-icon-btn"
                type="button"
                aria-label="Close settings"
                onClick={() => setDrawer(false)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="rx-drawer-body">
              <button
                className="rx-btn rx-btn-block"
                type="button"
                disabled={running || configAActive}
                onClick={applyConfigA}
              >
                <RotateCcw size={14} aria-hidden="true" />
                {configAActive ? "Config A is active" : "Reset to Config A"}
              </button>

              {/* ---- pipeline ---- */}
              <details className="rx-acc">
                <summary>
                  Pipeline
                  <span className="rx-acc-sub">{MODE_LABEL[mode]}</span>
                  <ChevronDown className="rx-acc-chev" size={15} aria-hidden="true" />
                </summary>
                <div className="rx-acc-body">
                  <Field
                    label="Stages"
                    hint="The sequence runs the remint and the HD finish as one job."
                  >
                    <div className="rx-seg is-stack" role="radiogroup" aria-label="Pipeline">
                      {(["sequence", "remint", "finish"] as PipelineMode[]).map((value) => (
                        <button
                          key={value}
                          type="button"
                          role="radio"
                          aria-checked={mode === value}
                          className={mode === value ? "is-active" : ""}
                          disabled={running}
                          onClick={() => setMode(value)}
                        >
                          {MODE_LABEL[value]}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <Field label="Wash model" hint={WASH_HINT[washModel]}>
                    <div className="rx-seg" role="radiogroup" aria-label="Wash model">
                      {(["qwen", "zimage", "qwen+zimage"] as WashModel[]).map((value) => (
                        <button
                          key={value}
                          type="button"
                          role="radio"
                          aria-checked={washModel === value}
                          className={washModel === value ? "is-active" : ""}
                          disabled={running || !runsRemint}
                          onClick={() => setWashModel(value)}
                        >
                          {WASH_LABEL[value]}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <Field
                    label="Engine"
                    hint={
                      engineMode === "adaptive"
                        ? "Runs extra passes and ships the strongest result that clears the bar (+2 credits)."
                        : "Runs the template path exactly as configured."
                    }
                  >
                    <div className="rx-seg" role="radiogroup" aria-label="Engine">
                      {(["adaptive", "template"] as CxRemintEngineMode[]).map((value) => (
                        <button
                          key={value}
                          type="button"
                          role="radio"
                          aria-checked={engineMode === value}
                          className={engineMode === value ? "is-active" : ""}
                          disabled={running || !runsRemint}
                          onClick={() => setEngineMode(value)}
                        >
                          {value === "adaptive" ? "Adaptive" : "Template"}
                        </button>
                      ))}
                    </div>
                  </Field>

                  {mode === "sequence" ? (
                    <Field
                      label="Finish routing"
                      hint={
                        finishMode === "adaptive"
                          ? "Builds more than one finish candidate and ships the strongest one that meets the quality bar."
                          : "Runs exactly the preset selected on the main panel."
                      }
                    >
                      <div className="rx-seg" role="radiogroup" aria-label="Finish routing">
                        {(["adaptive", "template"] as FinishRouting[]).map((value) => (
                          <button
                            key={value}
                            type="button"
                            role="radio"
                            aria-checked={finishMode === value}
                            className={finishMode === value ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setFinishMode(value)}
                          >
                            {value === "adaptive" ? "Adaptive" : "Template"}
                          </button>
                        ))}
                      </div>
                    </Field>
                  ) : null}
                </div>
              </details>

              {/* ---- metadata ---- */}
              <details className="rx-acc">
                <summary>
                  Metadata
                  <span className="rx-acc-sub">
                    {metadataMode === "device" ? "Device" : "Minimal"}
                  </span>
                  <ChevronDown className="rx-acc-chev" size={15} aria-hidden="true" />
                </summary>
                <div className="rx-acc-body">
                  <Field
                    label="Metadata"
                    hint={
                      metadataMode === "device"
                        ? "Writes a full device-style tag block."
                        : "Writes the minimum viable tag set."
                    }
                  >
                    <div className="rx-seg" role="radiogroup" aria-label="Metadata">
                      {(["device", "minimal"] as MetadataMode[]).map((value) => (
                        <button
                          key={value}
                          type="button"
                          role="radio"
                          aria-checked={metadataMode === value}
                          className={metadataMode === value ? "is-active" : ""}
                          disabled={running || !runsRemint}
                          onClick={() => setMetadataMode(value)}
                        >
                          {value === "device" ? "Device" : "Minimal"}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <label className="rx-switch">
                    <input
                      type="checkbox"
                      checked={deviceExif}
                      disabled={running || !runsRemint}
                      onChange={(event) => setDeviceExif(event.target.checked)}
                    />
                    <span className="rx-switch-text">
                      <b>iPhone EXIF</b>
                      <span className="rx-hint">
                        Stamp an iPhone capture profile on the output.
                      </span>
                    </span>
                    <span className="rx-switch-track">
                      <span className="rx-switch-knob" />
                    </span>
                  </label>
                </div>
              </details>

              {/* ---- pro tuning ---- */}
              <details className="rx-acc">
                <summary>
                  Pro tuning
                  <span className="rx-acc-sub">
                    {tuneDither === 1 && tuneSmooth === 1 && tuneSharpen === 1
                      ? "preset defaults"
                      : "tuned"}
                  </span>
                  <ChevronDown className="rx-acc-chev" size={15} aria-hidden="true" />
                </summary>
                <div className="rx-acc-body">
                  <p className="rx-hint">
                    Multipliers over the preset's calibrated gains — 1.00× is the preset. The worker
                    clamps each value to its own accepted range.
                  </p>
                  <TuneRow
                    label="Dither"
                    value={tuneDither}
                    min={0}
                    max={1.5}
                    disabled={running || !runsFinish}
                    onChange={setTuneDither}
                  />
                  <TuneRow
                    label="Smoothing"
                    value={tuneSmooth}
                    min={0.5}
                    max={1.5}
                    disabled={running || !runsFinish}
                    onChange={setTuneSmooth}
                  />
                  <TuneRow
                    label="Sharpen"
                    value={tuneSharpen}
                    min={0}
                    max={1.5}
                    disabled={running || !runsFinish}
                    onChange={setTuneSharpen}
                  />

                  <Field
                    label="Exact enlargement"
                    detail={qfScale <= 1.001 ? "native" : `${qfScale.toFixed(2)}×`}
                    hint="The finisher accepts any factor from 1.00 to 2.00."
                  >
                    <input
                      className="rx-range"
                      type="range"
                      min={1}
                      max={2}
                      step={0.05}
                      value={qfScale}
                      disabled={running || !runsFinish}
                      aria-label="Exact enlargement factor"
                      onChange={(event) => setQfScale(Number(event.target.value))}
                    />
                    <div className="rx-range-ends">
                      <span>Native (quality floor)</span>
                      <span>2× (~2500px)</span>
                    </div>
                  </Field>
                </div>
              </details>

              {/* ---- naming ---- */}
              <details className="rx-acc">
                <summary>
                  Naming
                  <span className="rx-acc-sub">{nameStyle}</span>
                  <ChevronDown className="rx-acc-chev" size={15} aria-hidden="true" />
                </summary>
                <div className="rx-acc-body">
                  <Field
                    label="Filename"
                    hint="The settings-code encodes every option that produced the image, so a filename can be traced back to its exact configuration."
                  >
                    <div className="rx-seg is-stack" role="radiogroup" aria-label="Filename style">
                      {(["settings-code", "photo-style", "original", "custom"] as NameStyle[]).map(
                        (value) => (
                          <button
                            key={value}
                            type="button"
                            role="radio"
                            aria-checked={nameStyle === value}
                            className={nameStyle === value ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setNameStyle(value)}
                          >
                            {value === "settings-code"
                              ? "Settings code"
                              : value === "photo-style"
                                ? "Photo style"
                                : value === "original"
                                  ? "Original name"
                                  : "Custom"}
                          </button>
                        )
                      )}
                    </div>
                  </Field>

                  {nameStyle === "custom" ? (
                    <input
                      className="rx-input"
                      type="text"
                      placeholder="my-shoot"
                      value={nameCustom}
                      disabled={running}
                      onChange={(event) => setNameCustom(event.target.value)}
                    />
                  ) : null}

                  <div className="rx-code">
                    <code>{settingsCode}</code>
                  </div>
                </div>
              </details>

              {/* ---- account ---- */}
              <details className="rx-acc" open={showAuth}>
                <summary>
                  Account
                  <span className="rx-acc-sub">{userEmail || "not signed in"}</span>
                  <ChevronDown className="rx-acc-chev" size={15} aria-hidden="true" />
                </summary>
                <div className="rx-acc-body">
                  <div className="rx-row">
                    <span>Credits</span>
                    <b>{credits.privacyCredits}</b>
                  </div>
                  <div className="rx-row">
                    <span>Re-Mint Max</span>
                    <b>{credits.deepCleanCredits}</b>
                  </div>

                  {!hasSupabaseConfig ? (
                    <p className="rx-hint">
                      Supabase is not configured in this build — credits run in demo mode and jobs
                      cannot be dispatched.
                    </p>
                  ) : showAuth ? (
                    <>
                      {authMode !== "update" ? (
                        <div className="rx-seg">
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
                        <div className="rx-input-icon">
                          <Mail size={14} aria-hidden="true" />
                          <input
                            className="rx-input"
                            type="email"
                            autoComplete="email"
                            placeholder="you@email.com"
                            value={authEmail}
                            onChange={(event) => setAuthEmail(event.target.value)}
                          />
                        </div>
                      ) : null}
                      {authMode !== "reset" ? (
                        <div className="rx-input-icon">
                          <KeyRound size={14} aria-hidden="true" />
                          <input
                            className="rx-input"
                            type="password"
                            autoComplete={
                              authMode === "signin" ? "current-password" : "new-password"
                            }
                            placeholder={authMode === "update" ? "New password" : "Password"}
                            value={authPassword}
                            onChange={(event) => setAuthPassword(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") void submitAuth();
                            }}
                          />
                        </div>
                      ) : null}
                      <button
                        className="rx-btn rx-btn-primary rx-btn-block"
                        type="button"
                        onClick={submitAuth}
                      >
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
                          className="rx-link"
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
                          className="rx-link"
                          type="button"
                          onClick={() => {
                            setAuthMode("signin");
                            setAuthStatus("");
                          }}
                        >
                          Back to sign in
                        </button>
                      ) : null}
                    </>
                  ) : (
                    <>
                      {isAdmin ? <span className="rx-chip is-on">Developer admin</span> : null}
                      <button className="rx-btn rx-btn-block" type="button" onClick={signOut}>
                        <LogOut size={14} aria-hidden="true" /> Sign out
                      </button>
                    </>
                  )}
                  {authStatus ? <p className="rx-hint">{authStatus}</p> : null}
                </div>
              </details>
            </div>
          </aside>
        </>
      ) : null}
    </div>
  );
}

/* ============================================================
   Sub-components
   ============================================================ */

function Field({
  label,
  detail,
  hint,
  children
}: {
  label: string;
  detail?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="rx-field">
      <span className="rx-label">
        {label}
        {detail ? <em>{detail}</em> : null}
      </span>
      {children}
      {hint ? <p className="rx-hint">{hint}</p> : null}
    </div>
  );
}

function TuneRow({
  label,
  value,
  min,
  max,
  disabled,
  onChange
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  disabled: boolean;
  onChange: (next: number) => void;
}) {
  return (
    <div className="rx-tune">
      <span>{label}</span>
      <input
        className="rx-range"
        type="range"
        min={min}
        max={max}
        step={0.05}
        value={value}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className={`rx-tune-val${value !== 1 ? " is-tuned" : ""}`}>{value.toFixed(2)}×</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <span className="rx-stat">
      <em>{label}</em>
      <b>{value}</b>
    </span>
  );
}

function QcRow({ label, value }: { label: string; value: number | undefined }) {
  if (typeof value !== "number") return null;
  return (
    <div className="rx-qc-row">
      <span>{label}</span>
      <b>{value.toFixed(3)}</b>
    </div>
  );
}

/* ============================================================
   Report formatting
   ============================================================ */

const BANDING_ORIGIN_LABEL: Record<string, string> = {
  pre_existing_float: "pre-existing (source)",
  quantization: "quantization",
  jpeg: "JPEG encode",
  none: "none"
};

function encodeLabel(report: QfView | null): string {
  const quality = report?.encode?.quality;
  const subsampling = report?.encode?.subsampling;
  if (quality === undefined && !subsampling) return "set by preset";
  return [quality !== undefined ? `Q${quality}` : null, subsampling].filter(Boolean).join(" · ");
}

function hasOverrides(overrides: NonNullable<QfView["overrides"]>): boolean {
  return (
    overrides.dither !== undefined ||
    overrides.smoothness !== undefined ||
    overrides.sharpen !== undefined
  );
}

function multiplier(value: number | undefined): string {
  return value === undefined ? "—" : `${value.toFixed(2)}×`;
}

function fixed(value: number | undefined, digits: number): string {
  return value === undefined ? "—" : value.toFixed(digits);
}

/* ============================================================
   Report readers — the shapes the worker emits, read defensively.
   ============================================================ */

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
  /** The multipliers the worker actually ran with, after its own clamping. */
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
    gradient_alpha?: number;
    gradient_ladder_attempts?: number;
    gradient_rois?: GradientRoi[];
  };
};

function readQfReport(engine: Record<string, unknown> | undefined): QfView | null {
  if (!engine) return null;
  // The sequence nests the finisher report under `quality_finish`; a
  // standalone finish puts it at the engine root. Check both rather than
  // trusting the currently-selected mode — the job may have run under a
  // different one.
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
    overrides: overrides
      ? {
          dither: numberOr(overrides.dither),
          smoothness: numberOr(overrides.smoothness),
          sharpen: numberOr(overrides.sharpen)
        }
      : undefined,
    encode: encode
      ? {
          quality: numberOr(encode.quality),
          subsampling: typeof encode.subsampling === "string" ? encode.subsampling : undefined
        }
      : undefined,
    delivery: delivery
      ? {
          width: numberOr(delivery.width),
          height: numberOr(delivery.height),
          sampling: typeof delivery.sampling === "string" ? delivery.sampling : undefined
        }
      : undefined,
    qc: qc
      ? {
          ssim: numberOr(qc.ssim),
          noise_floor_ratio: numberOr(qc.noise_floor_ratio),
          rho1: numberOr(qc.rho1),
          residual_rms: numberOr(qc.residual_rms),
          h1h0_ratio: numberOr(qc.h1h0_ratio),
          ringing: numberOr(qc.ringing),
          flatness_delta: numberOr(qc.flatness_delta),
          banding_origin: typeof qc.banding_origin === "string" ? qc.banding_origin : undefined,
          staircase_index_jpeg: numberOr(qc.staircase_index_jpeg),
          gradient_alpha: numberOr(qc.gradient_alpha),
          gradient_ladder_attempts: numberOr(qc.gradient_ladder_attempts),
          gradient_rois: readRois(qc.gradient_rois)
        }
      : undefined
  };
}

function readRois(value: unknown): GradientRoi[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const rois = value.filter(isRecord).map((roi) => ({
    tile: typeof roi.tile === "string" ? roi.tile : "—",
    coverage: numberOr(roi.coverage),
    rho1: numberOr(roi.rho1),
    residual_rms: numberOr(roi.residual_rms),
    banding: numberOr(roi.banding)
  }));
  return rois.length ? rois : undefined;
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
