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
  KeyRound,
  Leaf,
  Loader2,
  Lock,
  LogOut,
  Mail,
  Moon,
  RotateCcw,
  Scan,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Upload,
  UserRound,
  Wallet,
  Zap
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
  type DeepCleanProfile,
  type ExpertRefinementMode,
  type ExpertRefinementSettings,
  type ExpertRefinementTechnique,
  type CxRemintOptions,
  type CxRemintQualityFloor,
  type CxRemintEngineMode,
  type CxRemintDevice
} from "./lib/deepcleanClient";
import {
  getAdminRunpodEndpoint,
  updateAdminRunpodEndpoint,
  type AdminRunpodEndpoint
} from "./lib/adminRunpodClient";
import {
  reframeImageFile,
  reframeOptionsFor,
  REFRAME_PRESETS,
  type ReframePreset
} from "./lib/reframe";
import { supabase } from "./lib/supabase";

type ProcessingState = "idle" | "processing" | "done" | "error";
type Theme = "light" | "dark";
type AuthMode = "signin" | "signup" | "reset" | "update";
type MintDeepCleanProfile =
  | DeepCleanProfile
  | "max-remint"
  | "max-optimised-remint"
  | "max-cx-remint"
  | "max-cx-remint-v2"
  | "max-cx-remint-v3"
  | "max-cx-remint-v4"
  | "max-cx-remint-v5";

function isCxProfile(profile: MintDeepCleanProfile): boolean {
  return (
    profile === "max-cx-remint" ||
    profile === "max-cx-remint-v2" ||
    profile === "max-cx-remint-v3" ||
    profile === "max-cx-remint-v4" ||
    profile === "max-cx-remint-v5"
  );
}

function isCxDeepProfile(profile: MintDeepCleanProfile): boolean {
  return (
    profile === "max-cx-remint-v2" ||
    profile === "max-cx-remint-v3" ||
    profile === "max-cx-remint-v4" ||
    profile === "max-cx-remint-v5"
  );
}

// Quality-floor slider stops: index 0 = strongest carrier break / most
// resolution loss, last = max quality. Every stop stays > the competitor's
// free-tier 768px output. Ordered low->high for a natural left->right slider.
const CX_QUALITY_FLOOR_STOPS: {
  value: CxRemintQualityFloor;
  label: string;
  longEdge: number;
  hint: string;
}[] = [
  { value: "floor", label: "Floor", longEdge: 896, hint: "Strongest removal · still sharper than competitor free" },
  { value: "strong", label: "Strong", longEdge: 960, hint: "Heavier removal, small quality trade" },
  { value: "balanced", label: "Balanced", longEdge: 1080, hint: "Recommended — reliable removal, high quality" },
  { value: "high", label: "High", longEdge: 1280, hint: "More detail, may need adaptive for stubborn images" },
  { value: "studio", label: "Studio", longEdge: 1536, hint: "Max quality, weakest carrier break" }
];

const expertRefinementPresets: Record<
  ExpertRefinementMode,
  ExpertRefinementSettings["techniques"]
> = {
  off: {
    pixel_alignment_break: { enabled: false, value: 0 },
    sensor_noise_luma: { enabled: false, value: 0 },
    lens_vignette: { enabled: false, value: 0 },
    compression_texture: { enabled: false, value: 0 },
    bayer_cfa_lite: { enabled: false, value: 0 },
    lens_character: { enabled: false, value: 0 },
    double_quantization: { enabled: false, value: 0 }
  },
  light: {
    pixel_alignment_break: { enabled: true, value: 0.25 },
    sensor_noise_luma: { enabled: true, value: 0.2 },
    lens_vignette: { enabled: true, value: 0.1 },
    compression_texture: { enabled: true, value: 0.2 },
    bayer_cfa_lite: { enabled: false, value: 0.3 },
    lens_character: { enabled: false, value: 0.2 },
    double_quantization: { enabled: false, value: 0.1 }
  },
  balanced: {
    pixel_alignment_break: { enabled: true, value: 0.4 },
    sensor_noise_luma: { enabled: true, value: 0.35 },
    lens_vignette: { enabled: true, value: 0.15 },
    compression_texture: { enabled: true, value: 0.3 },
    bayer_cfa_lite: { enabled: false, value: 0.5 },
    lens_character: { enabled: false, value: 0.2 },
    double_quantization: { enabled: false, value: 0.1 }
  },
  optical: {
    pixel_alignment_break: { enabled: true, value: 0.55 },
    sensor_noise_luma: { enabled: true, value: 0.5 },
    lens_vignette: { enabled: true, value: 0.2 },
    compression_texture: { enabled: true, value: 0.4 },
    bayer_cfa_lite: { enabled: true, value: 0.7 },
    lens_character: { enabled: true, value: 0.2 },
    double_quantization: { enabled: true, value: 0.1 }
  }
};

const expertTechniqueRows: Array<{
  key: ExpertRefinementTechnique;
  label: string;
  detail: string;
}> = [
  {
    key: "pixel_alignment_break",
    label: "Pixel Alignment Break",
    detail: "Subtle resample round-trip to soften rigid pixel alignment."
  },
  {
    key: "sensor_noise_luma",
    label: "Sensor Noise (luma)",
    detail: "Brightness-dependent texture modeled after camera sensor noise."
  },
  {
    key: "lens_vignette",
    label: "Lens Vignette",
    detail: "Very light edge falloff similar to real lenses."
  },
  {
    key: "compression_texture",
    label: "Compression Texture",
    detail: "Camera-like final JPEG texture and chroma subsampling."
  },
  {
    key: "bayer_cfa_lite",
    label: "Bayer CFA Lite",
    detail: "Subtle camera-sensor color-filter decorrelation without heavy softness."
  },
  {
    key: "lens_character",
    label: "Lens Character",
    detail: "Mild chromatic aberration and optical curvature."
  },
  {
    key: "double_quantization",
    label: "Double Quantization",
    detail: "Optional second JPEG pass for difficult expert cases."
  }
];

const maxMintTechniques: ExpertRefinementSettings["techniques"] = {
  pixel_alignment_break: { enabled: true, value: 0.71 },
  sensor_noise_luma: { enabled: true, value: 0.61 },
  lens_vignette: { enabled: true, value: 0.29 },
  compression_texture: { enabled: true, value: 0.47 },
  bayer_cfa_lite: { enabled: true, value: 0.07 },
  lens_character: { enabled: true, value: 0.2 },
  double_quantization: { enabled: true, value: 0.23 }
};

function cloneExpertPreset(mode: ExpertRefinementMode): ExpertRefinementSettings["techniques"] {
  return Object.fromEntries(
    Object.entries(expertRefinementPresets[mode]).map(([key, value]) => [
      key,
      { ...value }
    ])
  ) as ExpertRefinementSettings["techniques"];
}

function cloneMaxMintTechniques(): ExpertRefinementSettings["techniques"] {
  return Object.fromEntries(
    Object.entries(maxMintTechniques).map(([key, value]) => [key, { ...value }])
  ) as ExpertRefinementSettings["techniques"];
}

function initialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const saved = localStorage.getItem("resmarke:theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function MintApp() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [dragging, setDragging] = useState(false);
  const [stageView, setStageView] = useState<"clean" | "original">("clean");
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
  const [deepCleanProfile, setDeepCleanProfile] = useState<MintDeepCleanProfile>("standard");
  const [deepCleanMicroTextureJitter, setDeepCleanMicroTextureJitter] = useState(false);
  const [expertRefinementMode, setExpertRefinementMode] =
    useState<ExpertRefinementMode>("off");
  const [expertRefinementIntensity, setExpertRefinementIntensity] = useState(45);
  const [expertRefinementPreserveLines, setExpertRefinementPreserveLines] = useState(true);
  const [expertRefinementTechniques, setExpertRefinementTechniques] = useState(() =>
    cloneExpertPreset("off")
  );
  const [deepCleanOutputMode, setDeepCleanOutputMode] =
    useState<DeepCleanOutputMode>("sealed");
  // CX Remint controls (quality-floor slider, template/adaptive, iPhone EXIF).
  const [cxQualityFloor, setCxQualityFloor] = useState<CxRemintQualityFloor>("balanced");
  const [cxEngineMode, setCxEngineMode] = useState<CxRemintEngineMode>("template");
  const [cxIphoneExif, setCxIphoneExif] = useState(true);
  const [cxDevice, setCxDevice] = useState<CxRemintDevice>("auto");
  // Browser-side reframe (zoom + tilt + shear) applied before upload. No GPU.
  const [cxReframe, setCxReframe] = useState(true);
  const [cxReframePreset, setCxReframePreset] = useState<ReframePreset>("balanced");
  const [cxReframeZoom, setCxReframeZoom] = useState(REFRAME_PRESETS.balanced.zoom);
  const [cxReframeTilt, setCxReframeTilt] = useState(REFRAME_PRESETS.balanced.rotationDeg);
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

  // Credit cost model. Base actions are cheap; heavier variants cost more, and
  // the live totals are shown on each tile so the charge is never a surprise.
  const instantCost = useMemo(() => {
    let cost = 1;
    if (outputFormat !== "jpeg") cost += 1; // lossless / modern formats
    if (sizeMode !== "original") cost += 1; // resize / re-ratio pass
    return cost;
  }, [outputFormat, sizeMode]);

  const maxCost = useMemo(() => {
    const profileBase: Record<MintDeepCleanProfile, number> = {
      standard: 6,
      "standard-plus": 7,
      strong: 8,
      max: 10,
      "max-mint": 12,
      "max-remint": 12,
      "max-optimised-remint": 12,
      // Non-generative, so no GPU regen bill — priced below the regen profiles.
      "max-cx-remint": 10,
      // v2/v3/v4/v5 regenerate on GPU (to break SynthID) then launder — priciest.
      "max-cx-remint-v2": 13,
      "max-cx-remint-v3": 13,
      "max-cx-remint-v4": 13,
      "max-cx-remint-v5": 13
    };
    const refineAdd: Record<ExpertRefinementMode, number> = {
      off: 0,
      light: 1,
      balanced: 2,
      optical: 3
    };
    let cost = profileBase[deepCleanProfile];
    // Expert refinement only applies to the non-CX profiles.
    if (!isCxProfile(deepCleanProfile)) cost += refineAdd[expertRefinementMode];
    if (deepCleanProfile === "max" && deepCleanMicroTextureJitter) cost += 1;
    // Adaptive CX Remint runs repeated real-detector probes — reflect that.
    if (isCxProfile(deepCleanProfile) && cxEngineMode === "adaptive") cost += 2;
    if (deepCleanOutputMode === "sealed-stamped") cost += 1;
    return cost;
  }, [
    deepCleanProfile,
    expertRefinementMode,
    deepCleanMicroTextureJitter,
    deepCleanOutputMode,
    cxEngineMode
  ]);

  // CX Remint quality-floor slider: map the selected preset to its slider index
  // and metadata for the control's labels.
  const cxQualityFloorIndex = Math.max(
    0,
    CX_QUALITY_FLOOR_STOPS.findIndex((stop) => stop.value === cxQualityFloor)
  );
  const cxQualityFloorStop = CX_QUALITY_FLOOR_STOPS[cxQualityFloorIndex];

  // Re-Mint can run locally in demo mode. Sign-in upgrades to Supabase credits.
  const canProcess = !!file && state !== "processing" && credits.privacyCredits >= instantCost;
  const canQueueMax = !!file && credits.privacyCredits >= maxCost;
  const isAdminUi =
    !!userEmail &&
    config.adminEmails.length > 0 &&
    config.adminEmails.includes(userEmail.toLowerCase());

  const outputName = useMemo(() => {
    const ext = outputFormat === "png" ? "png" : outputFormat === "webp" ? "webp" : "jpg";
    if (!file) return `remint-output.${ext}`;
    const base = file.name.replace(/\.[^.]+$/, "");
    return `${base}-remint.${ext}`;
  }, [file, outputFormat]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("resmarke:theme", theme);
  }, [theme]);

  useEffect(() => {
    document.title = "Re-Mint It — Your images, reborn clean.";
  }, []);

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
      if (_event === "PASSWORD_RECOVERY") {
        setAuthMode("update");
        setAuthStatus("Choose a new password for this account.");
      }
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
    if (authMode === "reset") {
      if (!email) {
        setAuthStatus("Enter your email to receive a reset link.");
        return;
      }
      setAuthStatus("Sending reset link...");
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.href.split("#")[0]
      });
      setAuthStatus(error ? error.message : "Reset link sent. Check your email.");
      return;
    }

    if (!authPassword) {
      setAuthStatus("Enter your password.");
      return;
    }
    if (authPassword.length < 6) {
      setAuthStatus("Password must be at least 6 characters.");
      return;
    }

    if (authMode === "update") {
      setAuthStatus("Updating password...");
      const { error } = await supabase.auth.updateUser({ password: authPassword });
      setAuthStatus(error ? error.message : "Password updated.");
      if (!error) {
        setAuthPassword("");
        setAuthMode("signin");
      }
      return;
    }

    if (!email) {
      setAuthStatus("Enter your email.");
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

  async function spendCredits(amount: number) {
    if (amount <= 0) return;
    if (!supabase || !userId) {
      let snapshot = credits;
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
      setStageView("clean");
      await spendCredits(instantCost);
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
      setDeepCleanStatus("Sign in before queueing a Re-Mint Max job.");
      return;
    }
    if (credits.privacyCredits < maxCost) {
      setDeepCleanStatus(`Not enough credits — Re-Mint Max needs ${maxCost}.`);
      return;
    }

    let createdJob: DeepCleanJob | null = null;
    setDeepCleanStatus("Creating Re-Mint Max job...");
    try {
      const job = await createDeepCleanJob({
        file,
        creatorId,
        profile: deepCleanProfile,
        outputMode: deepCleanOutputMode,
        microTextureJitter: deepCleanProfile === "max" && deepCleanMicroTextureJitter,
        expertRefinement: isCxProfile(deepCleanProfile)
          ? undefined
          : buildExpertRefinementSettings(),
        cxRemint: isCxProfile(deepCleanProfile)
          ? {
              engineMode: cxEngineMode,
              qualityFloor: cxQualityFloor,
              acquisition: "balanced",
              iphoneExif: cxIphoneExif,
              device: cxDevice
            }
          : undefined
      });
      createdJob = job;
      setDeepCleanJob(job);
      // Optional browser-side reframe (zoom + tilt + shift) before upload —
      // desyncs the watermark/fingerprint grid with zero GPU cost.
      let uploadFile = file;
      if (isCxProfile(deepCleanProfile) && cxReframe) {
        try {
          setDeepCleanStatus("Reframing (browser-side)...");
          uploadFile = await reframeImageFile(
            file,
            reframeOptionsFor(cxReframePreset, {
              zoom: cxReframeZoom,
              rotationDeg: cxReframeTilt
            })
          );
        } catch {
          uploadFile = file; // reframe is best-effort; never block the job
        }
      }
      setDeepCleanStatus("Uploading private input...");
      await uploadDeepCleanInput(job, uploadFile);
      setDeepCleanStatus("Dispatching GPU worker...");
      await dispatchDeepCleanJob(job.id);
      await spendCredits(maxCost);
      setDeepCleanStatus(`Job ${job.id} is running · ${maxCost} credits used.`);
      startDeepCleanPolling(job.id);
    } catch (nextError) {
      if (createdJob) {
        await cancelDeepCleanJob(createdJob.id).catch(() => undefined);
      }
      setDeepCleanStatus(
        nextError instanceof Error ? nextError.message : "Re-Mint Max is not configured yet."
      );
    }
  }

  function chooseExpertRefinementMode(mode: ExpertRefinementMode) {
    setExpertRefinementMode(mode);
    setExpertRefinementTechniques(cloneExpertPreset(mode));
  }

  function chooseDeepCleanProfile(profile: MintDeepCleanProfile) {
    setDeepCleanProfile(profile);
    if (profile !== "max") setDeepCleanMicroTextureJitter(false);
    if (isCxProfile(profile)) {
      // CX Remint outputs a stripped, camera-re-acquired JPEG; expert refinement
      // and the seal-by-default do not apply.
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
      // Deep (v2/v3/v4) regenerate, and the flux fingerprint only dies at the
      // lower resolutions (live tests: clean at ~960px, still flagged at
      // 1280px). Snap the quality-floor slider to the Strong (960px) sweet spot.
      // v5 processes even lower (Floor 896, maximum removal) because it upscales
      // the OUTPUT back to >=1080 afterwards, so the floor is free of the size
      // requirement.
      if (profile === "max-cx-remint-v5") {
        setCxQualityFloor("floor");
      } else if (isCxDeepProfile(profile)) {
        setCxQualityFloor("strong");
      }
      return;
    }
    if (profile === "max-remint" || profile === "max-optimised-remint") {
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
      return;
    }
    if (profile !== "max-mint") return;

    setDeepCleanOutputMode("stripped");
    setExpertRefinementMode("optical");
    setExpertRefinementIntensity(97);
    setExpertRefinementPreserveLines(true);
    setExpertRefinementTechniques(cloneMaxMintTechniques());
  }

  function updateExpertTechnique(
    key: ExpertRefinementTechnique,
    patch: Partial<{ enabled: boolean; value: number }>
  ) {
    setExpertRefinementTechniques((current) => ({
      ...current,
      [key]: {
        ...current[key],
        ...patch
      }
    }));
  }

  function buildExpertRefinementSettings(): ExpertRefinementSettings {
    return {
      mode: expertRefinementMode,
      intensity: expertRefinementIntensity,
      preserve_straight_lines: expertRefinementPreserveLines,
      techniques: expertRefinementTechniques
    };
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
          setDeepCleanStatus(job.failureReason || "Re-Mint Max failed and the credit was released.");
          if (userId) void refreshSupabaseCredits(userId);
        } else {
          setDeepCleanStatus(`GPU job status: ${job.status}.`);
        }
      } catch (nextError) {
        setDeepCleanStatus(
          nextError instanceof Error ? nextError.message : "Could not refresh Re-Mint Max job."
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
  const showAuthPanel = hasSupabaseConfig && (!userId || authMode === "update");
  const authSummary =
    authMode === "signup"
      ? "Create account"
      : authMode === "reset"
        ? "Reset password"
        : authMode === "update"
          ? "Set password"
          : "Sign in";

  return (
    <div className="remint rm-app">
      <header className="rm-nav">
        <a className="rm-brand" href="/">
          <span className="rm-brand-mark">
            <Leaf size={18} aria-hidden="true" />
          </span>
          <span className="rm-brand-word">
            Re<span className="rm-brand-dash">‑</span>Mint<span className="rm-brand-it"> It</span>
          </span>
        </a>

        {!file ? (
          <nav className="rm-nav-links" aria-label="Sections">
            <a href="#how">How it works</a>
            <a href="#max">Re-Mint Max</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
        ) : null}

        <div className="rm-nav-right">
          <span className="rm-credits" title="Your Re-Mint credit balance">
            <Wallet size={15} aria-hidden="true" />
            <strong>{credits.privacyCredits}</strong>
            <span>credits</span>
          </span>

          {showAuthPanel ? (
            <details className="rm-pop" open={authMode === "update"}>
              <summary className="rm-pop-trigger">{authSummary}</summary>
              <div className="rm-pop-panel">
                {authMode !== "update" ? (
                  <div className="rm-seg rm-seg-sm" aria-label="Authentication mode">
                    <button
                      className={authMode === "signin" ? "is-active" : ""}
                      type="button"
                      onClick={() => {
                        setAuthMode("signin");
                        setAuthStatus("");
                      }}
                    >
                      Sign in
                    </button>
                    <button
                      className={authMode === "signup" ? "is-active" : ""}
                      type="button"
                      onClick={() => {
                        setAuthMode("signup");
                        setAuthStatus("");
                      }}
                    >
                      Sign up
                    </button>
                  </div>
                ) : null}
                <p className="rm-pop-note">
                  {authMode === "signin"
                    ? "Enter your email and password to access your credits."
                    : authMode === "signup"
                      ? "Create an account with email and password."
                      : authMode === "reset"
                        ? "Send a secure reset link to your inbox."
                        : "Set a new password to finish recovery."}
                </p>
                {authMode !== "update" ? (
                  <div className="rm-input-icon">
                    <Mail size={16} aria-hidden="true" />
                    <input
                      className="rm-input"
                      value={authEmail}
                      onChange={(event) => setAuthEmail(event.target.value)}
                      placeholder="you@email.com"
                      type="email"
                      autoComplete="email"
                    />
                  </div>
                ) : null}
                {authMode !== "reset" ? (
                  <div className="rm-input-icon">
                    <KeyRound size={16} aria-hidden="true" />
                    <input
                      className="rm-input"
                      value={authPassword}
                      onChange={(event) => setAuthPassword(event.target.value)}
                      placeholder={authMode === "update" ? "New password" : "Password"}
                      type="password"
                      autoComplete={authMode === "signin" ? "current-password" : "new-password"}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") void submitPasswordAuth();
                      }}
                    />
                  </div>
                ) : null}
                <button className="rm-btn rm-btn-primary rm-btn-block" type="button" onClick={submitPasswordAuth}>
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
                    className="rm-link"
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
                    className="rm-link"
                    type="button"
                    onClick={() => {
                      setAuthMode("signin");
                      setAuthStatus("");
                    }}
                  >
                    Back to sign in
                  </button>
                ) : null}
                {authStatus ? <p className="rm-pop-status">{authStatus}</p> : null}
              </div>
            </details>
          ) : hasSupabaseConfig && userId ? (
            <details className="rm-pop">
              <summary className="rm-pop-trigger rm-account-trigger">
                <UserRound size={15} aria-hidden="true" />
                <span>{userEmail || "Account"}</span>
              </summary>
              <div className="rm-pop-panel">
                <div className="rm-account-row">
                  <span>Credit balance</span>
                  <strong>{credits.privacyCredits}</strong>
                </div>
                <div className="rm-account-row">
                  <span>Re-Mint Max</span>
                  <strong>{credits.deepCleanCredits}</strong>
                </div>
                {isAdminUi ? <span className="rm-admin-chip">Developer admin</span> : null}
                <button className="rm-btn rm-btn-soft rm-btn-block" type="button" onClick={signOut}>
                  <LogOut size={16} aria-hidden="true" /> Sign out
                </button>
              </div>
            </details>
          ) : null}

          <button
            className="rm-icon-btn"
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>

      <main className="rm-main">
        {!file ? (
          <>
            <section className="rm-hero">
              <span className="rm-pill">
                <span className="rm-dot" /> Private by design · Runs in your browser
              </span>
              <h1 className="rm-hero-title">
                Your images,
                <br />
                <span className="rm-grad">reborn clean.</span>
              </h1>
              <p className="rm-hero-sub">
                Re-Mint It strips hidden metadata, lifts visible AI marks, and seals your work with a
                creator mark of its own — instantly, locally, and entirely on your device.
              </p>

              <Dropzone
                large
                previewUrl=""
                dragging={dragging}
                setDragging={setDragging}
                onPick={openPicker}
                onDropFile={onFileSelected}
              />

              <div className="rm-trust">
                <span>
                  <Lock size={14} aria-hidden="true" /> No uploads
                </span>
                <span>
                  <Zap size={14} aria-hidden="true" /> Instant, on-device
                </span>
                <span>
                  <Fingerprint size={14} aria-hidden="true" /> Creator Seal
                </span>
              </div>
            </section>

            <section className="rm-section" id="how">
              <SectionHead eyebrow="How it works" title="Three steps to a fresh mint" />
              <div className="rm-steps">
                <Step
                  n={1}
                  icon={<Upload size={18} aria-hidden="true" />}
                  title="Drop your image"
                  body="Add a JPG, PNG, or WebP. Everything runs locally — nothing is uploaded."
                />
                <Step
                  n={2}
                  icon={<Sparkles size={18} aria-hidden="true" />}
                  title="Re-Mint it"
                  body="Strip metadata, lift visible AI marks, and seal it with your custom creator seal."
                />
                <Step
                  n={3}
                  icon={<Download size={18} aria-hidden="true" />}
                  title="Export your way"
                  body="Download in your original format and size — or pick a custom type and ratio."
                />
              </div>
            </section>

            <section className="rm-section" id="max">
              <div className="rm-spotlight">
                <div className="rm-spotlight-glow" aria-hidden="true" />
                <div className="rm-spotlight-body">
                  <span className="rm-pill rm-pill-max">
                    <Cpu size={12} aria-hidden="true" /> Re-Mint Max · Beta
                  </span>
                  <h3>
                    When a browser isn’t enough,
                    <br />
                    <span className="rm-grad">bring in the GPU.</span>
                  </h3>
                  <p>
                    For stubborn, deeply embedded watermarks, Re-Mint Max runs an optional cloud GPU
                    pass with advanced profile choices far beyond what local processing can do. You
                    only pay after a job completes successfully.
                  </p>
                  <div className="rm-spotlight-feats">
                    <span>
                      <Check size={15} aria-hidden="true" /> Deep watermark reduction
                    </span>
                    <span>
                      <Check size={15} aria-hidden="true" /> Camera-grade refinement
                    </span>
                    <span>
                      <Check size={15} aria-hidden="true" /> Pay only on success
                    </span>
                  </div>
                  <button className="rm-btn rm-btn-max rm-btn-lg" type="button" onClick={openPicker}>
                    <Upload size={18} aria-hidden="true" /> Start with an image
                  </button>
                </div>
                <div className="rm-spotlight-art" aria-hidden="true">
                  <span className="rm-orbit rm-orbit-1" />
                  <span className="rm-orbit rm-orbit-2" />
                  <span className="rm-orbit-core">
                    <Cloud size={38} aria-hidden="true" />
                  </span>
                </div>
              </div>
            </section>

            <section className="rm-section" id="pricing">
              <SectionHead
                eyebrow="Pricing"
                title="Simple, creator-friendly pricing"
                subtitle="Start free. Upgrade only when you need more volume."
              />
              <div className="rm-tiers">
                <Tier
                  name="Free"
                  price="$0"
                  period="forever"
                  features={["3 Re-Mint exports", "Local, private processing", "Creator Seal"]}
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
                  features={["200 exports / month", "Priority processing", "All formats, sizes & ratios"]}
                  cta="Choose Pro"
                  onClick={openPicker}
                />
                <Tier
                  name="Pro+"
                  price="$29.99"
                  period="month"
                  features={["500 exports / month", "Re-Mint Max credits", "Everything in Pro"]}
                  cta="Choose Pro+"
                  onClick={openPicker}
                />
              </div>
              <p className="rm-fineprint">
                Card payments via Airwallex are launching soon — start re-minting free today, no
                account required.
              </p>
            </section>

            <section className="rm-section" id="faq">
              <SectionHead eyebrow="FAQ" title="Questions, answered" />
              <div className="rm-faq">
                <Faq
                  q="Are my images uploaded anywhere?"
                  a="No. Re-Mint runs entirely in your browser — your images never leave your device. Re-Mint Max is a separate, optional cloud feature you explicitly opt into."
                />
                <Faq
                  q="What exactly does Re-Mint It remove?"
                  a="All EXIF and metadata (GPS, device, software tags), via a clean pixel re-encode — plus optional removal of visible AI corner marks."
                />
                <Faq
                  q="What is the Creator Seal?"
                  a="A subtle custom creator seal embedded into your export so your work is recognizably yours. It's a creator mark, not a claim of original provenance."
                />
                <Faq
                  q="Which formats and sizes can I export?"
                  a="JPG, PNG, or WebP — at your original dimensions, a square, or any custom width and height you set."
                />
                <Faq q="What can I use it on?" a="Use Re-Mint It only on images you own or control." />
              </div>
            </section>

            <section className="rm-section">
              <div className="rm-cta">
                <h2>Re-mint your first image — free</h2>
                <p>No account, no uploads. It runs right here in your browser.</p>
                <button className="rm-btn rm-btn-primary rm-btn-lg" type="button" onClick={openPicker}>
                  <Upload size={18} aria-hidden="true" /> Drop an image
                </button>
              </div>
            </section>
          </>
        ) : (
          <section className="rm-studio">
            <div className="rm-studio-top">
              <div className="rm-file">
                <span className="rm-file-name">{file.name}</span>
                <span className="rm-file-meta">
                  {(file.size / 1_000_000).toFixed(2)} MB
                  {inputDims ? ` · ${inputDims.w}×${inputDims.h}` : ""}
                </span>
              </div>
              <div className="rm-studio-top-actions">
                <button className="rm-btn rm-btn-soft rm-btn-sm" type="button" onClick={openPicker}>
                  <Upload size={15} aria-hidden="true" /> Replace
                </button>
                <button className="rm-btn rm-btn-soft rm-btn-sm" type="button" onClick={resetAll}>
                  <RotateCcw size={15} aria-hidden="true" /> Start over
                </button>
              </div>
            </div>

            <div className="rm-studio-grid">
              <div className="rm-stage">
                <div className={`rm-stage-frame${state === "processing" ? " is-busy" : ""}`}>
                  <img
                    src={resultUrl && stageView === "clean" ? resultUrl : previewUrl}
                    alt={resultUrl && stageView === "clean" ? "Re-Minted result" : "Original image"}
                  />
                  {state === "processing" ? (
                    <div className="rm-stage-veil">
                      <Loader2 className="rm-spin" size={28} aria-hidden="true" />
                      <span>Re-minting…</span>
                    </div>
                  ) : null}
                  {resultUrl ? (
                    <div className="rm-stage-compare" role="group" aria-label="Compare original and result">
                      <button
                        className={stageView === "original" ? "is-active" : ""}
                        type="button"
                        onClick={() => setStageView("original")}
                      >
                        Original
                      </button>
                      <button
                        className={stageView === "clean" ? "is-active" : ""}
                        type="button"
                        onClick={() => setStageView("clean")}
                      >
                        Re-Minted
                      </button>
                    </div>
                  ) : null}
                </div>

                {!resultUrl && state !== "processing" ? (
                  <p className="rm-stage-hint">
                    <Scan size={14} aria-hidden="true" /> Your re-minted image will appear here
                  </p>
                ) : null}

                {report ? (
                  <div className="rm-metrics">
                    <RmMetric label="Metadata" value="Stripped" />
                    <RmMetric
                      label="Visible cleanup"
                      value={report.visibleCleanupApplied ? `${report.visibleCleanupPixels} px` : "None"}
                    />
                    <RmMetric label="Seal" value="Creator Seal" />
                    <RmMetric label="Hash" value={resultHash.slice(0, 12)} />
                  </div>
                ) : null}
              </div>

              <aside className="rm-rail">
                <div className="rm-card rm-instant">
                  <div className="rm-card-head">
                    <span className="rm-card-icon">
                      <Sparkles size={18} aria-hidden="true" />
                    </span>
                    <div className="rm-card-headtext">
                      <div className="rm-card-title">Instant Re-Mint</div>
                      <div className="rm-card-sub">
                        <Lock size={11} aria-hidden="true" /> On-device · Private
                      </div>
                    </div>
                    <span className="rm-cost" title="Credits charged per export. Some output options cost more.">
                      <Wallet size={13} aria-hidden="true" />
                      {instantCost} {instantCost === 1 ? "credit" : "credits"}
                    </span>
                  </div>
                  <p className="rm-card-desc">
                    Strip metadata, lift AI marks, and seal — instantly, on your device.
                  </p>

                  <button
                    className="rm-btn rm-btn-primary rm-btn-lg rm-btn-block"
                    type="button"
                    disabled={!canProcess}
                    onClick={processPrivacyMax}
                  >
                    {state === "processing" ? (
                      <>
                        <Loader2 className="rm-spin" size={18} aria-hidden="true" /> Re-minting…
                      </>
                    ) : (
                      <>
                        <Sparkles size={18} aria-hidden="true" /> {resultBlob ? "Re-Mint again" : "Re-Mint image"}
                      </>
                    )}
                  </button>

                  {resultBlob ? (
                    <a className="rm-btn rm-btn-soft rm-btn-block" href={resultUrl} download={outputName}>
                      <Download size={18} aria-hidden="true" /> Download{" "}
                      {outputFormat === "jpeg" ? "JPG" : outputFormat.toUpperCase()}
                    </a>
                  ) : null}

                  {state === "error" ? <p className="rm-error">{error}</p> : null}

                  {credits.privacyCredits < instantCost ? (
                    <div className="rm-warn">
                      <span>Not enough credits for this export.</span>
                      {credits.mode === "demo" ? (
                        <button type="button" onClick={() => setCredits(grantLocalPrivacyCredits(15))}>
                          Add 15
                        </button>
                      ) : null}
                    </div>
                  ) : null}

                  <details className="rm-disc">
                    <summary>
                      <SlidersHorizontal size={15} aria-hidden="true" /> Advanced output &amp; seal
                      <ChevronDown className="rm-chev" size={16} aria-hidden="true" />
                    </summary>
                    <div className="rm-disc-body">
                      <div className="rm-field">
                        <span className="rm-field-label">Format</span>
                        <div className="rm-seg" aria-label="Output format">
                          <button
                            className={outputFormat === "jpeg" ? "is-active" : ""}
                            type="button"
                            onClick={() => setOutputFormat("jpeg")}
                          >
                            JPG
                          </button>
                          <button
                            className={outputFormat === "png" ? "is-active" : ""}
                            type="button"
                            onClick={() => setOutputFormat("png")}
                          >
                            PNG
                          </button>
                          <button
                            className={outputFormat === "webp" ? "is-active" : ""}
                            type="button"
                            onClick={() => setOutputFormat("webp")}
                          >
                            WebP
                          </button>
                        </div>
                      </div>

                      <label className="rm-field">
                        <span className="rm-field-label">Size &amp; ratio</span>
                        <select
                          className="rm-select"
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
                        <div className="rm-dim">
                          <label className="rm-field">
                            <span className="rm-field-label">Width</span>
                            <input
                              className="rm-input"
                              type="number"
                              min={16}
                              max={8192}
                              value={customWidth || ""}
                              onChange={(event) => setCustomWidth(Number(event.target.value))}
                            />
                          </label>
                          <span className="rm-dim-x">×</span>
                          <label className="rm-field">
                            <span className="rm-field-label">Height</span>
                            <input
                              className="rm-input"
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
                        <div className="rm-field">
                          <span className="rm-field-label">Fit</span>
                          <div className="rm-seg" aria-label="Image fit">
                            <button
                              className={fit === "contain" ? "is-active" : ""}
                              type="button"
                              onClick={() => setFit("contain")}
                            >
                              Contain
                            </button>
                            <button
                              className={fit === "cover" ? "is-active" : ""}
                              type="button"
                              onClick={() => setFit("cover")}
                            >
                              Cover
                            </button>
                          </div>
                        </div>
                      ) : null}

                      {outputFormat !== "png" ? (
                        <label className="rm-range">
                          <span className="rm-field-label">
                            Quality <em>{Math.round(jpegQuality * 100)}%</em>
                          </span>
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

                      <div className="rm-disc-divider" />

                      <label className="rm-field">
                        <span className="rm-field-label">Creator ID</span>
                        <input
                          className="rm-input"
                          value={creatorId}
                          onChange={(event) => setCreatorId(event.target.value)}
                          placeholder="creator@example.com"
                        />
                      </label>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={cleanVisibleMarks}
                          onChange={(event) => setCleanVisibleMarks(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Clean visible AI corner marks</span>
                      </label>

                      <label className="rm-range">
                        <span className="rm-field-label">
                          Creator Seal strength <em>{markStrength}</em>
                        </span>
                        <input
                          type="range"
                          min="1"
                          max="8"
                          value={markStrength}
                          onChange={(event) => setMarkStrength(Number(event.target.value))}
                        />
                      </label>
                    </div>
                  </details>
                </div>

                <div className="rm-card rm-max" id="max">
                  <div className="rm-max-glow" aria-hidden="true" />
                  <div className="rm-card-head">
                    <span className="rm-card-icon rm-card-icon-max">
                      <Cloud size={18} aria-hidden="true" />
                    </span>
                    <div className="rm-card-headtext">
                      <div className="rm-card-title">
                        Re-Mint Max <span className="rm-badge">GPU</span>
                      </div>
                      <div className="rm-card-sub">
                        <Cpu size={11} aria-hidden="true" /> Cloud GPU processing · Beta
                      </div>
                    </div>
                    <span className="rm-cost rm-cost-max" title="Heavier profiles, refinement and stamping cost more credits.">
                      <Wallet size={13} aria-hidden="true" />
                      {maxCost} credits
                    </span>
                  </div>
                  <p className="rm-card-desc">
                    Cloud GPU processing for stubborn, deeply embedded watermarks — far beyond what a
                    browser can do.
                  </p>

                  <div className="rm-field-grid">
                    <label className="rm-field">
                      <span className="rm-field-label">Profile</span>
                      <select
                        className="rm-select"
                        value={deepCleanProfile}
                        onChange={(event) => chooseDeepCleanProfile(event.target.value as MintDeepCleanProfile)}
                      >
                        <option value="standard">Standard</option>
                        <option value="standard-plus">Standard+</option>
                        <option value="strong">Strong</option>
                        <option value="max">Max (Expert)</option>
                        <option value="max-mint">Max Mint</option>
                        <option value="max-remint">Max ReMint</option>
                        <option value="max-optimised-remint">Max Optimised ReMint</option>
                        <option value="max-cx-remint">CX Remint (non-generative)</option>
                        <option value="max-cx-remint-v2">CX Remint v2 · Deep (removes SynthID)</option>
                        <option value="max-cx-remint-v3">CX Remint v3 · Deep + colour restore</option>
                        <option value="max-cx-remint-v4">CX Remint v4 · Deep + tone match + realism</option>
                        <option value="max-cx-remint-v5">CX Remint v5 · Max removal + upscale to 1080+ (recommended)</option>
                      </select>
                    </label>
                    <label className="rm-field">
                      <span className="rm-field-label">Output</span>
                      <select
                        className="rm-select"
                        value={deepCleanOutputMode}
                        onChange={(event) => setDeepCleanOutputMode(event.target.value as DeepCleanOutputMode)}
                      >
                        <option value="stripped">Stripped only</option>
                        <option value="sealed">Stripped + Creator Seal</option>
                        <option value="sealed-stamped">Stripped + seal + stamp</option>
                      </select>
                    </label>
                  </div>

                  {deepCleanProfile === "max" ? (
                    <label className="rm-switch">
                      <input
                        type="checkbox"
                        checked={deepCleanMicroTextureJitter}
                        onChange={(event) => setDeepCleanMicroTextureJitter(event.target.checked)}
                      />
                      <span className="rm-switch-track" aria-hidden="true">
                        <span className="rm-switch-thumb" />
                      </span>
                      <span>Micro-texture jitter</span>
                    </label>
                  ) : null}

                  {deepCleanProfile === "max-remint" || deepCleanProfile === "max-optimised-remint" ? (
                    <div className="rm-disc-note">
                      {deepCleanProfile === "max-remint"
                        ? "Max ReMint skips global regeneration and uses non-generative statistical reshaping, local repair candidates, and quality gates for creator-AI images."
                        : "Max Optimised ReMint uses moderate regeneration with idempotency, unsharp restoration, PSNR/SSIM gates, and light optimised finalization."}
                    </div>
                  ) : null}

                  {isCxProfile(deepCleanProfile) ? (
                    <div className="rm-cx-panel">
                      <div className="rm-field">
                        <span className="rm-field-label">Mode</span>
                        <div className="rm-seg" role="radiogroup" aria-label="CX Remint mode">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={cxEngineMode === "template"}
                            className={cxEngineMode === "template" ? "is-active" : ""}
                            onClick={() => setCxEngineMode("template")}
                          >
                            Optimised template
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={cxEngineMode === "adaptive"}
                            className={cxEngineMode === "adaptive" ? "is-active" : ""}
                            onClick={() => setCxEngineMode("adaptive")}
                          >
                            Adaptive (detector-gated)
                          </button>
                        </div>
                        <p className="rm-hint">
                          {cxEngineMode === "template"
                            ? "Fast, predictable single pass at the quality-floor you pick below."
                            : "Escalates strength against a live AI detector and stops at the first pass — the least quality loss that clears. +2 credits."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">
                          Quality floor · {cxQualityFloorStop.label} (~{cxQualityFloorStop.longEdge}px)
                        </span>
                        <input
                          className="rm-cx-slider"
                          type="range"
                          min={0}
                          max={CX_QUALITY_FLOOR_STOPS.length - 1}
                          step={1}
                          value={cxQualityFloorIndex}
                          onChange={(event) =>
                            setCxQualityFloor(CX_QUALITY_FLOOR_STOPS[Number(event.target.value)].value)
                          }
                        />
                        <div className="rm-range-ends">
                          <span>Strongest removal</span>
                          <span>Max quality</span>
                        </div>
                        <p className="rm-hint">{cxQualityFloorStop.hint}</p>
                      </div>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={cxIphoneExif}
                          onChange={(event) => setCxIphoneExif(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Rebuild iPhone photo metadata (EXIF)</span>
                      </label>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={cxReframe}
                          onChange={(event) => setCxReframe(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Reframe: zoom + tilt + shear (browser-side, no GPU)</span>
                      </label>

                      {cxReframe ? (
                        <div className="rm-cx-subpanel">
                          <div className="rm-field">
                            <span className="rm-field-label">Reframe strength</span>
                            <div className="rm-seg rm-seg-sm" role="radiogroup" aria-label="Reframe strength">
                              {(["subtle", "balanced", "strong"] as ReframePreset[]).map((p) => (
                                <button
                                  key={p}
                                  type="button"
                                  role="radio"
                                  aria-checked={cxReframePreset === p}
                                  className={cxReframePreset === p ? "is-active" : ""}
                                  onClick={() => {
                                    setCxReframePreset(p);
                                    setCxReframeZoom(REFRAME_PRESETS[p].zoom);
                                    setCxReframeTilt(REFRAME_PRESETS[p].rotationDeg);
                                  }}
                                >
                                  {p === "subtle" ? "Subtle" : p === "balanced" ? "Balanced" : "Strong"}
                                </button>
                              ))}
                            </div>
                          </div>

                          <div className="rm-field">
                            <span className="rm-field-label">
                              Tilt · {cxReframeTilt.toFixed(1)}° (the part that breaks the fingerprint)
                            </span>
                            <input
                              className="rm-cx-slider"
                              type="range"
                              min={0}
                              max={5}
                              step={0.1}
                              value={cxReframeTilt}
                              onChange={(event) => setCxReframeTilt(Number(event.target.value))}
                            />
                          </div>

                          <div className="rm-field">
                            <span className="rm-field-label">
                              Zoom · {Math.round((cxReframeZoom - 1) * 100)}% crop (keep low for quality)
                            </span>
                            <input
                              className="rm-cx-slider"
                              type="range"
                              min={1.0}
                              max={1.1}
                              step={0.005}
                              value={cxReframeZoom}
                              onChange={(event) => setCxReframeZoom(Number(event.target.value))}
                            />
                            <p className="rm-hint">
                              Zoom auto-raises to whatever the tilt needs to avoid empty corners, so a
                              low zoom with high tilt still fills the frame.
                            </p>
                          </div>
                        </div>
                      ) : null}

                      {cxIphoneExif ? (
                        <label className="rm-field">
                          <span className="rm-field-label">Device</span>
                          <select
                            className="rm-select"
                            value={cxDevice}
                            onChange={(event) => setCxDevice(event.target.value as CxRemintDevice)}
                          >
                            <option value="auto">Auto (pick a recent iPhone)</option>
                            <option value="iphone-16-pro-max">iPhone 16 Pro Max</option>
                            <option value="iphone-16-pro">iPhone 16 Pro</option>
                            <option value="iphone-16">iPhone 16</option>
                            <option value="iphone-15-pro-max">iPhone 15 Pro Max</option>
                            <option value="iphone-15-pro">iPhone 15 Pro</option>
                            <option value="iphone-15">iPhone 15</option>
                            <option value="iphone-14-pro">iPhone 14 Pro</option>
                          </select>
                        </label>
                      ) : null}

                      <div className="rm-disc-note">
                        {deepCleanProfile === "max-cx-remint-v5"
                          ? "CX Remint v5 (recommended) processes at the LOWEST floor (896px) for maximum fingerprint removal, then upscales the delivered image back to ~1440px with sharpening + fresh grain — so you get both max removal AND a 1080+ output. Upscaling can't re-add the removed fingerprint, so detection stays clean. Everything from v4 (SynthID regen, histogram tone match, realism) is included. Detector scores are stochastic run-to-run — for CONSISTENT clears, wire the live detector and use Adaptive mode."
                          : deepCleanProfile === "max-cx-remint-v4"
                          ? "CX Remint v4 regenerates to remove SynthID, full-histogram tone-matches to the original (fixes over-contrast), with realism boost. v5 adds max-removal-at-low-res + upscale-back — prefer v5 for the 1080+ requirement."
                          : deepCleanProfile === "max-cx-remint-v3"
                          ? "CX Remint v3 regenerates to remove SynthID then restores the original's colour palette (mean/std). v4 adds full tone matching + realism — prefer v4 unless A/B testing."
                          : deepCleanProfile === "max-cx-remint-v2"
                          ? "CX Remint v2 (Deep) regenerates the frame to remove Google SynthID, then launders off the diffusion fingerprint with resampling + spectral reshaping. v3 adds colour restoration on top — prefer v3 unless you're A/B testing."
                          : "CX Remint is non-generative: it breaks the diffusion fingerprint by resampling and re-acquires a real-camera signature without stamping a new one. Note: it does NOT remove Google SynthID — if the image is SynthID-watermarked, use v3 (Deep). Output never drops below 896px."}
                      </div>
                    </div>
                  ) : null}

                  <button
                    className="rm-btn rm-btn-max rm-btn-lg rm-btn-block"
                    type="button"
                    onClick={startDeepCleanBeta}
                    disabled={!canQueueMax}
                  >
                    <Cloud size={18} aria-hidden="true" /> Queue GPU job · {maxCost} credits
                  </button>

                  {deepCleanProfile !== "max-remint" &&
                  deepCleanProfile !== "max-optimised-remint" &&
                  !isCxProfile(deepCleanProfile) ? (
                    <details className="rm-disc">
                      <summary>
                        <SlidersHorizontal size={15} aria-hidden="true" /> Expert refinement
                        <ChevronDown className="rm-chev" size={16} aria-hidden="true" />
                      </summary>
                      <div className="rm-disc-body">
                        <p className="rm-disc-note">
                          Optional final camera-style texture pass for difficult outputs.
                        </p>
                        <div className="rm-field">
                          <span className="rm-field-label">Mode</span>
                          <div className="rm-seg" aria-label="Expert refinement mode">
                            {(["off", "light", "balanced", "optical"] as ExpertRefinementMode[]).map((mode) => (
                              <button
                                className={expertRefinementMode === mode ? "is-active" : ""}
                                key={mode}
                                type="button"
                                onClick={() => chooseExpertRefinementMode(mode)}
                              >
                                {mode === "off"
                                  ? "Off"
                                  : mode === "light"
                                    ? "Light"
                                    : mode === "balanced"
                                      ? "Balanced"
                                      : "Optical"}
                              </button>
                            ))}
                          </div>
                        </div>
                        <label className="rm-range">
                          <span className="rm-field-label">
                            Intensity <em>{expertRefinementIntensity}%</em>
                          </span>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={expertRefinementIntensity}
                            disabled={expertRefinementMode === "off"}
                            onChange={(event) => setExpertRefinementIntensity(Number(event.target.value))}
                          />
                        </label>

                        <details className="rm-disc rm-disc-nested">
                          <summary>
                            Manual technique controls
                            <ChevronDown className="rm-chev" size={15} aria-hidden="true" />
                          </summary>
                          <div className="rm-disc-body">
                            {expertTechniqueRows.map((row) => {
                              const techConfig = expertRefinementTechniques[row.key];
                              const disabled = expertRefinementMode === "off";
                              const lockedByLines =
                                row.key === "lens_character" && expertRefinementPreserveLines;
                              return (
                                <div className="rm-tech" key={row.key}>
                                  <label className="rm-switch rm-switch-sm">
                                    <input
                                      type="checkbox"
                                      checked={lockedByLines ? false : techConfig.enabled}
                                      disabled={disabled || lockedByLines}
                                      onChange={(event) =>
                                        updateExpertTechnique(row.key, { enabled: event.target.checked })
                                      }
                                    />
                                    <span className="rm-switch-track" aria-hidden="true">
                                      <span className="rm-switch-thumb" />
                                    </span>
                                    <span>{row.label}</span>
                                  </label>
                                  <label className="rm-range rm-tech-range">
                                    <span className="rm-field-label">
                                      <em>
                                        {techConfig.value.toFixed(2)}
                                        {lockedByLines ? " · guarded" : ""}
                                      </em>
                                    </span>
                                    <input
                                      type="range"
                                      min="0"
                                      max="1"
                                      step="0.01"
                                      value={techConfig.value}
                                      disabled={disabled || !techConfig.enabled || lockedByLines}
                                      onChange={(event) =>
                                        updateExpertTechnique(row.key, { value: Number(event.target.value) })
                                      }
                                    />
                                  </label>
                                  <p className="rm-tech-detail">{row.detail}</p>
                                </div>
                              );
                            })}
                            <label className="rm-switch">
                              <input
                                type="checkbox"
                                checked={expertRefinementPreserveLines}
                                disabled={expertRefinementMode === "off"}
                                onChange={(event) => setExpertRefinementPreserveLines(event.target.checked)}
                              />
                              <span className="rm-switch-track" aria-hidden="true">
                                <span className="rm-switch-thumb" />
                              </span>
                              <span>Preserve straight lines for architecture/interiors</span>
                            </label>
                          </div>
                        </details>
                      </div>
                    </details>
                  ) : null}

                  <p className="rm-status">
                    {hasSupabaseConfig
                      ? deepCleanStatus || "Connected. Queue a job to run it on the GPU worker."
                      : "Set Supabase env vars to enable Re-Mint Max."}
                  </p>

                  {deepCleanJob && ["processing", "completed", "failed"].includes(deepCleanJob.status) ? (
                    <div className="rm-jobresult">
                      <div className="rm-jobframe">
                        {deepCleanJob.outputUrl ? (
                          <img src={deepCleanJob.outputUrl} alt="Re-Mint Max result preview" />
                        ) : deepCleanJob.status === "failed" ? (
                          <div className="rm-jobempty">
                            <ImageOff size={24} aria-hidden="true" />
                            <span>{deepCleanJob.failureReason || "Re-Mint Max failed."}</span>
                          </div>
                        ) : (
                          <div className="rm-jobempty">
                            <Loader2 className="rm-spin" size={24} aria-hidden="true" />
                            <span>GPU worker is processing…</span>
                          </div>
                        )}
                      </div>
                      {deepCleanJob.status === "completed" ? (
                        <>
                          <div className="rm-metrics rm-metrics-sm">
                            <RmMetric label="Status" value="Completed" />
                            <RmMetric
                              label="Runtime"
                              value={deepCleanJob.runtimeMs ? `${(deepCleanJob.runtimeMs / 1000).toFixed(1)}s` : "—"}
                            />
                            <RmMetric label="GPU" value={deepCleanJob.gpuType || "—"} />
                            <RmMetric label="Output" value={deepCleanOutputMode} />
                          </div>
                          <a
                            className="rm-btn rm-btn-max rm-btn-block"
                            href={deepCleanJob.outputUrl}
                            download={deepCleanJob.outputName ?? "IMG_0000.JPG"}
                          >
                            <Download size={18} aria-hidden="true" /> Download result
                          </a>
                        </>
                      ) : deepCleanJob.status === "failed" ? (
                        <p className="rm-error">
                          {deepCleanJob.failureReason || "Re-Mint Max failed; your credit was released."}
                        </p>
                      ) : (
                        <p className="rm-status">Hang tight — processing on the GPU…</p>
                      )}
                    </div>
                  ) : null}
                </div>
              </aside>
            </div>

            {isAdminUi ? (
              <details className="rm-card rm-admin">
                <summary className="rm-admin-summary">
                  <span className="rm-card-icon">
                    <Gauge size={18} aria-hidden="true" />
                  </span>
                  <span className="rm-card-title">Admin GPU standby</span>
                  <span className="rm-badge rm-badge-muted">Private</span>
                  <ChevronDown className="rm-chev" size={18} aria-hidden="true" />
                </summary>
                <div className="rm-admin-body">
                  <p className="rm-card-desc">
                    Control RunPod worker cost for your admin sessions. Sleep shuts the worker down
                    quickly; warm window keeps it ready briefly after a job; keep warm holds one active
                    worker until you switch it off.
                  </p>
                  <div className="rm-metrics">
                    <RmMetric label="Endpoint" value={adminEndpoint?.name ?? "Not loaded"} />
                    <RmMetric label="Active" value={String(adminEndpoint?.workersMin ?? "—")} />
                    <RmMetric label="Max" value={String(adminEndpoint?.workersMax ?? "—")} />
                    <RmMetric
                      label="Idle timeout"
                      value={typeof adminEndpoint?.idleTimeout === "number" ? `${adminEndpoint.idleTimeout}s` : "—"}
                    />
                  </div>
                  <div className="rm-field-grid rm-field-grid-3">
                    <label className="rm-field">
                      <span className="rm-field-label">Idle timeout</span>
                      <input
                        className="rm-input"
                        type="number"
                        min={5}
                        max={3600}
                        value={adminIdleTimeout}
                        onChange={(event) => setAdminIdleTimeout(Number(event.target.value))}
                      />
                    </label>
                    <label className="rm-field">
                      <span className="rm-field-label">Active workers</span>
                      <select
                        className="rm-select"
                        value={adminWorkersMin}
                        onChange={(event) => setAdminWorkersMin(Number(event.target.value))}
                      >
                        <option value={0}>0 · scale to zero</option>
                        <option value={1}>1 · keep warm</option>
                      </select>
                    </label>
                    <label className="rm-field">
                      <span className="rm-field-label">Max workers</span>
                      <select
                        className="rm-select"
                        value={adminWorkersMax}
                        onChange={(event) => setAdminWorkersMax(Number(event.target.value))}
                      >
                        <option value={1}>1</option>
                        <option value={2}>2</option>
                        <option value={3}>3</option>
                      </select>
                    </label>
                  </div>
                  <div className="rm-admin-actions">
                    <button className="rm-btn rm-btn-soft" type="button" disabled={adminBusy} onClick={refreshAdminEndpoint}>
                      Refresh
                    </button>
                    <button
                      className="rm-btn rm-btn-soft"
                      type="button"
                      disabled={adminBusy}
                      onClick={() => applyAdminPreset("sleep")}
                    >
                      Sleep now
                    </button>
                    <button
                      className="rm-btn rm-btn-soft"
                      type="button"
                      disabled={adminBusy}
                      onClick={() => applyAdminPreset("warm-window")}
                    >
                      Warm window
                    </button>
                    <button
                      className="rm-btn rm-btn-primary"
                      type="button"
                      disabled={adminBusy}
                      onClick={() => applyAdminPreset("keep-warm")}
                    >
                      Keep warm
                    </button>
                    <button
                      className="rm-btn rm-btn-soft"
                      type="button"
                      disabled={adminBusy}
                      onClick={() => applyAdminPreset("manual")}
                    >
                      Apply manual
                    </button>
                  </div>
                  <p className="rm-status">
                    {adminStatus || "Admin controls are available for this signed-in account."}
                  </p>
                </div>
              </details>
            ) : null}
          </section>
        )}
      </main>

      <input
        ref={fileInputRef}
        className="rm-sr-only"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(event) => onFileSelected(event.target.files?.item(0) ?? null)}
      />

      <footer className="rm-footer">
        <div className="rm-footer-inner">
          <a className="rm-brand rm-brand-sm" href="/">
            <span className="rm-brand-mark">
              <Leaf size={15} aria-hidden="true" />
            </span>
            <span className="rm-brand-word">
              Re<span className="rm-brand-dash">‑</span>Mint<span className="rm-brand-it"> It</span>
            </span>
          </a>
          <span className="rm-footer-note">
            Use only on images you own or control. The Creator Seal is a creator mark, not proof of
            provenance.
          </span>
          <span className="rm-footer-copy">© {new Date().getFullYear()} Re-Mint It</span>
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
      className={["rm-drop", large ? "rm-drop-lg" : "", previewUrl ? "has-image" : "", dragging ? "is-drag" : ""]
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
        <div className="rm-drop-inner">
          <span className="rm-drop-icon">
            <Upload size={26} aria-hidden="true" />
          </span>
          <div className="rm-drop-title">Drop your image to begin</div>
          <div className="rm-drop-sub">
            or <span className="rm-drop-browse">browse files</span> · JPEG, PNG, WebP up to 25MB
          </div>
        </div>
      )}
    </div>
  );
}

function RmMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rm-metric">
      <span>{label}</span>
      <strong>{value}</strong>
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
    <div className="rm-section-head">
      <span className="rm-eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
    </div>
  );
}

function Step({ n, icon, title, body }: { n: number; icon: ReactNode; title: string; body: string }) {
  return (
    <div className="rm-step">
      <span className="rm-step-icon">{icon}</span>
      <span className="rm-step-n">{String(n).padStart(2, "0")}</span>
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
    <div className={featured ? "rm-tier is-featured" : "rm-tier"}>
      {featured ? (
        <span className="rm-tier-badge">
          <Sparkles size={12} aria-hidden="true" /> Most popular
        </span>
      ) : null}
      <div className="rm-tier-name">{name}</div>
      <div className="rm-tier-price">
        <strong>{price}</strong>
        <span>/ {period}</span>
      </div>
      <ul className="rm-tier-feats">
        {features.map((feature) => (
          <li key={feature}>
            <Check size={15} aria-hidden="true" /> {feature}
          </li>
        ))}
      </ul>
      <button
        className={featured ? "rm-btn rm-btn-primary rm-btn-block" : "rm-btn rm-btn-soft rm-btn-block"}
        type="button"
        onClick={onClick}
      >
        {cta} <ArrowRight size={16} aria-hidden="true" />
      </button>
    </div>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <details className="rm-faq-item">
      <summary>
        {q}
        <ChevronDown className="rm-chev" size={18} aria-hidden="true" />
      </summary>
      <p>{a}</p>
    </details>
  );
}
