import {
  Check,
  ChevronDown,
  ClipboardCopy,
  Copy,
  Download,
  ExternalLink,
  FileJson,
  Film,
  FlaskConical,
  Gauge,
  Image as ImageIcon,
  KeyRound,
  Loader2,
  LogOut,
  Mail,
  Moon,
  Play,
  RefreshCw,
  ScanSearch,
  SlidersHorizontal,
  Sun,
  Trash2,
  Upload,
  UserRound,
  Wallet,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { config, hasSupabaseConfig } from "./lib/config";
import {
  cancelDeepCleanJob,
  createDeepCleanJob,
  dispatchDeepCleanJob,
  getDeepCleanJob,
  uploadDeepCleanInput,
  type DeepCleanJob
} from "./lib/deepcleanClient";
import {
  appendDetectionOnlyLedgerRow,
  appendGradeLedgerRow,
  compactGradeReport,
  exportDetectionOnlyLedgerCsv,
  exportDetectionOnlyLedgerJsonl,
  exportGradeLedgerCsv,
  exportGradeLedgerJsonl,
  importGradeLedger,
  loadDetectionOnlyLedger,
  loadGradeLedger,
  topAiSources,
  workerReportProvenance,
  type DetectionOnlyLedgerRow,
  type GradeLedgerRow,
  type GradeMode,
  type GradeVerdict,
  type ModeGradePair,
  type NormalizedGrade
} from "./lib/gradeLedger";
import { getGradeSessionId, gradeImage, gradeOutputUrl } from "./lib/graderClient";
import {
  createCorpusRunIntent,
  fetchCorpusSnapshot,
  registerCorpusRun,
  type CorpusExperiment,
  type CorpusImage,
  type CorpusSnapshot
} from "./lib/corpusClient";
import { readLocalCredits, spendLocalPrivacyCredit, type CreditSnapshot } from "./lib/localCredits";
import {
  CAM1_PRESET_DEFINITION,
  PRESET_DEFINITIONS,
  TRANSFER_4D_1A_PRESET_DEFINITION,
  buildSettingsCode,
  configIdentity,
  is4dCam1,
  is4d1a,
  presetFromRequested,
  settingsForPreset,
  type PresetDefinition,
  type PresetId,
  type SettingsCodeInput
} from "./lib/settingsCode";
import { supabase } from "./lib/supabase";
import "./relab.css";

type Theme = "light" | "dark";
type QueueStatus =
  | "ready"
  | "preparing"
  | "uploading"
  | "queued"
  | "processing"
  | "grading"
  | "completed"
  | "failed";
type SortKey = "ai" | "delta" | "verdict" | "timestamp";
type AuthMode = "signin" | "signup";

type QueueItem = {
  id: string;
  file: File;
  previewUrl: string;
  width?: number;
  height?: number;
  status: QueueStatus;
  job?: DeepCleanJob;
  error?: string;
  ledgerId?: string;
  corpus?: {
    imageId: string;
    experimentId: string;
    intentId?: string;
    registrationStatus: "idle" | "intent" | "pending" | "registered" | "failed";
    registrationRunId?: string;
    registrationError?: string;
  };
};

const MAX_QUEUE = 20;
const MAX_BYTES = 25 * 1024 * 1024;
const UNIT_COST = 23;
const ACCEPTED = new Set(["image/jpeg", "image/png", "image/webp"]);
const SESSION_CAP_FALLBACK = 40;

const PRESETS: Record<PresetId, PresetDefinition> = {
  ...PRESET_DEFINITIONS,
  "4d-cam-1": CAM1_PRESET_DEFINITION,
  "4d-1a": TRANSFER_4D_1A_PRESET_DEFINITION,
};
const LAB_SEED_RE = /^lab-[a-z0-9]{1,32}$/;
const CAM1_LOCKED_SEEDS = new Set(["lab-ctla1", "lab-ctla2"]);

const VERDICT_RANK: Record<GradeVerdict, number> = {
  CLEAR: 0,
  NEAR: 1,
  BORDER: 2,
  FAIL: 3
};

function initialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const saved = localStorage.getItem("resmarke:theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const HIVE_GRADE_MODE: GradeMode = "real";

export default function RelabApp() {
  const fileInput = useRef<HTMLInputElement | null>(null);
  const importInput = useRef<HTMLInputElement | null>(null);
  const sequence = useRef(0);
  const queueRef = useRef<QueueItem[]>([]);

  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [activeId, setActiveId] = useState("");
  const [presetId, setPresetId] = useState<PresetId>("config-a");
  const [labSeed, setLabSeed] = useState("");
  const primaryMode = HIVE_GRADE_MODE;
  const [running, setRunning] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState("");
  const [notice, setNotice] = useState("");
  const [batch, setBatch] = useState({ done: 0, total: 0 });
  const [rows, setRows] = useState<GradeLedgerRow[]>(loadGradeLedger);
  const [detectionOnlyRows, setDetectionOnlyRows] =
    useState<DetectionOnlyLedgerRow[]>(loadDetectionOnlyLedger);
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortAscending, setSortAscending] = useState(false);
  const [copyState, setCopyState] = useState("");
  const [gradeStats, setGradeStats] = useState({
    grades: 0,
    cacheHits: 0,
    vendorCalls: 0,
    cap: SESSION_CAP_FALLBACK
  });
  const [corpusSnapshot, setCorpusSnapshot] = useState<CorpusSnapshot | null>(null);
  const [corpusPickerOpen, setCorpusPickerOpen] = useState(false);
  const [corpusExperimentId, setCorpusExperimentId] = useState("");
  const [corpusLoading, setCorpusLoading] = useState(false);

  const [credits, setCredits] = useState<CreditSnapshot>(() => readLocalCredits());
  const [userId, setUserId] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authStatus, setAuthStatus] = useState("");

  const preset = useMemo(() => {
    const next = structuredClone(PRESETS[presetId]);
    if (labSeed) next.remint.seed = labSeed;
    return next;
  }, [labSeed, presetId]);
  const settingsCode = useMemo(() => settingsCodeForPreset(preset), [preset]);
  const labSeedValid = !labSeed || LAB_SEED_RE.test(labSeed);
  const cam1SeedReady = presetId !== "4d-cam-1" || CAM1_LOCKED_SEEDS.has(labSeed);
  const transfer4d1aSeedReady = presetId !== "4d-1a" || CAM1_LOCKED_SEEDS.has(labSeed);
  const pending = queue.filter((item) => item.status !== "completed");
  const active = queue.find((item) => item.id === activeId) ?? queue[0] ?? null;
  const totalCost = pending.length * UNIT_COST;
  const canRun =
    pending.length > 0 &&
    !running &&
    !detecting &&
    hasSupabaseConfig &&
    !!userId &&
    labSeedValid &&
    cam1SeedReady &&
    transfer4d1aSeedReady &&
    credits.privacyCredits >= totalCost;

  const sortedRows = useMemo(() => {
    const direction = sortAscending ? 1 : -1;
    return [...rows].sort((left, right) => {
      if (sortKey === "timestamp") {
        return direction * left.timestamp.localeCompare(right.timestamp);
      }
      if (sortKey === "ai") {
        return direction * (left.remint_grade.ai_probability - right.remint_grade.ai_probability);
      }
      if (sortKey === "delta") return direction * (left.delta - right.delta);
      return direction * (VERDICT_RANK[left.verdict] - VERDICT_RANK[right.verdict]);
    });
  }, [rows, sortAscending, sortKey]);

  const auxiliaryModes = useMemo(() => {
    const modes = new Set<GradeMode>();
    for (const row of rows) {
      for (const mode of Object.keys(row.mode_results) as GradeMode[]) {
        if (mode !== row.mode) modes.add(mode);
      }
    }
    return (["sdxl", "flux_schnell", "real"] as GradeMode[]).filter((mode) => modes.has(mode));
  }, [rows]);

  const corpusExperiment = useMemo(
    () => corpusSnapshot?.experiments.find((experiment) => experiment.id === corpusExperimentId) ?? null,
    [corpusExperimentId, corpusSnapshot]
  );
  const corpusPickerImages = useMemo(() => {
    if (!corpusSnapshot || !corpusExperiment) return [];
    const imageIds = new Set(
      corpusSnapshot.members
        .filter((member) => member.corpus_set_id === corpusExperiment.corpus_set_id)
        .map((member) => member.corpus_image_id)
    );
    return corpusSnapshot.images.filter((image) => imageIds.has(image.id));
  }, [corpusExperiment, corpusSnapshot]);

  const rankedDetectionOnlyRows = useMemo(
    () =>
      [...detectionOnlyRows].sort(
        (left, right) =>
          left.grade.ai_probability - right.grade.ai_probability ||
          right.timestamp.localeCompare(left.timestamp)
      ),
    [detectionOnlyRows]
  );

  const activeDetectionOnlyResult = useMemo(
    () =>
      active
        ? [...detectionOnlyRows].reverse().find((row) => row.file_id === active.id) ?? null
        : null,
    [active, detectionOnlyRows]
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("resmarke:theme", theme);
  }, [theme]);

  useEffect(() => {
    document.title = "/RELAB — Remint Detection Lab";
  }, []);

  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  useEffect(
    () => () => queueRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl)),
    []
  );

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => {
      const user = data.session?.user;
      setUserId(user?.id ?? "");
      setUserEmail(user?.email ?? "");
      if (user) void refreshCredits(user.id);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      const user = session?.user;
      setUserId(user?.id ?? "");
      setUserEmail(user?.email ?? "");
      if (user) void refreshCredits(user.id);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!copyState) return;
    const timer = window.setTimeout(() => setCopyState(""), 1400);
    return () => window.clearTimeout(timer);
  }, [copyState]);

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

  async function submitAuth() {
    if (!supabase) return;
    const email = authEmail.trim();
    if (!email || !authPassword) return setAuthStatus("Enter an email and password.");
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
    setAuthStatus(
      error
        ? error.message
        : data.session
          ? "Account created. You are signed in."
          : "Account created. Confirm by email before signing in."
    );
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUserId("");
    setUserEmail("");
    setCredits(readLocalCredits());
  }

  async function spendCredits(amount: number) {
    if (!supabase || !userId) {
      let next = readLocalCredits();
      for (let index = 0; index < amount; index += 1) next = spendLocalPrivacyCredit();
      setCredits(next);
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

  function patchItem(id: string, patch: Partial<QueueItem>) {
    setQueue((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  function addFiles(files: File[]) {
    if (!files.length || running) return;
    const supported = files.filter(
      (file) => ACCEPTED.has(file.type) && file.size > 0 && file.size <= MAX_BYTES
    );
    const slots = Math.max(0, MAX_QUEUE - queue.length);
    const accepted = supported.slice(0, slots);
    if (!accepted.length) {
      setNotice(
        slots === 0
          ? `Queue full (maximum ${MAX_QUEUE}).`
          : "Use JPEG, PNG, or WebP files up to 25 MB."
      );
      return;
    }
    const added: QueueItem[] = accepted.map((file) => ({
      id: `og-${Date.now()}-${sequence.current++}`,
      file,
      previewUrl: URL.createObjectURL(file),
      status: "ready"
    }));
    setQueue((current) => [...current, ...added]);
    if (!activeId) setActiveId(added[0].id);
    for (const item of added) {
      void createImageBitmap(item.file)
        .then((bitmap) => {
          patchItem(item.id, { width: bitmap.width, height: bitmap.height });
          bitmap.close();
        })
        .catch(() => undefined);
    }
    const skipped = files.length - accepted.length;
    setNotice(skipped ? `${skipped} file${skipped === 1 ? "" : "s"} skipped.` : "");
  }

  async function openCorpusPicker() {
    if (!userId) {
      setNotice("Sign in before loading a fixed-corpus image.");
      return;
    }
    setCorpusPickerOpen(true);
    setCorpusLoading(true);
    try {
      const next = await fetchCorpusSnapshot();
      setCorpusSnapshot(next);
      setCorpusExperimentId((current) => current || next.experiments[0]?.id || "");
      if (!next.experiments.length) setNotice("Create a locked corpus set and experiment on /corpus first.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load the corpus picker.");
    } finally {
      setCorpusLoading(false);
    }
  }

  async function addCorpusImage(image: CorpusImage, experiment: CorpusExperiment) {
    if (running || queue.length >= MAX_QUEUE || !image.signed_url) return;
    setCorpusLoading(true);
    try {
      const response = await fetch(image.signed_url, { credentials: "omit" });
      if (!response.ok) throw new Error(`Could not download corpus original (HTTP ${response.status}).`);
      const blob = await response.blob();
      const file = new File([blob], image.file_name, { type: image.content_type });
      const item: QueueItem = {
        id: `corpus-${image.id}-${Date.now()}-${sequence.current++}`,
        file,
        previewUrl: URL.createObjectURL(file),
        width: image.width,
        height: image.height,
        status: "ready",
        corpus: {
          imageId: image.id,
          experimentId: experiment.id,
          registrationStatus: "idle"
        }
      };
      setQueue((current) => [...current, item]);
      setActiveId(item.id);
      setCorpusPickerOpen(false);
      setNotice(`Loaded fixed-corpus original · ${image.file_name} · experiment ${shortId(experiment.id)}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load the corpus original.");
    } finally {
      setCorpusLoading(false);
    }
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

  function clearQueue() {
    if (running) return;
    queue.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    setQueue([]);
    setActiveId("");
    setNotice("");
    setStatus("");
  }

  async function waitForJob(jobId: string, itemId: string, position: number, total: number) {
    for (;;) {
      const job = await getDeepCleanJob(jobId);
      if (job.status === "completed") return job;
      if (job.status === "failed") {
        throw new Error(job.failureReason || "The worker could not process this image.");
      }
      patchItem(itemId, { status: job.status === "queued" ? "queued" : "processing", job });
      setStatus(`Processing ${position}/${total} · ${job.status}`);
      await new Promise<void>((resolve) => window.setTimeout(resolve, 3500));
    }
  }

  async function processItem(item: QueueItem, position: number, total: number) {
    const runPreset = structuredClone(preset);
    const runSettingsCode = settingsCodeForPreset(runPreset);
    const runConfigLabel = configLabelForPreset(runPreset);
    let created: DeepCleanJob | null = null;
    let corpusIntentId: string | null = null;
    let workerCompleted = false;
    patchItem(item.id, { status: "preparing", error: undefined, job: undefined });
    setActiveId(item.id);
    try {
      setStatus(`Preparing ${position}/${total} · ${item.file.name}`);
      const job = await createDeepCleanJob({
        file: item.file,
        creatorId: userEmail || "creator@example.com",
        profile: "ds-remint-v8.9-hd",
        outputMode: "stripped",
        dsRemintV89Hd: {
          remint: runPreset.remint,
          finish: runPreset.finish,
          finishMode: runPreset.finishMode
        },
        outputNameStyle: "settings-code",
        outputNameCustom: position > 1 ? `${runSettingsCode}-${position}` : runSettingsCode
      });
      created = job;
      if (item.corpus) {
        patchItem(item.id, {
          corpus: { ...item.corpus, registrationStatus: "intent", registrationError: undefined }
        });
        setStatus(`Recording corpus run intent ${position}/${total}…`);
        corpusIntentId = await createCorpusRunIntent({
          corpusImageId: item.corpus.imageId,
          experimentId: item.corpus.experimentId,
          configLabel: runConfigLabel,
          requestedSettingsCode: runSettingsCode,
          requestedSettingsCanonical: settingsCanonicalForPreset(runPreset)
        });
        patchItem(item.id, {
          corpus: { ...item.corpus, intentId: corpusIntentId, registrationStatus: "pending" }
        });
      }
      patchItem(item.id, { status: "uploading", job });
      setStatus(`Uploading ${position}/${total} privately…`);
      await uploadDeepCleanInput(job, item.file);
      patchItem(item.id, { status: "queued", job });
      await dispatchDeepCleanJob(job.id);
      await spendCredits(UNIT_COST);
      patchItem(item.id, { status: "processing", job });
      const completed = await waitForJob(job.id, item.id, position, total);
      workerCompleted = true;
      patchItem(item.id, { status: "grading", job: completed });
      setStatus(`Grading OG + remint ${position}/${total}…`);
      const row = await gradeCompletedItem(item, completed, runPreset, runSettingsCode);
      setRows(appendGradeLedgerRow(row));
      patchItem(item.id, {
        status: "completed",
        job: completed,
        ledgerId: row.id,
        error: undefined
      });
      if (corpusIntentId) void registerCorpusItem(item.id, corpusIntentId, completed.id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "The item could not be completed.";
      if (created && !workerCompleted) {
        await cancelDeepCleanJob(created.id).catch(() => undefined);
      }
      patchItem(item.id, { status: "failed", error: message, job: created ?? undefined });
      throw error;
    }
  }

  async function registerCorpusItem(itemId: string, intentId: string, workerJobId: string) {
    const current = queueRef.current.find((item) => item.id === itemId);
    if (!current?.corpus) return;
    patchItem(itemId, {
      corpus: { ...current.corpus, intentId, registrationStatus: "pending", registrationError: undefined }
    });
    try {
      const result = await registerCorpusRun(intentId, workerJobId);
      const latest = queueRef.current.find((item) => item.id === itemId);
      if (!latest?.corpus) return;
      patchItem(itemId, {
        corpus: {
          ...latest.corpus,
          intentId,
          registrationStatus: "registered",
          registrationRunId: result.corpus_run_id,
          registrationError: undefined
        }
      });
    } catch (error) {
      const latest = queueRef.current.find((item) => item.id === itemId);
      if (!latest?.corpus) return;
      patchItem(itemId, {
        corpus: {
          ...latest.corpus,
          intentId,
          registrationStatus: "failed",
          registrationError: error instanceof Error ? error.message : "Corpus registration failed."
        }
      });
    }
  }

  function retryCorpusRegistration(item: QueueItem) {
    if (!item.corpus?.intentId || !item.job?.id || item.job.status !== "completed") return;
    void registerCorpusItem(item.id, item.corpus.intentId, item.job.id);
  }

  async function gradeCompletedItem(
    item: QueueItem,
    job: DeepCleanJob,
    runPreset: PresetDefinition,
    runSettingsCode: string
  ): Promise<GradeLedgerRow> {
    if (!job.outputUrl) throw new Error("Completed job is missing a secure output URL.");
    const sessionId = getGradeSessionId();
    const requestedModes = [primaryMode];
    const modeResults: Partial<Record<GradeMode, ModeGradePair>> = {};
    let firstPair: ModeGradePair | null = null;

    for (const mode of requestedModes) {
      const og = await gradeImage(item.file, "og", {
        mode,
        settingsCode: runSettingsCode,
        sessionId
      });
      recordGradeResponse(og);
      const remint = await gradeOutputUrl(job.outputUrl, "remint", {
        mode,
        settingsCode: runSettingsCode,
        ogGrade: og,
        sessionId
      });
      recordGradeResponse(remint);
      const pair = pairFor(mode, og, remint);
      modeResults[mode] = pair;
      if (!firstPair) firstPair = pair;
    }

    if (!firstPair) throw new Error("No detector mode was selected.");
    const executed = await workerReportProvenance(job.report);
    return {
      schema_version: 1,
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      file_id: item.id,
      file_name: item.file.name,
      job_id: job.id,
      image_sha256: firstPair.og.image_sha256,
      settings_code: runSettingsCode,
      requested_settings: {
        profile: "ds-remint-v8.9-hd",
        remint: runPreset.remint,
        finish: runPreset.finish,
        finish_mode: runPreset.finishMode
      },
      executed,
      mode: firstPair.remint.mode,
      vendor: firstPair.remint.vendor,
      mock: firstPair.og.mock || firstPair.remint.mock,
      og_grade: firstPair.og,
      remint_grade: firstPair.remint,
      mode_results: modeResults,
      delta: firstPair.delta,
      verdict: firstPair.verdict,
      qa_flag: firstPair.qa_flag,
      swap_index: firstPair.remint.swap_index,
      retention_index: firstPair.remint.retention_index
    };
  }

  function recordGradeResponse(grade: NormalizedGrade) {
    setGradeStats((current) => ({
      grades: current.grades + 1,
      cacheHits: current.cacheHits + (grade.cache_hit ? 1 : 0),
      vendorCalls: Math.max(current.vendorCalls, grade.session_usage?.vendor_calls ?? 0),
      cap: grade.session_usage?.cap ?? current.cap
    }));
  }

  async function runSelectedDetectionOnly() {
    const item = active;
    if (!item || running || detecting) return;
    if (!hasSupabaseConfig || !userId) {
      setNotice("Sign in before running detection-only grading.");
      return;
    }

    setDetecting(true);
    setNotice(`Detection only · testing ${item.file.name} · no remint job will run…`);
    try {
      const sessionId = getGradeSessionId();
      const requestedModes = [primaryMode];
      const modeResults: Partial<Record<GradeMode, NormalizedGrade>> = {};
      let primaryGrade: NormalizedGrade | null = null;

      for (const mode of requestedModes) {
        const grade = await gradeImage(item.file, "og", { mode, sessionId });
        recordGradeResponse(grade);
        modeResults[mode] = grade;
        if (!primaryGrade) primaryGrade = grade;
      }

      if (!primaryGrade) throw new Error("No detector mode was selected.");
      const row: DetectionOnlyLedgerRow = {
        schema_version: 1,
        run_kind: "detection_only",
        id: crypto.randomUUID(),
        timestamp: new Date().toISOString(),
        file_id: item.id,
        file_name: item.file.name,
        image_sha256: primaryGrade.image_sha256,
        mode: primaryGrade.mode,
        vendor: primaryGrade.vendor,
        mock: primaryGrade.mock,
        grade: primaryGrade,
        mode_results: modeResults,
        qa_flag: primaryGrade.verdict === "BORDER" || Boolean(primaryGrade.vendor_error),
        settings_code: null,
        worker_job_id: null,
        remint_dispatched: false,
        remint_credits_spent: 0
      };
      setDetectionOnlyRows(appendDetectionOnlyLedgerRow(row));
      setNotice(
        `Detection only complete · ${modeLabel(row.mode)} · ${percent(
          row.grade.ai_probability
        )} · ${row.grade.verdict} · remint not dispatched · 0 remint credits.`
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Detection-only grading failed.");
    } finally {
      setDetecting(false);
    }
  }

  async function runQueue() {
    const items = queue.filter((item) => item.status !== "completed");
    if (!items.length || running || detecting) return;
    if (!hasSupabaseConfig || !userId) return setStatus("Sign in before running the queue.");
    if (credits.privacyCredits < items.length * UNIT_COST) {
      return setStatus(`Not enough credits — this run needs ${items.length * UNIT_COST}.`);
    }
    setRunning(true);
    setNotice("");
    setBatch({ done: 0, total: items.length });
    let failed = 0;
    for (const [index, item] of items.entries()) {
      try {
        await processItem(item, index + 1, items.length);
      } catch {
        failed += 1;
      }
      setBatch({ done: index + 1, total: items.length });
    }
    setRunning(false);
    setBatch({ done: 0, total: 0 });
    if (userId) await refreshCredits(userId);
    setStatus(failed ? `Complete with ${failed} failed item(s).` : "Jobs and paired grades complete.");
  }

  async function regradeRow(row: GradeLedgerRow) {
    if (running) return;
    const item = queue.find((candidate) => candidate.job?.id === row.job_id);
    if (!item?.job?.id) return setNotice("Re-grade is available while the source file is in this queue.");
    setRunning(true);
    setActiveId(item.id);
    patchItem(item.id, { status: "grading", error: undefined });
    try {
      const fresh = await getDeepCleanJob(item.job.id);
      if (fresh.status !== "completed" || !fresh.outputUrl) throw new Error("Output is not ready.");
      const runPreset = presetFromRequested(row.requested_settings);
      if (!runPreset) throw new Error("Stored requested settings do not match an authorized /relab tuple.");
      const next = await gradeCompletedItem(item, fresh, runPreset, row.settings_code);
      setRows(appendGradeLedgerRow(next));
      patchItem(item.id, { status: "completed", job: fresh, ledgerId: next.id });
      const providerCalls = next.og_grade.provider_calls + next.remint_grade.provider_calls;
      setNotice(
        providerCalls === 0 && next.og_grade.cache_hit && next.remint_grade.cache_hit
          ? "Re-grade complete · both hashes were cache hits · 0 provider calls."
          : `Re-grade complete · ${providerCalls} provider call(s).`
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Re-grade failed.";
      patchItem(item.id, { status: "failed", error: message });
      setNotice(message);
    } finally {
      setRunning(false);
    }
  }

  async function openResult(row: GradeLedgerRow) {
    const item = queue.find((candidate) => candidate.job?.id === row.job_id);
    if (!item?.job?.id) return setNotice("Open result is available while the job is in this queue.");
    try {
      const fresh = await getDeepCleanJob(item.job.id);
      if (!fresh.outputUrl) throw new Error("The output link is not ready.");
      window.open(fresh.outputUrl, "_blank", "noopener,noreferrer");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not open the output.");
    }
  }

  function sortBy(next: SortKey) {
    if (sortKey === next) setSortAscending((current) => !current);
    else {
      setSortKey(next);
      setSortAscending(next === "ai" || next === "verdict");
    }
  }

  function downloadText(text: string, name: string, type: string) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function copyText(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyState(key);
    } catch {
      setNotice("Clipboard access was denied.");
    }
  }

  async function importLedgerFile(file: File) {
    try {
      setRows(importGradeLedger(await file.text()));
      setNotice("Ledger imported and truncated to the newest 500 rows.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Ledger import failed.");
    }
  }

  const activeResultUrl = active?.job?.status === "completed" ? active.job.outputUrl : undefined;
  const needsSignIn = hasSupabaseConfig && !userId;

  return (
    <div className="relab">
      <input
        ref={fileInput}
        hidden
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp"
        onChange={(event) => {
          addFiles(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
      <input
        ref={importInput}
        hidden
        type="file"
        accept="application/json,.jsonl"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void importLedgerFile(file);
          event.target.value = "";
        }}
      />

      <div className="rl-shell">
        <header className="rl-topbar">
          <div className="rl-brand">
            <span className="rl-brand-mark"><FlaskConical size={16} /></span>
            <span><b>/RELAB</b><small>Remint detection lab</small></span>
          </div>
          <span className="rl-flow"><Check size={12} /> Frozen V11 engines <span>→</span> paired grading</span>
          <span className="rl-spacer" />
          <button
            className="rl-code"
            type="button"
            onClick={() => void copyText(settingsCode, "code")}
            title="Copy settings code"
          >
            {copyState === "code" ? <Check size={12} /> : <Copy size={12} />}
            <code>{settingsCode}</code>
          </button>
          <span className="rl-badge rl-badge-live">HIVE API</span>
          <span className="rl-credits"><Wallet size={13} /><b>{credits.privacyCredits}</b></span>
          {needsSignIn ? (
            <details className="rl-account">
              <summary><UserRound size={14} /> Sign in</summary>
              <div className="rl-account-panel">
                <div className="rl-segment">
                  <button className={authMode === "signin" ? "is-active" : ""} onClick={() => setAuthMode("signin")}>Sign in</button>
                  <button className={authMode === "signup" ? "is-active" : ""} onClick={() => setAuthMode("signup")}>Sign up</button>
                </div>
                <label><Mail size={13} /><input type="email" placeholder="you@email.com" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} /></label>
                <label><KeyRound size={13} /><input type="password" placeholder="Password" value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void submitAuth(); }} /></label>
                <button className="rl-btn rl-btn-primary" type="button" onClick={() => void submitAuth()}>{authMode === "signin" ? "Sign in" : "Create account"}</button>
                {authStatus ? <p>{authStatus}</p> : null}
              </div>
            </details>
          ) : userId ? (
            <details className="rl-account">
              <summary><UserRound size={14} /> {userEmail}</summary>
              <div className="rl-account-panel">
                <p>{credits.privacyCredits} credits</p>
                <button className="rl-btn" type="button" onClick={() => void signOut()}><LogOut size={13} /> Sign out</button>
              </div>
            </details>
          ) : null}
          <button className="rl-icon" type="button" aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </button>
        </header>

        <div className="rl-console">
          <aside className="rl-panel rl-queue-panel">
            <div className="rl-panel-head">
              <b>Queue</b><span>{queue.length}/{MAX_QUEUE}</span><span className="rl-spacer" />
              <button className="rl-btn rl-btn-small" type="button" disabled={running || corpusLoading || !userId || queue.length >= MAX_QUEUE} onClick={() => void openCorpusPicker()}>{corpusLoading ? <Loader2 className="rl-spin" size={13} /> : <ImageIcon size={13} />} Corpus</button>
              <button className="rl-btn rl-btn-small" type="button" disabled={running || queue.length >= MAX_QUEUE} onClick={() => fileInput.current?.click()}><Upload size={13} /> Add</button>
            </div>
            {corpusPickerOpen ? (
              <div className="rl-corpus-picker">
                <div><b>Fixed-corpus picker</b><button className="rl-icon" type="button" onClick={() => setCorpusPickerOpen(false)}><X size={12} /></button></div>
                <label><span>Comparable experiment</span><select value={corpusExperimentId} onChange={(event) => setCorpusExperimentId(event.target.value)}><option value="">Select experiment</option>{corpusSnapshot?.experiments.map((experiment) => <option key={experiment.id} value={experiment.id}>{shortId(experiment.id)} · {experiment.detector_vendor}/{experiment.detector_mode}</option>)}</select></label>
                <div className="rl-corpus-images">
                  {corpusPickerImages.map((image) => <button key={image.id} type="button" disabled={corpusLoading || queue.some((item) => item.corpus?.imageId === image.id && item.corpus.experimentId === corpusExperimentId)} onClick={() => { if (corpusExperiment) void addCorpusImage(image, corpusExperiment); }}>{image.signed_url ? <img src={image.signed_url} alt="" /> : <span />}<span><b>{image.file_name}</b><small>{image.width}×{image.height} · {shortId(image.sha256)}</small></span></button>)}
                  {!corpusPickerImages.length ? <p>No active images in this experiment's locked set.</p> : null}
                </div>
              </div>
            ) : null}
            <div className="rl-panel-scroll">
              <button
                type="button"
                className={`rl-drop${dragging ? " is-drag" : ""}`}
                disabled={running}
                onClick={() => fileInput.current?.click()}
                onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(Array.from(event.dataTransfer.files)); }}
              >
                <Upload size={18} /><b>Drop images</b><span>JPEG · PNG · WebP · 25 MB</span>
              </button>
              <div className="rl-queue">
                {queue.map((item) => (
                  <div key={item.id} role="button" tabIndex={0} className={`rl-qitem${active?.id === item.id ? " is-active" : ""}`} onClick={() => setActiveId(item.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setActiveId(item.id); }}>
                    <img src={item.previewUrl} alt="" />
                    <span><b>{item.file.name}</b><small><i className={`rl-status-dot is-${item.status}`} />{statusLabel(item.status)}{item.width ? ` · ${item.width}×${item.height}` : ""}</small>{item.corpus ? <small className={`rl-registration is-${item.corpus.registrationStatus}`}>{registrationLabel(item.corpus.registrationStatus)}{item.corpus.registrationRunId ? ` · ${shortId(item.corpus.registrationRunId)}` : ""}</small> : null}{item.corpus?.registrationStatus === "failed" ? <button className="rl-registration-retry" type="button" onClick={(event) => { event.stopPropagation(); retryCorpusRegistration(item); }}><RefreshCw size={10} /> Retry registration</button> : null}{item.error || item.corpus?.registrationError ? <em>{item.error ?? item.corpus?.registrationError}</em> : null}</span>
                    <button className="rl-icon" type="button" aria-label="Remove image" disabled={running} onClick={(event) => { event.stopPropagation(); removeItem(item.id); }}><X size={13} /></button>
                  </div>
                ))}
              </div>
            </div>
            {queue.length ? <div className="rl-panel-foot"><button className="rl-btn" type="button" disabled={running} onClick={clearQueue}><Trash2 size={13} /> Clear queue</button></div> : null}
          </aside>

          <main className="rl-panel rl-viewer">
            <div className="rl-panel-head">
              <b>{active?.file.name ?? "Viewer"}</b>
              {active ? <span>{(active.file.size / 1_000_000).toFixed(2)} MB</span> : null}
            </div>
            <div className="rl-stage">
              {active ? (
                <div className="rl-frame">
                  <img src={activeResultUrl || active.previewUrl} alt={activeResultUrl ? "Remint output" : "Original"} />
                  {activeResultUrl ? <span className="rl-image-tag">Remint output</span> : <span className="rl-image-tag">Original</span>}
                  {["preparing", "uploading", "queued", "processing", "grading"].includes(active.status) ? <div className="rl-veil"><Loader2 className="rl-spin" size={26} /><b>{statusLabel(active.status)}</b></div> : null}
                </div>
              ) : (
                <div className="rl-empty"><ImageIcon size={32} /><h2>Load a fixed-corpus image</h2><p>Config A is selected. Every completed output is paired with its original and graded in the same explicit detector mode.</p><button className="rl-btn rl-btn-primary" type="button" onClick={() => fileInput.current?.click()}><Upload size={14} /> Add images</button></div>
              )}
            </div>
            <div className="rl-stage-status">{notice || status || (!hasSupabaseConfig ? "Supabase environment is not configured." : "Ready.")}</div>
          </main>

          <aside className="rl-panel rl-controls">
            <div className="rl-panel-head"><SlidersHorizontal size={13} /><b>Frozen presets</b><span className="rl-spacer" /><span>{UNIT_COST} cr/image</span></div>
            <div className="rl-panel-scroll rl-control-body">
              {(Object.values(PRESETS) as PresetDefinition[]).map((next) => (
                <button key={next.id} className={`rl-preset${presetId === next.id ? " is-active" : ""}`} type="button" disabled={running} onClick={() => setPresetId(next.id)}>
                  <span className="rl-preset-icon">{next.id === "config-3c" || next.id === "4d-cam-1" || next.id === "4d-1a" ? <FlaskConical size={15} /> : next.id === "config-2b" ? <Film size={15} /> : next.id === "config-1a" ? <Gauge size={15} /> : <Check size={15} />}</span>
                  <span><b>{next.label}</b><small>{next.detail}</small></span>
                  <span>{presetId === next.id ? "ACTIVE" : "SELECT"}</span>
                </button>
              ))}

              <section className="rl-detector-card">
                <div className="rl-section-title"><KeyRound size={14} /><b>Lab paired seed</b></div>
                <label className="rl-field">
                  <span>Optional fixed seed</span>
                  <input
                    type="text"
                    value={labSeed}
                    pattern="^lab-[a-z0-9]{1,32}$"
                    placeholder="lab-pair1"
                    aria-invalid={!labSeedValid}
                    disabled={running}
                    onChange={(event) => setLabSeed(event.target.value)}
                  />
                </label>
                <p className="rl-help">Exact form: <code>lab-[a-z0-9]&#123;1,32&#125;</code>. Blank keeps production randomness; authorized lab accounts only.</p>
                {!labSeedValid ? <div className="rl-warning"><b>INVALID</b><span>The seed must match the exact lab format.</span></div> : null}
                {presetId === "4d-cam-1" && !cam1SeedReady ? <div className="rl-warning"><b>LOCKED</b><span>4D-CAM-1 requires lab-ctla1 or lab-ctla2.</span></div> : null}
                {presetId === "4d-1a" && !transfer4d1aSeedReady ? <div className="rl-warning"><b>LOCKED</b><span>4D-1A requires lab-ctla1 or lab-ctla2.</span></div> : null}
              </section>

              <section className="rl-detector-card">
                <div className="rl-section-title"><FlaskConical size={14} /><b>Detection loop</b></div>
                <label className="rl-field"><span>Vendor detector</span><select value={primaryMode} disabled><option value="real">Hive unified detector</option></select><ChevronDown size={13} /></label>
                <p className="rl-help">Hive exposes one detector API. SDXL, Flux Schnell, and Real are website example presets—not separate API modes.</p>
                <div className="rl-detect-only-block">
                  <button className="rl-btn rl-detect-only" type="button" disabled={!active || running || detecting || !hasSupabaseConfig || !userId} onClick={() => void runSelectedDetectionOnly()}>
                    {detecting ? <><Loader2 className="rl-spin" size={15} /> Testing selected image…</> : <><ScanSearch size={15} /> Run API detection only</>}
                  </button>
                  <small>{active ? `Selected original: ${active.file.name}` : "Select an image from the queue."}</small>
                  <small>No remint job · no worker dispatch · 0 remint credits</small>
                  {activeDetectionOnlyResult ? (
                    <div className="rl-detect-result">
                      <span><small>AI probability</small><b>{percent(activeDetectionOnlyResult.grade.ai_probability)}</b></span>
                      <span><small>Deepfake</small><b>{percent(activeDetectionOnlyResult.grade.deepfake_probability)}</b></span>
                      <span><small>Verdict</small><b className={`is-${activeDetectionOnlyResult.grade.verdict.toLowerCase()}`}>{activeDetectionOnlyResult.grade.verdict}</b></span>
                      <span><small>API result</small><b>{gradeCallLabel(activeDetectionOnlyResult.grade)}</b></span>
                      <div className="rl-detect-sources">
                        <small>Top 5 AI source signals</small>
                        <SourceRankList sources={activeDetectionOnlyResult.grade.sources} />
                      </div>
                      <div className="rl-detect-meta">
                        <span>Hive unified</span>
                        <code title={activeDetectionOnlyResult.grade.image_sha256}>SHA {shortId(activeDetectionOnlyResult.grade.image_sha256)}</code>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="rl-budget"><span><b>{gradeStats.vendorCalls}</b> / {gradeStats.cap}<small>vendor calls this session</small></span><span><b>{gradeStats.cacheHits}</b><small>cache hits</small></span><span><b>{gradeStats.grades}</b><small>grades returned</small></span></div>
                <div className="rl-warning is-live"><b>LIVE</b><span>Server-side Hive adapter · credentials never enter the browser or ledger.</span></div>
              </section>
            </div>
            <div className="rl-runbar">
              {running && batch.total ? <div className="rl-progress"><span style={{ width: `${(batch.done / batch.total) * 100}%` }} /></div> : null}
              <div><span>{pending.length} pending · {queue.length - pending.length} done</span><b>{totalCost} credits</b></div>
              <button className="rl-btn rl-btn-primary rl-run" type="button" disabled={!canRun} onClick={() => void runQueue()}>{running ? <><Loader2 className="rl-spin" size={15} /> Running loop…</> : <><Play size={15} /> Run {pending.length || 0} image{pending.length === 1 ? "" : "s"}</>}</button>
              {needsSignIn ? <small>Sign in to dispatch jobs and grades.</small> : null}
            </div>
          </aside>
        </div>

        <section className="rl-ledger">
          <div className="rl-ledger-head">
            <div><b>Ranked grade ledger</b><span>{rows.length}/500 persistent rows</span></div>
            <span className="rl-spacer" />
            <button className="rl-btn rl-btn-small" type="button" onClick={() => importInput.current?.click()}><Upload size={13} /> Import</button>
            <button className="rl-btn rl-btn-small" type="button" disabled={!rows.length} onClick={() => downloadText(exportGradeLedgerJsonl(rows), "relab-grades.jsonl", "application/x-ndjson")}><FileJson size={13} /> JSONL</button>
            <button className="rl-btn rl-btn-small" type="button" disabled={!rows.length} onClick={() => downloadText(exportGradeLedgerCsv(rows), "relab-grades.csv", "text/csv")}><Download size={13} /> CSV</button>
            <button className="rl-btn rl-btn-small" type="button" disabled={!rows.length} onClick={() => void copyText(compactGradeReport(rows), "compact")}><ClipboardCopy size={13} /> {copyState === "compact" ? "Copied" : "Copy compact report"}</button>
          </div>
          <div className="rl-table-wrap">
            <table>
              <thead><tr><th>#</th><th>File ID</th><th>Settings code</th><th>Mode</th><th><button onClick={() => sortBy("ai")}>OG AI% / Remint AI%</button></th><th><button onClick={() => sortBy("delta")}>Δ</button></th><th>Deepfake OG / RM</th><th>Top 5 AI sources</th>{auxiliaryModes.map((mode) => <th key={mode}>{modeLabel(mode)}<br />OG / Remint / Δ</th>)}<th>Swap / retention</th><th><button onClick={() => sortBy("verdict")}>Verdict</button></th><th>QA</th><th>API provenance</th><th><button onClick={() => sortBy("timestamp")}>Timestamp</button></th><th>Actions</th></tr></thead>
              <tbody>
                {sortedRows.map((row, index) => (
                  <tr key={row.id}>
                    <td className="rl-rank">{index + 1}</td>
                    <td><b>{row.file_name}</b><small>{row.file_id}</small>{row.mock ? <span className="rl-mini-mock">MOCK</span> : null}</td>
                    <td><code>{row.settings_code}</code></td>
                    <td>{modeLabel(row.mode)}</td>
                    <td><span className="rl-pair"><b>{percent(row.og_grade.ai_probability)}</b><span>→</span><b>{percent(row.remint_grade.ai_probability)}</b></span></td>
                    <td className={row.delta >= 0 ? "is-good" : "is-bad"}>{signedPercent(row.delta)}</td>
                    <td><span className="rl-pair"><b>{percent(row.og_grade.deepfake_probability)}</b><span>→</span><b>{percent(row.remint_grade.deepfake_probability)}</b></span></td>
                    <td><div className="rl-source-pair"><SourceRankList label="OG" sources={row.og_grade.sources} compact /><SourceRankList label="RM" sources={row.remint_grade.sources} compact /></div></td>
                    {auxiliaryModes.map((mode) => {
                      const pair = row.mode_results[mode];
                      return <td key={mode}>{pair ? <span className="rl-pair"><b>{percent(pair.og.ai_probability)}</b><span>→</span><b>{percent(pair.remint.ai_probability)}</b><span className={pair.delta >= 0 ? "is-good" : "is-bad"}>{signedPercent(pair.delta)}</span></span> : "—"}</td>;
                    })}
                    <td>{percent(row.swap_index)} / {percent(row.retention_index)}</td>
                    <td><span className={`rl-verdict is-${row.verdict.toLowerCase()}`}>{row.verdict}</span></td>
                    <td>{row.qa_flag ? <span className="rl-qa">FLAG</span> : "—"}</td>
                    <td><div className="rl-api-meta"><span><small>OG</small> {gradeCallLabel(row.og_grade)}</span><span><small>RM</small> {gradeCallLabel(row.remint_grade)}</span><code title={row.image_sha256}>SHA {shortId(row.image_sha256)}</code></div></td>
                    <td>{new Date(row.timestamp).toLocaleString()}</td>
                    <td><div className="rl-actions"><button title="Re-grade (hash cache applies)" disabled={running} onClick={() => void regradeRow(row)}><RefreshCw size={13} /></button><button title="Copy compact report line" onClick={() => void copyText(compactGradeReport([row]), row.id)}>{copyState === row.id ? <Check size={13} /> : <Copy size={13} />}</button><button title="Open result" onClick={() => void openResult(row)}><ExternalLink size={13} /></button></div></td>
                  </tr>
                ))}
                {!rows.length ? <tr><td colSpan={14 + auxiliaryModes.length} className="rl-no-results">Completed paired grades will appear here.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rl-ledger rl-detection-only-ledger">
          <div className="rl-ledger-head">
            <div><b>Detection-only ledger</b><span>{detectionOnlyRows.length}/500 isolated API tests · no remint provenance</span></div>
            <span className="rl-spacer" />
            <button className="rl-btn rl-btn-small" type="button" disabled={!detectionOnlyRows.length} onClick={() => downloadText(exportDetectionOnlyLedgerJsonl(detectionOnlyRows), "relab-detection-only.jsonl", "application/x-ndjson")}><FileJson size={13} /> JSONL</button>
            <button className="rl-btn rl-btn-small" type="button" disabled={!detectionOnlyRows.length} onClick={() => downloadText(exportDetectionOnlyLedgerCsv(detectionOnlyRows), "relab-detection-only.csv", "text/csv")}><Download size={13} /> CSV</button>
          </div>
          <div className="rl-table-wrap">
            <table>
              <thead><tr><th>#</th><th>Selected image</th><th>Mode</th><th>AI%</th><th>Deepfake%</th><th>Top 5 AI sources</th><th>Verdict</th><th>API provenance</th><th>Isolation proof</th><th>Timestamp</th><th>Copy</th></tr></thead>
              <tbody>
                {rankedDetectionOnlyRows.map((row, index) => (
                  <tr key={row.id}>
                    <td className="rl-rank">{index + 1}</td>
                    <td><b>{row.file_name}</b><small>{row.file_id}</small>{row.mock ? <span className="rl-mini-mock">MOCK</span> : null}</td>
                    <td>{modeLabel(row.mode)}</td>
                    <td><b>{percent(row.grade.ai_probability)}</b></td>
                    <td>{percent(row.grade.deepfake_probability)}</td>
                    <td><SourceRankList sources={row.grade.sources} compact /></td>
                    <td><span className={`rl-verdict is-${row.grade.verdict.toLowerCase()}`}>{row.grade.verdict}</span></td>
                    <td><div className="rl-api-meta"><b>{gradeCallLabel(row.grade)}</b><span>{row.grade.provider_calls} provider call{row.grade.provider_calls === 1 ? "" : "s"}</span><code title={row.grade.image_sha256}>SHA {shortId(row.grade.image_sha256)}</code></div></td>
                    <td><span className="rl-isolation-proof">No job · 0 credits</span></td>
                    <td>{new Date(row.timestamp).toLocaleString()}</td>
                    <td><div className="rl-actions"><button title="Copy standalone JSON record" onClick={() => void copyText(JSON.stringify(row), `detect-${row.id}`)}>{copyState === `detect-${row.id}` ? <Check size={13} /> : <Copy size={13} />}</button></div></td>
                  </tr>
                ))}
                {!detectionOnlyRows.length ? <tr><td colSpan={11} className="rl-no-results">Select a queued image and press “Run API detection only.”</td></tr> : null}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function SourceRankList({
  sources,
  label,
  compact = false
}: {
  sources: Record<string, number>;
  label?: string;
  compact?: boolean;
}) {
  const ranked = topAiSources(sources, 5);
  return (
    <div className={`rl-source-list${compact ? " is-compact" : ""}`}>
      {label ? <small className="rl-source-list-label">{label}</small> : null}
      {ranked.length ? (
        <ol>
          {ranked.map((source) => (
            <li key={source.family} title={`${source.family}: ${percent(source.probability)}`}>
              <span className="rl-source-rank">{source.rank}</span>
              <span className="rl-source-name">{sourceLabel(source.family)}</span>
              <span className="rl-source-track"><i style={{ width: `${source.probability * 100}%` }} /></span>
              <b>{percent(source.probability)}</b>
            </li>
          ))}
        </ol>
      ) : <span className="rl-source-empty">No source signals</span>}
    </div>
  );
}

function settingsCodeForPreset(preset: PresetDefinition): string {
  return buildSettingsCode(settingsCanonicalForPreset(preset));
}

function settingsCanonicalForPreset(preset: PresetDefinition): SettingsCodeInput {
  return settingsForPreset(preset);
}

function configLabelForPreset(preset: PresetDefinition): "A" | "1A" | "2B" | "3C" | "CUSTOM" {
  const canonical = settingsCanonicalForPreset(preset);
  const label = configIdentity(canonical).label;
  if (label === "CUSTOM") {
    const lockedSeed = CAM1_LOCKED_SEEDS.has(preset.remint.seed ?? "");
    if ((!is4dCam1(canonical) && !is4d1a(canonical)) || !lockedSeed) {
      throw new Error("CUSTOM is restricted to an exact seeded 4D lab tuple.");
    }
    return label;
  }
  return label;
}

function pairFor(requestedMode: GradeMode, og: NormalizedGrade, remint: NormalizedGrade): ModeGradePair {
  const delta = Math.round((og.ai_probability - remint.ai_probability) * 1_000_000) / 1_000_000;
  return {
    mode: remint.mode ?? requestedMode,
    og,
    remint,
    delta,
    verdict: remint.verdict,
    qa_flag: remint.verdict === "BORDER" || Boolean(og.vendor_error || remint.vendor_error)
  };
}

function modeLabel(mode: GradeMode): string {
  return mode === "real" ? "Hive unified" : mode === "sdxl" ? "Legacy SDXL preset" : "Legacy Flux preset";
}

function gradeCallLabel(grade: NormalizedGrade): string {
  if (grade.mock) return "MOCK";
  if (grade.cache_hit) return "CACHE HIT";
  if (grade.provider_calls === 1) return "1 API CALL";
  return `${grade.provider_calls} API CALLS`;
}

function shortId(value: string): string {
  return value ? `${value.slice(0, 10)}…` : "—";
}

function sourceLabel(value: string): string {
  const known: Record<string, string> = {
    adobe_firefly: "Adobe Firefly",
    dalle: "DALL·E",
    dalle2: "DALL·E 2",
    dalle3: "DALL·E 3",
    flux: "Flux",
    midjourney: "Midjourney",
    stable_diffusion: "Stable Diffusion",
    stable_diffusion_xl: "Stable Diffusion XL",
    stablediffusion: "Stable Diffusion",
    stablediffusionxl: "Stable Diffusion XL"
  };
  const key = value.trim().toLowerCase();
  return known[key] ?? key
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusLabel(status: QueueStatus): string {
  return {
    ready: "Ready",
    preparing: "Preparing",
    uploading: "Uploading",
    queued: "Queued",
    processing: "Processing",
    grading: "Grading pair",
    completed: "Graded",
    failed: "Failed"
  }[status];
}

function registrationLabel(status: NonNullable<QueueItem["corpus"]>["registrationStatus"]): string {
  return {
    idle: "CORPUS · ready",
    intent: "CORPUS · recording intent",
    pending: "CORPUS · registration pending",
    registered: "CORPUS · registered",
    failed: "CORPUS · registration failed"
  }[status];
}

function percent(value: number): string {
  return `${(Math.max(0, Math.min(1, value)) * 100).toFixed(1)}%`;
}

function signedPercent(value: number): string {
  const amount = Math.max(-1, Math.min(1, value)) * 100;
  return `${amount >= 0 ? "+" : ""}${amount.toFixed(1)}%`;
}
