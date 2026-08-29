import {
  Archive,
  ArrowRight,
  Check,
  ChevronDown,
  Copy,
  Download,
  Droplets,
  Film,
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
  RefreshCw,
  Scan,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  UserRound,
  Wallet,
  X,
  Zap
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
   /REMINT — the same console as /cmint, tightened.

   Identical engines, identical job payloads, identical credit
   rules. /cmint stays the reference implementation and is not
   touched by this file. What changes here is the workbench:

     · Config A is the boot state, presented as a real preset
       card instead of a debug button.
     · The settings-code (the delivered filename) is live in
       the topbar, one click from the clipboard.
     · Metadata and naming are segmented controls, not selects.
     · The queue rail gains Re-run all, per-item error text and
       a live batch counter; the run bar gains a progress bar
       and a Cmd/Ctrl+Enter shortcut.
     · The result card collapses, so the rail stops growing.

   No engine behaviour lives here — every run goes through the
   same createDeepCleanJob payloads the existing pages use.
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
type NameStyle = "photo-style" | "original" | "custom" | "settings-code";
type QfPreset = "conservative" | "standard" | "strong" | "fidelity";
type FinishRouting = "adaptive" | "template";

const MAX_QUEUE = 20;
const MAX_BYTES = 25 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

/* Credit cost model — identical to /cmint: V8.9 = 15 (+2 when the adaptive
   engine runs its extra passes), Quality Finish = 6 (CPU-only). The sequence
   is a single job that performs both stages, so it bills the sum. */
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
  "qwen+zimage": "Qwen + Z-Image"
};

const STRENGTH_HINT: Record<Strength, string> = {
  light: "The lightest pass — for frames that already look right.",
  balanced: "The recommended pass for everyday production work.",
  deep: "The strongest pass — only when Balanced isn't enough."
};

const QF_HINT: Record<QfPreset, string> = {
  conservative: "Lightest touch. Closest to the original file.",
  standard: "The recommended finish for everyday delivery.",
  strong: "Strongest cleanup and sharpening — watch the self-QC readouts.",
  fidelity:
    "Maximum fidelity. Runs at delivery resolution with the lightest grain — for professionals."
};

const WASH_HINT: Record<WashModel, string> = {
  qwen: "The proven default.",
  zimage: "An alternative family. Verify on your own material first.",
  "qwen+zimage": "Both models blended 50/50."
};

const METADATA_HINT: Record<MetadataMode, string> = {
  device: "Writes a coherent device EXIF block on the output.",
  minimal: "Ships with the minimum viable tag set."
};

const NAME_LABEL: Record<NameStyle, string> = {
  "settings-code": "Settings code",
  "photo-style": "Photo style",
  original: "Original",
  custom: "Custom"
};

function initialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const saved = localStorage.getItem("resmarke:theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function RemintApp() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const seqRef = useRef(0);
  const queueRef = useRef<QueueItem[]>([]);
  const runRef = useRef<(() => void) | null>(null);

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
  const [copied, setCopied] = useState(false);
  const [batch, setBatch] = useState({ done: 0, total: 0 });

  const [compare, setCompare] = useState<CompareMode>("split");
  const [splitPos, setSplitPos] = useState(50);
  const [pixelView, setPixelView] = useState(false);

  /* ---- Pipeline. Config A is the boot state (see applyConfigA). ---- */
  const [mode, setMode] = useState<PipelineMode>("sequence");

  // Stage 1 — DS ReMint V8.9 (identical option set to the frozen engine).
  const [washModel, setWashModel] = useState<WashModel>("qwen");
  const [strength, setStrength] = useState<Strength>("deep");
  const [engineMode, setEngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [metadataMode, setMetadataMode] = useState<MetadataMode>("device");
  const [deviceExif, setDeviceExif] = useState(true);
  const [outputTarget, setOutputTarget] = useState<number | null>(null);
  // Stage-1 codec (Config 2B lever) — defaults are the frozen engine values.
  const [stageJpegQ, setStageJpegQ] = useState(92);
  const [stageJpegS, setStageJpegS] = useState<"4:2:0" | "4:2:2" | "4:4:4">("4:2:0");
  const [nameStyle, setNameStyle] = useState<NameStyle>("settings-code");
  const [nameCustom, setNameCustom] = useState("");

  // Stage 2 — Quality Finish.
  const [qfPreset, setQfPreset] = useState<QfPreset>("strong");
  const [qfScale, setQfScale] = useState(1);
  const [wallClean, setWallClean] = useState(true);
  const [finishMode, setFinishMode] = useState<FinishRouting>("adaptive");
  // Pro tuning — multipliers over the preset's calibrated gains. 1.00 = preset
  // default; the worker clamps every value to its own accepted range.
  const [tuneDither, setTuneDither] = useState(1);
  const [tuneSmooth, setTuneSmooth] = useState(1.25);
  const [tuneSharpen, setTuneSharpen] = useState(1);
  const tuned = tuneDither !== 1 || tuneSmooth !== 1 || tuneSharpen !== 1;

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
    document.title = "/REMINT — Coherent Pro + Quality Finish";
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
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  // Cmd/Ctrl+Enter runs the queue from anywhere on the page.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        runRef.current?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1400);
    return () => window.clearTimeout(timer);
  }, [copied]);

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
      metadataMode,
      ...(outputTarget != null ? { outputTarget } : {}),
      // Config 2B lever — only serialized when non-default so Config A /
      // Config 1A settings hashes stay byte-stable with earlier exports.
      ...(stageJpegQ !== 92 || stageJpegS !== "4:2:0"
        ? { jpegQuality: stageJpegQ, jpegSubsampling: stageJpegS }
        : {})
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
     the whole canonical object, so identical settings on either page produce
     an identical code. */
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
    finishMode === "adaptive" &&
    outputTarget === null &&
    stageJpegQ === 92 &&
    stageJpegS === "4:2:0";

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
    setOutputTarget(null);
    setStageJpegQ(92);
    setStageJpegS("4:2:0");
  }

  // ReMint 1.01 — Config A with exactly one production variable moved:
  // delivery long edge 1250 -> 1800. The wash process cap remains 1536.
  const remint101Active =
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
    finishMode === "adaptive" &&
    outputTarget === 1800 &&
    stageJpegQ === 92 &&
    stageJpegS === "4:2:0";

  function applyRemint101() {
    applyConfigA();
    setOutputTarget(1800);
  }

  // Config 1A — the V8 cross-wash test tuple: every Config A lever unchanged
  // except the wash model swaps to the Qwen + Z-Image blend (the runtime
  // lever that targets the fingerprint-swap failure on night content).
  // Exactly ONE variable moves vs Config A, so the next test is a clean A/B.
  const config1AActive =
    mode === "sequence" &&
    washModel === "qwen+zimage" &&
    strength === "deep" &&
    engineMode === "adaptive" &&
    qfPreset === "strong" &&
    qfScale <= 1.001 &&
    Math.abs(tuneSmooth - 1.25) < 0.001 &&
    Math.abs(tuneDither - 1) < 0.001 &&
    Math.abs(tuneSharpen - 1) < 0.001 &&
    wallClean &&
    finishMode === "adaptive" &&
    outputTarget === null;

  function applyConfig1A() {
    setMode("sequence");
    setWashModel("qwen+zimage");
    setStrength("deep");
    setEngineMode("adaptive");
    setQfPreset("strong");
    setQfScale(1);
    setTuneSmooth(1.25);
    setTuneDither(1);
    setTuneSharpen(1);
    setWallClean(true);
    setFinishMode("adaptive");
    setOutputTarget(null);
    setStageJpegQ(92);
    setStageJpegS("4:2:0");
  }

  // Config 2B — stage-one codec variant: every Config A lever unchanged,
  // the stage-1 encode moves q92 4:2:0 -> Q97 4:4:4 at the SAME lattice
  // (targets the O2→O3 codec transition flagged by the V10 attribution plan).
  // ONE variable moved vs Config A. Detection-coupled (V4's q97 warning).
  const config2BActive =
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
    finishMode === "adaptive" &&
    outputTarget === null &&
    stageJpegQ === 97 &&
    stageJpegS === "4:4:4";

  function applyConfig2B() {
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
    setOutputTarget(null);
    setStageJpegQ(97);
    setStageJpegS("4:4:4");
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(settingsCode);
      setCopied(true);
    } catch {
      setNotice(`Settings code: ${settingsCode}`);
    }
  }

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

  /* Single-item processor. The batch run, Re-run all and the per-item re-run
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
    setBatch({ done: 0, total: items.length });
    let ok = 0;
    let failed = 0;

    for (const [index, item] of items.entries()) {
      try {
        await processItem(item, index + 1, items.length);
        ok += 1;
      } catch {
        failed += 1;
      }
      setBatch({ done: index + 1, total: items.length });
    }

    setRunning(false);
    setBatch({ done: 0, total: 0 });
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

  // Keeps the keyboard shortcut in sync without re-binding the listener.
  runRef.current = canRun ? runQueue : null;

  /* Re-run every image in the queue with the settings currently on screen —
     completed ones included. Each is a brand-new job and bills a fresh unit
     cost. */
  function rerunAll() {
    if (running || zipBusy || !queue.length) return;
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
    const base = raw.replace(/[<>:"/\\|?*\s]+/g, "-").slice(0, 90) || "image";
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
        {/* ---------- topbar ---------- */}
        <header className="rx-top">
          <div className="rx-brand">
            <span className="rx-brand-mark">
              <Sparkles size={15} aria-hidden="true" />
            </span>
            <span className="rx-brand-text">
              <b>/REMINT</b>
              <span>Coherent Pro · Quality Finish</span>
            </span>
          </div>

          <div className="rx-chain" aria-label="Active pipeline">
            <span className={`rx-chain-node${runsRemint ? " is-on" : ""}`}>
              {runsRemint ? <Check size={11} aria-hidden="true" /> : null}
              Remint
            </span>
            <span className="rx-chain-arrow" aria-hidden="true">
              <ArrowRight size={12} />
            </span>
            <span className={`rx-chain-node is-two${runsFinish ? " is-on" : ""}`}>
              {runsFinish ? <Check size={11} aria-hidden="true" /> : null}
              Quality Finish
            </span>
          </div>

          <span className="rx-top-spacer" />

          <div className="rx-top-right">
            {/* The settings-code is the delivered filename — keep it visible
                and one click from the clipboard. */}
            <button
              className={`rx-code-chip${copied ? " is-copied" : ""}`}
              type="button"
              title="Settings code — the delivered filename. Click to copy."
              onClick={() => void copyCode()}
            >
              {copied ? (
                <Check size={12} aria-hidden="true" />
              ) : (
                <Copy size={12} aria-hidden="true" />
              )}
              <code>{settingsCode}</code>
            </button>

            <span className="rx-credits" title="Credit balance">
              <Wallet size={13} aria-hidden="true" />
              <b>{credits.privacyCredits}</b>
            </span>

            {showAuth ? (
              <details className="rx-pop" open={authMode === "update"}>
                <summary className="rx-pop-trigger">
                  <UserRound size={14} aria-hidden="true" /> Sign in
                </summary>
                <div className="rx-pop-panel">
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
                  {authStatus ? <p className="rx-pop-status">{authStatus}</p> : null}
                </div>
              </details>
            ) : hasSupabaseConfig && userId ? (
              <details className="rx-pop">
                <summary className="rx-pop-trigger">
                  <UserRound size={14} aria-hidden="true" />
                  {userEmail || "Account"}
                </summary>
                <div className="rx-pop-panel">
                  <div className="rx-row">
                    <span>Credits</span>
                    <b>{credits.privacyCredits}</b>
                  </div>
                  <div className="rx-row">
                    <span>Re-Mint Max</span>
                    <b>{credits.deepCleanCredits}</b>
                  </div>
                  {isAdmin ? <span className="rx-tag is-on">Developer admin</span> : null}
                  <button className="rx-btn rx-btn-block" type="button" onClick={signOut}>
                    <LogOut size={14} aria-hidden="true" /> Sign out
                  </button>
                </div>
              </details>
            ) : null}

            <button
              className="rx-icon-btn"
              type="button"
              aria-label="Toggle theme"
              title={theme === "dark" ? "Switch to light" : "Switch to dark"}
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>
        </header>

        <div className="rx-work">
          {/* ---------- queue rail ---------- */}
          <section className="rx-pane rx-pane-queue" aria-label="Image queue">
            <div className="rx-rail-head">
              <span className="rx-rail-title">Queue</span>
              <span className={`rx-count${running ? " is-run" : ""}`}>
                {running && batch.total
                  ? `${batch.done}/${batch.total}`
                  : `${queue.length}/${MAX_QUEUE}`}
              </span>
              <span className="rx-top-spacer" />
              <button
                className="rx-btn rx-btn-sm"
                type="button"
                onClick={openPicker}
                disabled={running || queue.length >= MAX_QUEUE}
              >
                <Upload size={13} aria-hidden="true" /> Add
              </button>
            </div>

            <div className="rx-pane-scroll">
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
                <Upload size={17} aria-hidden="true" />
                <b>Drop images</b>
                <span>JPEG · PNG · WebP · up to 25 MB each</span>
              </div>

              {queue.length ? (
                <div className="rx-queue">
                  {queue.map((item) => (
                    <div
                      key={item.id}
                      className={`rx-qitem${item.id === active?.id ? " is-active" : ""}${
                        item.id === draggedId ? " is-dragging" : ""
                      }${item.status === "failed" ? " is-fail" : ""}`}
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
                      <span className="rx-qthumb">
                        <img src={item.previewUrl} alt="" />
                      </span>
                      <span className="rx-qbody">
                        <span className="rx-qname">{item.file.name}</span>
                        <span className="rx-qmeta">
                          <i className={`rx-dot ${statusDotClass(item.status)}`} />
                          {statusLabel(item.status)}
                          {item.width ? ` · ${item.width}×${item.height}` : ""}
                        </span>
                        {/* Per-item failure text, so a bad image in a batch is
                            readable without selecting it. */}
                        {item.status === "failed" && item.error ? (
                          <span className="rx-qerr">{item.error}</span>
                        ) : null}
                      </span>
                      <span className="rx-qactions">
                        {item.status === "completed" ? (
                          <>
                            <button
                              className="rx-qact"
                              type="button"
                              title={`Re-run this image with the current settings (${unitCost} credits)`}
                              aria-label="Re-run this image"
                              disabled={running || zipBusy}
                              onClick={(event) => {
                                event.stopPropagation();
                                void rerunItem(item);
                              }}
                            >
                              <RefreshCw size={14} />
                            </button>
                            <button
                              className="rx-qact"
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
                          className="rx-qact is-danger"
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
                        <span className="rx-grip" aria-hidden="true">
                          <GripVertical size={13} />
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            {queue.length ? (
              <div className="rx-rail-foot">
                <div className="rx-foot-split">
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
                    ZIP ({completed.length})
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
                </div>
                <button
                  className="rx-btn rx-btn-block"
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
          <section className="rx-pane rx-pane-stage" aria-label="Viewer">
            <div className="rx-stage-bar">
              {active ? (
                <div className="rx-stage-file">
                  <b>{active.file.name}</b>
                  <span>
                    {(active.file.size / 1_000_000).toFixed(2)} MB
                    {active.width ? ` · ${active.width}×${active.height}` : ""}
                  </span>
                </div>
              ) : (
                <span className="rx-rail-title">Viewer</span>
              )}

              <span className="rx-top-spacer" />

              {resultUrl ? (
                <div
                  className="rx-seg"
                  style={{ width: 210 }}
                  role="radiogroup"
                  aria-label="Compare mode"
                >
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
                className="rx-icon-btn"
                type="button"
                title={pixelView ? "Fit to view" : "View at 1:1 pixels"}
                aria-label="Toggle pixel view"
                disabled={!active}
                onClick={() => setPixelView((current) => !current)}
              >
                {pixelView ? <Scan size={15} /> : <Maximize2 size={15} />}
              </button>
            </div>

            <div className={`rx-stage-body${pixelView ? " is-pixel" : ""}`}>
              {!active ? (
                <div className="rx-empty">
                  <Images size={30} aria-hidden="true" />
                  <h2>Nothing loaded</h2>
                  <p>
                    Add images to the queue and run. Config A is already applied, so the only
                    decision left is what to drop in. Results appear here with a split compare
                    against the original.
                  </p>
                  <button className="rx-btn rx-btn-primary" type="button" onClick={openPicker}>
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

            <div className="rx-stage-foot">
              {notice ? (
                <span style={{ color: "var(--rx-warn)" }}>{notice}</span>
              ) : active?.error ? (
                <span style={{ color: "var(--rx-danger)" }}>{active.error}</span>
              ) : (
                <span>
                  {status ||
                    (hasSupabaseConfig
                      ? "Ready. Config A is applied — drop images and run."
                      : "Supabase env vars are not set — jobs cannot be dispatched.")}
                </span>
              )}
            </div>
          </section>

          {/* ---------- control rail ---------- */}
          <section className="rx-pane rx-pane-ctl" aria-label="Pipeline controls">
            <div className="rx-rail-head">
              <SlidersHorizontal size={13} aria-hidden="true" />
              <span className="rx-rail-title">Pipeline</span>
              <span className="rx-top-spacer" />
              <span className="rx-count">{unitCost} cr / image</span>
            </div>

            <div className="rx-pane-scroll">
              <div className="rx-ctl">
                {/* Config A — one tap restores the proven all-clear tuple. */}
                <button
                  type="button"
                  className={`rx-preset${configAActive ? " is-active" : ""}`}
                  disabled={running}
                  onClick={applyConfigA}
                  title="Deep · Strong · Native · Smoothing 1.25× · Wall smoothing on · Adaptive"
                >
                  <span className="rx-preset-mark">
                    <Zap size={15} aria-hidden="true" />
                  </span>
                  <span className="rx-preset-text">
                    <b>Config A</b>
                    <span>Deep · Strong · Native · S1.25 · Wall clean</span>
                  </span>
                  <span className="rx-preset-state">
                    {configAActive ? (
                      <>
                        <Check size={12} aria-hidden="true" /> Active
                      </>
                    ) : (
                      "Restore"
                    )}
                  </span>
                </button>

                {/* ReMint 1.01 — Config A with delivery moved to 1800px. */}
                <button
                  type="button"
                  className={`rx-preset${remint101Active ? " is-active" : ""}`}
                  disabled={running}
                  onClick={() => (remint101Active ? applyConfigA() : applyRemint101())}
                  title="ReMint 1.01 — 1800px delivery · rest identical to Config A"
                >
                  <span className="rx-preset-mark">
                    <Maximize2 size={15} aria-hidden="true" />
                  </span>
                  <span className="rx-preset-text">
                    <b>ReMint 1.01</b>
                    <span>1800px delivery · rest identical to Config A</span>
                  </span>
                  <span
                    className={`rx-toggle-pill${remint101Active ? " is-on" : ""}`}
                    role="switch"
                    aria-checked={remint101Active}
                    aria-label="ReMint 1.01 applied"
                  >
                    <span className="rx-toggle-pill-knob" />
                    <span className="rx-toggle-pill-label">
                      {remint101Active ? "ON" : "OFF"}
                    </span>
                  </span>
                </button>

                {/* Config 1A — the V8 cross-wash test preset. A simple toggle:
                    ON applies the tuple, tapping again returns to Config A. */}
                <button
                  type="button"
                  className={`rx-preset rx-preset-1a${config1AActive ? " is-active" : ""}`}
                  disabled={running}
                  onClick={() => (config1AActive ? applyConfigA() : applyConfig1A())}
                  title="Config 1A — Qwen+Z-Image wash · rest identical to Config A"
                >
                  <span className="rx-preset-mark">
                    <Droplets size={15} aria-hidden="true" />
                  </span>
                  <span className="rx-preset-text">
                    <b>Config 1A</b>
                    <span>Qwen+Z-Image wash · Deep · Strong · S1.25</span>
                  </span>
                  <span
                    className={`rx-toggle-pill${config1AActive ? " is-on" : ""}`}
                    role="switch"
                    aria-checked={config1AActive}
                    aria-label="Config 1A applied"
                  >
                    <span className="rx-toggle-pill-knob" />
                    <span className="rx-toggle-pill-label">
                      {config1AActive ? "ON" : "OFF"}
                    </span>
                  </span>
                </button>

                {/* Config 2B — stage-one codec variant: Q97 4:4:4 at the SAME
                    lattice. One variable moved vs Config A (O2→O3 offender). */}
                <button
                  type="button"
                  className={`rx-preset rx-preset-2b${config2BActive ? " is-active" : ""}`}
                  disabled={running}
                  onClick={() => (config2BActive ? applyConfigA() : applyConfig2B())}
                  title="Config 2B — stage-1 codec Q97 4:4:4 · rest identical to Config A"
                >
                  <span className="rx-preset-mark">
                    <Film size={15} aria-hidden="true" />
                  </span>
                  <span className="rx-preset-text">
                    <b>Config 2B</b>
                    <span>Stage-1 codec Q97 4:4:4 · Deep · Strong · S1.25</span>
                  </span>
                  <span
                    className={`rx-toggle-pill${config2BActive ? " is-on" : ""}`}
                    role="switch"
                    aria-checked={config2BActive}
                    aria-label="Config 2B applied"
                  >
                    <span className="rx-toggle-pill-knob" />
                    <span className="rx-toggle-pill-label">
                      {config2BActive ? "ON" : "OFF"}
                    </span>
                  </span>
                </button>

                {/* mode picker */}
                <div className="rx-modes" role="radiogroup" aria-label="Pipeline mode">
                  <ModeCard
                    active={mode === "sequence"}
                    disabled={running}
                    title="Remint + Finish"
                    detail="The complete flow. Remint, then the HD finish — one job, end to end."
                    cost={
                      COST_REMINT + (engineMode === "adaptive" ? COST_ADAPTIVE : 0) + COST_FINISH
                    }
                    onClick={() => setMode("sequence")}
                  />
                  <ModeCard
                    active={mode === "remint"}
                    disabled={running}
                    title="Remint"
                    detail="The core pass alone. A clean, naturalized file up to 1250px."
                    cost={COST_REMINT + (engineMode === "adaptive" ? COST_ADAPTIVE : 0)}
                    onClick={() => setMode("remint")}
                  />
                  <ModeCard
                    active={mode === "finish"}
                    disabled={running}
                    title="Quality Finish"
                    detail="Polish a file you already have. Detail restored, grain kept — CPU only."
                    cost={COST_FINISH}
                    onClick={() => setMode("finish")}
                  />
                </div>

                {mode === "finish" ? (
                  <div className="rx-note">
                    <Info size={13} aria-hidden="true" />
                    <span>
                      Quality Finish alone — it polishes whatever you give it and never runs the
                      remint stage.
                    </span>
                  </div>
                ) : null}

                {/* ---- stage 1 ---- */}
                {runsRemint ? (
                  <div className="rx-card">
                    <div className="rx-card-head">
                      <span className="rx-card-num">1</span>
                      <span className="rx-card-title">
                        <b>Remint · V8.9</b>
                        <span>The coherent camera pass — GPU</span>
                      </span>
                      <span className="rx-tag is-on">GPU</span>
                    </div>

                    <div className="rx-card-body">
                      <div className="rx-stats">
                        <Stat label="Wash" value={WASH_LABEL[washModel]} />
                        <Stat label="Camera" value={`${strength} model`} />
                        <Stat label="Resample" value="1× · ≤1250px" />
                        <Stat
                          label="Engine"
                          value={engineMode === "adaptive" ? "up to 3 passes" : "1 pass"}
                        />
                      </div>

                      <div className="rx-field">
                        <span className="rx-label">Strength</span>
                        <div className="rx-seg" role="radiogroup" aria-label="V8.9 strength">
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
                        <p className="rx-hint">{STRENGTH_HINT[strength]}</p>
                      </div>

                      <div className="rx-field">
                        <span className="rx-label">Engine</span>
                        <div className="rx-seg" role="radiogroup" aria-label="V8.9 engine">
                          {(["adaptive", "template"] as CxRemintEngineMode[]).map((value) => (
                            <button
                              key={value}
                              type="button"
                              role="radio"
                              aria-checked={engineMode === value}
                              className={engineMode === value ? "is-active" : ""}
                              disabled={running}
                              onClick={() => setEngineMode(value)}
                            >
                              {value === "adaptive" ? "Adaptive" : "Template"}
                            </button>
                          ))}
                        </div>
                        <p className="rx-hint">
                          {engineMode === "adaptive"
                            ? `Tries the lightest settings first and ships the least destructive result that meets the quality bar. +${COST_ADAPTIVE} credits.`
                            : "One deterministic pass at the chosen strength."}
                        </p>
                      </div>
                    </div>

                    <details className="rx-disc">
                      <summary>
                        <SlidersHorizontal size={13} aria-hidden="true" /> Expert · wash, metadata,
                        naming
                        <ChevronDown className="rx-chev" size={14} aria-hidden="true" />
                      </summary>
                      <div className="rx-disc-body">
                        <div className="rx-field">
                          <span className="rx-label">Wash model</span>
                          <div className="rx-seg" role="radiogroup" aria-label="Wash model">
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
                          <p className="rx-hint">{WASH_HINT[washModel]}</p>
                        </div>

                        <div className="rx-field">
                          <span className="rx-label">Metadata</span>
                          <div className="rx-seg" role="radiogroup" aria-label="Metadata mode">
                            {(["device", "minimal"] as MetadataMode[]).map((value) => (
                              <button
                                key={value}
                                type="button"
                                role="radio"
                                aria-checked={metadataMode === value}
                                className={metadataMode === value ? "is-active" : ""}
                                disabled={running}
                                onClick={() => setMetadataMode(value)}
                              >
                                {value === "device" ? "Device EXIF" : "Minimal"}
                              </button>
                            ))}
                          </div>
                          <p className="rx-hint">{METADATA_HINT[metadataMode]}</p>
                        </div>

                        <label className="rx-switch">
                          <input
                            type="checkbox"
                            checked={deviceExif}
                            disabled={running}
                            onChange={(event) => setDeviceExif(event.target.checked)}
                          />
                          <span className="rx-switch-track" aria-hidden="true">
                            <span className="rx-switch-thumb" />
                          </span>
                          <span>Coherent device EXIF</span>
                        </label>

                        <div className="rx-field">
                          <span className="rx-label">Output filename</span>
                          <div
                            className="rx-seg rx-seg-wrap"
                            role="radiogroup"
                            aria-label="Filename style"
                          >
                            {(
                              ["settings-code", "photo-style", "original", "custom"] as NameStyle[]
                            ).map((value) => (
                              <button
                                key={value}
                                type="button"
                                role="radio"
                                aria-checked={nameStyle === value}
                                className={nameStyle === value ? "is-active" : ""}
                                disabled={running}
                                onClick={() => setNameStyle(value)}
                              >
                                {NAME_LABEL[value]}
                              </button>
                            ))}
                          </div>
                          {nameStyle === "custom" ? (
                            <>
                              <input
                                className="rx-input"
                                value={nameCustom}
                                disabled={running}
                                placeholder="my-photo"
                                onChange={(event) => setNameCustom(event.target.value)}
                              />
                              <p className="rx-hint">
                                First image keeps the exact name; each next image adds -2, -3…
                              </p>
                            </>
                          ) : null}
                          {nameStyle === "settings-code" ? (
                            <p className="rx-hint">
                              The filename encodes the exact settings used — share it back for a
                              full settings → performance loop.
                              <br />
                              <code>{settingsCode}</code>
                            </p>
                          ) : null}
                          {nameStyle === "photo-style" ? (
                            <p className="rx-hint">Camera-style names, IMG_0001 upward.</p>
                          ) : null}
                          {nameStyle === "original" ? (
                            <p className="rx-hint">Keeps the name of the file you dropped in.</p>
                          ) : null}
                        </div>
                      </div>
                    </details>
                  </div>
                ) : null}

                {/* ---- stage 2 ---- */}
                {runsFinish ? (
                  <div className="rx-card">
                    <div className="rx-card-head">
                      <span className="rx-card-num is-two">{runsRemint ? "2" : "1"}</span>
                      <span className="rx-card-title">
                        <b>Quality Finish</b>
                        <span>Non-AI restoration · grain kept, crispness restored</span>
                      </span>
                      <span className="rx-tag is-two">CPU</span>
                    </div>

                    <div className="rx-card-body">
                      <div className="rx-stats">
                        <Stat label="Preset" value={qfReport?.preset ?? qfPreset} />
                        <Stat
                          label="Delivery"
                          value={
                            qfReport
                              ? qfReport.scale
                                ? `${qfReport.scale.toFixed(2)}× HD`
                                : "native size"
                              : qfScale <= 1.001
                                ? "native size"
                                : `${qfScale.toFixed(2)}× HD`
                          }
                        />
                        <Stat label="Encode" value={encodeLabel(qfReport)} />
                        <Stat
                          label="Self-QC"
                          value={
                            qfReport
                              ? qfReport.applied
                                ? "passed"
                                : "input shipped"
                              : "ships input on fail"
                          }
                        />
                      </div>

                      <div className="rx-field">
                        <span className="rx-label">Restoration strength</span>
                        <div
                          className="rx-seg rx-seg-2"
                          role="radiogroup"
                          aria-label="Finish preset"
                        >
                          {(["conservative", "standard", "strong", "fidelity"] as QfPreset[]).map(
                            (value) => (
                              <button
                                key={value}
                                type="button"
                                role="radio"
                                aria-checked={qfPreset === value}
                                className={qfPreset === value ? "is-active" : ""}
                                disabled={running}
                                onClick={() => setQfPreset(value)}
                              >
                                {value === "fidelity"
                                  ? "Fidelity HD"
                                  : value[0].toUpperCase() + value.slice(1)}
                              </button>
                            )
                          )}
                        </div>
                        <p className="rx-hint">{QF_HINT[qfPreset]}</p>
                      </div>

                      <div className="rx-field">
                        <span className="rx-label">
                          Delivery size
                          <em>{qfScale <= 1.001 ? "native" : `${qfScale.toFixed(2)}×`}</em>
                        </span>
                        <div
                          className="rx-seg rx-seg-2"
                          role="radiogroup"
                          aria-label="Delivery size"
                        >
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

                      <label className="rx-switch">
                        <input
                          type="checkbox"
                          checked={wallClean}
                          disabled={running}
                          onChange={(event) => setWallClean(event.target.checked)}
                        />
                        <span className="rx-switch-track" aria-hidden="true">
                          <span className="rx-switch-thumb" />
                        </span>
                        <span>Wall smoothing · Mobile Clean</span>
                      </label>
                      <p className="rx-hint">
                        Auto-smooths rendered walls while keeping structure. Turn off to A/B
                        compare — the report still measures what it would have done.
                      </p>

                      {/* Pro tuning — multipliers over the preset's calibrated gains. */}
                      <div className="rx-field">
                        <span className="rx-label">
                          Pro tuning
                          {tuned ? (
                            <button
                              className="rx-reset"
                              type="button"
                              disabled={running}
                              onClick={() => {
                                setTuneDither(1);
                                setTuneSmooth(1);
                                setTuneSharpen(1);
                              }}
                            >
                              Reset to preset
                            </button>
                          ) : null}
                        </span>
                        <TuneRow
                          name="Gradient dither"
                          min={0}
                          max={1.5}
                          value={tuneDither}
                          disabled={running}
                          onChange={setTuneDither}
                        />
                        <TuneRow
                          name="Smoothing"
                          min={0.5}
                          max={1.5}
                          value={tuneSmooth}
                          disabled={running}
                          onChange={setTuneSmooth}
                        />
                        <TuneRow
                          name="Sharpening"
                          min={0}
                          max={1.5}
                          value={tuneSharpen}
                          disabled={running}
                          onChange={setTuneSharpen}
                        />
                        <p className="rx-hint">
                          1.00 = preset default. Each slider is a multiplier over the preset's
                          calibrated gain, so leave them at 1.00 unless a specific image asks for
                          more or less.
                        </p>
                      </div>

                      {mode === "sequence" ? (
                        <div className="rx-field">
                          <span className="rx-label">Finish routing</span>
                          <div
                            className="rx-seg rx-seg-2"
                            role="radiogroup"
                            aria-label="Finish routing"
                          >
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
                          <p className="rx-hint">
                            {finishMode === "adaptive"
                              ? "Builds more than one finish candidate and ships the strongest one that meets the quality bar."
                              : "Runs exactly the preset selected above, with no candidate selection."}
                          </p>
                        </div>
                      ) : null}
                    </div>

                    <details className="rx-disc">
                      <summary>
                        <Gauge size={13} aria-hidden="true" /> Expert · exact enlargement factor
                        <ChevronDown className="rx-chev" size={14} aria-hidden="true" />
                      </summary>
                      <div className="rx-disc-body">
                        <div className="rx-field">
                          <span className="rx-label">
                            Enlargement
                            <em>{qfScale <= 1.001 ? "native" : `${qfScale.toFixed(2)}×`}</em>
                          </span>
                          <input
                            className="rx-range"
                            type="range"
                            min={1}
                            max={2}
                            step={0.05}
                            value={qfScale}
                            disabled={running}
                            aria-label="Exact enlargement factor"
                            onChange={(event) => setQfScale(Number(event.target.value))}
                          />
                          <div className="rx-range-ends">
                            <span>Native (quality floor)</span>
                            <span>2× (~2500px)</span>
                          </div>
                          <p className="rx-hint">
                            The finisher accepts any factor from 1.00 to 2.00. Native delivery is
                            always the quality floor; enlargement is the HD path and adds perceived
                            resolution only when the finisher's self-QC passes.
                          </p>
                        </div>
                      </div>
                    </details>
                  </div>
                ) : null}

                {/* ---- result / QC — collapsible, so the rail stops growing ---- */}
                {active?.job?.status === "completed" ? (
                  <details className="rx-card" open>
                    <summary className="rx-card-head">
                      <span className="rx-card-num">
                        <Check size={11} aria-hidden="true" />
                      </span>
                      <span className="rx-card-title">
                        <b>Result</b>
                        <span>{active.file.name}</span>
                      </span>
                      <ChevronDown className="rx-chev" size={14} aria-hidden="true" />
                    </summary>
                    <div className="rx-card-body">
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
                          className={`rx-risk rx-risk-${
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
                    </div>
                  </details>
                ) : null}
              </div>
            </div>

            {/* ---- run bar ---- */}
            <div className="rx-run">
              {hasSupabaseConfig && !userId ? (
                <div className="rx-note is-warn">
                  <Info size={13} aria-hidden="true" />
                  <span>Sign in to dispatch jobs.</span>
                </div>
              ) : pending.length > 0 && credits.privacyCredits < totalCost ? (
                <div className="rx-note is-warn">
                  <Info size={13} aria-hidden="true" />
                  <span>
                    This queue needs {totalCost} credits; you have {credits.privacyCredits}.
                  </span>
                </div>
              ) : null}

              {running && batch.total ? (
                <div className="rx-progress" aria-hidden="true">
                  <span style={{ width: `${(batch.done / batch.total) * 100}%` }} />
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
                      : `Run ${pending.length} ${pending.length === 1 ? "image" : "images"}`}
                    <kbd className="rx-kbd">⌘⏎</kbd>
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
      className={`rx-frame${split ? " rx-compare" : ""}`}
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
          <div className="rx-split-top" style={{ clipPath: `inset(0 0 0 ${splitPos}%)` }}>
            <img src={resultUrl} alt="Processed result" draggable={false} />
          </div>
          <div className="rx-split-handle" style={{ left: `${splitPos}%` }}>
            <span className="rx-split-knob">
              <GripVertical size={14} aria-hidden="true" />
            </span>
          </div>
          <span className="rx-split-tag is-left">Original</span>
          <span className="rx-split-tag is-right">Processed</span>
        </>
      ) : null}

      {busy ? (
        <div className="rx-veil">
          <Loader2 className="rx-spin" size={26} aria-hidden="true" />
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
      className={`rx-mode${active ? " is-active" : ""}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="rx-mode-radio" aria-hidden="true" />
      <span className="rx-mode-text">
        <b>{title}</b>
        <span>{detail}</span>
      </span>
      <span className="rx-cost">{cost} cr</span>
    </button>
  );
}

function TuneRow({
  name,
  min,
  max,
  value,
  disabled,
  onChange
}: {
  name: string;
  min: number;
  max: number;
  value: number;
  disabled: boolean;
  onChange: (next: number) => void;
}) {
  return (
    <div className="rx-tune">
      <span className="rx-tune-name">{name}</span>
      <input
        className="rx-range"
        type="range"
        aria-label={name}
        min={min}
        max={max}
        step={0.05}
        value={value}
        disabled={disabled}
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
  // different one. The nested slot is always the finisher's, so accept it
  // even in its short "no candidate applied" form, which carries no `mode`.
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
