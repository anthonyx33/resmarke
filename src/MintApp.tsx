import {
  Archive,
  ArrowRight,
  Check,
  ChevronDown,
  Cloud,
  Cpu,
  Download,
  Fingerprint,
  Gauge,
  GripVertical,
  ImageOff,
  Images,
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
  Trash2,
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
  type CxRemintDevice,
  type CxRemintResolutionMode,
  type CxRemintAcquisition
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
type QueueItemStatus =
  | "ready"
  | "preparing"
  | "uploading"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

type ImageQueueItem = {
  id: string;
  file: File;
  previewUrl: string;
  width?: number;
  height?: number;
  status: QueueItemStatus;
  job?: DeepCleanJob;
  error?: string;
};

const MAX_QUEUE_IMAGES = 20;
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;

type MintDeepCleanProfile =
  | DeepCleanProfile
  | "max-remint"
  | "max-optimised-remint"
  | "max-cx-remint"
  | "max-cx-remint-v2"
  | "max-cx-remint-v3"
  | "max-cx-remint-v4"
  | "max-cx-remint-v5"
  | "ds-remint-v6"
  | "ds-remint-v7"
  | "ds-remint-v8"
  | "ds-remint-v8.1"
  | "ds-remint-v8.2"
  | "ds-remint-v8.3"
  | "ds-remint-v8.8"
  | "ds-remint-v8.9";

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
  const queueSequenceRef = useRef(0);
  const imageQueueRef = useRef<ImageQueueItem[]>([]);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [imageQueue, setImageQueue] = useState<ImageQueueItem[]>([]);
  const [activeQueueId, setActiveQueueId] = useState("");
  const [draggedQueueId, setDraggedQueueId] = useState("");
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchNotice, setBatchNotice] = useState("");
  const [zipBusy, setZipBusy] = useState(false);
  const [downloadingItemId, setDownloadingItemId] = useState("");
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
  const [deepCleanProfile, setDeepCleanProfile] =
    useState<MintDeepCleanProfile>("max-cx-remint-v5");
  const [deepCleanMicroTextureJitter, setDeepCleanMicroTextureJitter] = useState(false);
  const [expertRefinementMode, setExpertRefinementMode] =
    useState<ExpertRefinementMode>("off");
  const [expertRefinementIntensity, setExpertRefinementIntensity] = useState(45);
  const [expertRefinementPreserveLines, setExpertRefinementPreserveLines] = useState(true);
  const [expertRefinementTechniques, setExpertRefinementTechniques] = useState(() =>
    cloneExpertPreset("off")
  );
  const [deepCleanOutputMode, setDeepCleanOutputMode] =
    useState<DeepCleanOutputMode>("stripped");
  // CX Remint controls (quality-floor slider, template/adaptive, iPhone EXIF).
  const [cxQualityFloor, setCxQualityFloor] = useState<CxRemintQualityFloor>("strong");
  const [cxEngineMode, setCxEngineMode] = useState<CxRemintEngineMode>("template");
  const [cxIphoneExif, setCxIphoneExif] = useState(true);
  const [cxDevice, setCxDevice] = useState<CxRemintDevice>("iphone-15");
  const [cxResolutionMode, setCxResolutionMode] =
    useState<CxRemintResolutionMode>("off");
  const [cxResolutionX, setCxResolutionX] = useState(72);
  const [cxResolutionY, setCxResolutionY] = useState(72);
  // DS ReMint V6 controls (dedicated main toggle, see the Re-Mint Max card).
  const [dsV6QualityFloor, setDsV6QualityFloor] =
    useState<CxRemintQualityFloor>("balanced");
  const [dsV6EngineMode, setDsV6EngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [dsV6Acquisition, setDsV6Acquisition] = useState<CxRemintAcquisition>("balanced");
  const [dsV6IphoneExif, setDsV6IphoneExif] = useState(true);
  const [dsV6OutputTarget, setDsV6OutputTarget] = useState("");
  // Expert tuning (A/B-tuned defaults from the worker validation runs).
  const [dsV6Sharpen, setDsV6Sharpen] = useState(24);
  const [dsV6Texture, setDsV6Texture] = useState(90);
  const [dsV6Spectral, setDsV6Spectral] = useState(30);
  // DS ReMint V7 controls (wash -> camera re-life -> source-aware gate).
  const [dsV7EngineMode, setDsV7EngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [dsV7IphoneExif, setDsV7IphoneExif] = useState(true);
  // DS ReMint V8 controls (quality floor + ghost ladder + device/naming expert set).
  const [dsV8EngineMode, setDsV8EngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [dsV8QualityFloor, setDsV8QualityFloor] =
    useState<"studio" | "high" | "balanced" | "strong">("balanced");
  const [dsV8IphoneExif, setDsV8IphoneExif] = useState(true);
  const [dsV8Device, setDsV8Device] = useState<CxRemintDevice>("auto");
  const [dsV8ResolutionMode, setDsV8ResolutionMode] =
    useState<CxRemintResolutionMode>("off");
  const [dsV8ResolutionX, setDsV8ResolutionX] = useState(72);
  const [dsV8ResolutionY, setDsV8ResolutionY] = useState(72);
  const [dsV8OutputNameStyle, setDsV8OutputNameStyle] =
    useState<"photo-style" | "original" | "custom">("photo-style");
  const [dsV8OutputNameCustom, setDsV8OutputNameCustom] = useState("");
  const [dsV8MetadataMode, setDsV8MetadataMode] =
    useState<"device" | "minimal">("device");
  // DS ReMint V8.2 Max controls (degrade -> low-res launder -> neural restore -> re-life).
  const [dsV82EngineMode, setDsV82EngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [dsV82QualityFloor, setDsV82QualityFloor] =
    useState<"studio" | "balanced" | "strong">("balanced");
  const [dsV82IphoneExif, setDsV82IphoneExif] = useState(true);
  const [dsV82MetadataMode, setDsV82MetadataMode] =
    useState<"device" | "minimal">("device");
  const [dsV82RestoreEngine, setDsV82RestoreEngine] =
    useState<"neural" | "classical">("neural");
  // DS ReMint V8.3 controls (wash-family lab + restore engine).
  const [dsV83EngineMode, setDsV83EngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [dsV83QualityFloor, setDsV83QualityFloor] =
    useState<"studio" | "balanced" | "strong">("balanced");
  const [dsV83WashModel, setDsV83WashModel] =
    useState<"qwen" | "zimage" | "qwen+zimage">("qwen+zimage");
  const [dsV83RestoreEngine, setDsV83RestoreEngine] =
    useState<"neural" | "classical">("neural");
  const [dsV83IphoneExif, setDsV83IphoneExif] = useState(true);
  const [dsV83MetadataMode, setDsV83MetadataMode] =
    useState<"device" | "minimal">("device");
  // DS ReMint V8.8 controls (coherent camera model).
  const [dsV88EngineMode, setDsV88EngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [dsV88WashModel, setDsV88WashModel] =
    useState<"qwen" | "zimage" | "qwen+zimage">("qwen");
  const [dsV88Strength, setDsV88Strength] =
    useState<"light" | "balanced" | "deep">("balanced");
  const [dsV88IphoneExif, setDsV88IphoneExif] = useState(true);
  const [dsV88MetadataMode, setDsV88MetadataMode] =
    useState<"device" | "minimal">("device");
  // Browser-side reframe (zoom + tilt + shear) applied before upload. No GPU.
  const [cxReframe, setCxReframe] = useState(true);
  const [cxReframePreset, setCxReframePreset] = useState<ReframePreset>("balanced");
  const [cxReframeZoom, setCxReframeZoom] = useState(REFRAME_PRESETS.balanced.zoom);
  const [cxReframeTilt, setCxReframeTilt] = useState(REFRAME_PRESETS.balanced.rotationDeg);
  const [deepCleanStatus, setDeepCleanStatus] = useState("");
  const [deepCleanJob, setDeepCleanJob] = useState<DeepCleanJob | null>(null);
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
      "max-cx-remint-v5": 13,
      // DS ReMint V6: regen + laundering + classical reconstruction + QC.
      "ds-remint-v6": 13,
      // DS ReMint V7: wash + camera re-life + source-aware gate + single encode.
      "ds-remint-v7": 13,
      // DS ReMint V8: V7 + quality floor + ghost ladder + device/naming options.
      "ds-remint-v8": 13,
      // DS ReMint V8.1: quality-first floors through ghost_lite + metadata mode.
      "ds-remint-v8.1": 13,
      // DS ReMint V8.2 Max: degrade + neural restore costs an extra GPU pass.
      "ds-remint-v8.2": 14,
      // DS ReMint V8.3: wash-family lab (mix = two GPU wash passes).
      "ds-remint-v8.3": 15,
      // DS ReMint V8.8 Coherent: wash + coherent camera model, single resample.
      "ds-remint-v8.8": 15,
      // DS ReMint V8.9: data-tuned coherent defaults + baseline routing.
      "ds-remint-v8.9": 15
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
    // Adaptive DS ReMint V6 does the same detector-gated escalation.
    if (deepCleanProfile === "ds-remint-v6" && dsV6EngineMode === "adaptive") cost += 2;
    // Adaptive DS ReMint V7 runs repeated real-detector probes per re-life rung.
    if (deepCleanProfile === "ds-remint-v7" && dsV7EngineMode === "adaptive") cost += 2;
    // Adaptive DS ReMint V8 does the same detector-gated escalation.
    if (deepCleanProfile === "ds-remint-v8.1" && dsV8EngineMode === "adaptive") cost += 2;
    // Adaptive DS ReMint V8.2 probes each degrade floor against the live detector.
    if (deepCleanProfile === "ds-remint-v8.2" && dsV82EngineMode === "adaptive") cost += 2;
    // Adaptive DS ReMint V8.3 probes each floor against the live detector.
    if (deepCleanProfile === "ds-remint-v8.3" && dsV83EngineMode === "adaptive") cost += 2;
    // Adaptive DS ReMint V8.8 escalates the strength ladder against the detector.
    if (deepCleanProfile === "ds-remint-v8.9" && dsV88EngineMode === "adaptive") cost += 2;
    if (deepCleanOutputMode === "sealed-stamped") cost += 1;
    return cost;
  }, [
    deepCleanProfile,
    expertRefinementMode,
    deepCleanMicroTextureJitter,
    deepCleanOutputMode,
    cxEngineMode,
    dsV6EngineMode,
    dsV7EngineMode,
    dsV8EngineMode,
    dsV82EngineMode,
    dsV83EngineMode,
    dsV88EngineMode
  ]);

  // CX Remint quality-floor slider: map the selected preset to its slider index
  // and metadata for the control's labels.
  const cxQualityFloorIndex = Math.max(
    0,
    CX_QUALITY_FLOOR_STOPS.findIndex((stop) => stop.value === cxQualityFloor)
  );
  const cxQualityFloorStop = CX_QUALITY_FLOOR_STOPS[cxQualityFloorIndex];

  // DS ReMint V6 derived state: active toggle + quality-floor slider mapping.
  const dsV6Active = deepCleanProfile === "ds-remint-v6";
  // DS ReMint V7 derived state: active toggle.
  const dsV7Active = deepCleanProfile === "ds-remint-v7";
  // DS ReMint V8.1 derived state: active toggle.
  const dsV8Active = deepCleanProfile === "ds-remint-v8.1";
  // DS ReMint V8.2 derived state: active toggle.
  const dsV82Active = deepCleanProfile === "ds-remint-v8.2";
  // DS ReMint V8.3 derived state: active toggle.
  const dsV83Active = deepCleanProfile === "ds-remint-v8.3";
  // DS ReMint V8.8/V8.9 derived state: active toggle.
  const dsV88Active = deepCleanProfile === "ds-remint-v8.9";
  const dsV6QualityFloorIndex = Math.max(
    0,
    CX_QUALITY_FLOOR_STOPS.findIndex((stop) => stop.value === dsV6QualityFloor)
  );
  const dsV6QualityFloorStop = CX_QUALITY_FLOOR_STOPS[dsV6QualityFloorIndex];

  // Live pipeline indicators for the V6 panel: what the worker will actually
  // do for the first queued image (approximation; the worker clamps exactly).
  const dsV6InputLong =
    imageQueue.length > 0
      ? Math.max(imageQueue[0].width ?? 0, imageQueue[0].height ?? 0)
      : 0;
  const dsV6DeliveryTargetNum = dsV6OutputTarget === "" ? 1440 : Number(dsV6OutputTarget);
  const dsV6ProcessPx =
    dsV6InputLong > 0
      ? Math.min(dsV6InputLong, dsV6QualityFloorStop.longEdge)
      : dsV6QualityFloorStop.longEdge;
  const dsV6DeliveryPx =
    dsV6InputLong > 0
      ? Math.min(dsV6InputLong, dsV6DeliveryTargetNum)
      : dsV6DeliveryTargetNum;

  // Re-Mint can run locally in demo mode. Sign-in upgrades to Supabase credits.
  const pendingBatchItems = imageQueue.filter((item) => item.status !== "completed");
  const completedBatchItems = imageQueue.filter(
    (item) => item.status === "completed" && item.job?.outputUrl
  );
  const batchRequiredCost = pendingBatchItems.length * maxCost;
  const canProcess =
    !!file &&
    state !== "processing" &&
    !batchRunning &&
    !zipBusy &&
    credits.privacyCredits >= instantCost;
  const canQueueMax =
    pendingBatchItems.length > 0 &&
    !batchRunning &&
    !zipBusy &&
    credits.privacyCredits >= batchRequiredCost;
  const activeQueueItem =
    imageQueue.find((item) => item.id === activeQueueId) ?? imageQueue[0] ?? null;
  const activeBatchBusy = Boolean(
    activeQueueItem &&
      ["preparing", "uploading", "queued", "processing"].includes(activeQueueItem.status)
  );
  const stageResultUrl =
    resultUrl ||
    (activeQueueItem?.job?.status === "completed" ? activeQueueItem.job.outputUrl ?? "" : "");
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
    imageQueueRef.current = imageQueue;
  }, [imageQueue]);

  useEffect(() => {
    return () => imageQueueRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
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

  function clearActiveResult() {
    setError("");
    setState("idle");
    setReport(null);
    setResultHash("");
    setResultBlob(null);
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    setResultUrl("");
    setStageView("clean");
  }

  function selectQueueItem(item: ImageQueueItem) {
    clearActiveResult();
    setActiveQueueId(item.id);
    setFile(item.file);
    setPreviewUrl(item.previewUrl);
    setDeepCleanJob(item.job ?? null);
    setDeepCleanStatus(
      item.status === "failed"
        ? item.error || "This image could not be processed."
        : item.status === "completed"
          ? "Completed and ready to download."
          : ""
    );

    const nextFormat: OutputFormat = item.file.type.includes("png")
      ? "png"
      : item.file.type.includes("webp")
        ? "webp"
        : "jpeg";
    setOutputFormat(nextFormat);
    setSizeMode("original");
    setInputDims(item.width && item.height ? { w: item.width, h: item.height } : null);
    if (item.width && item.height) {
      setCustomWidth(item.width);
      setCustomHeight(item.height);
    }
  }

  function updateQueueItem(id: string, patch: Partial<ImageQueueItem>) {
    setImageQueue((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item))
    );
    if (activeQueueId === id && patch.job !== undefined) setDeepCleanJob(patch.job);
  }

  function addFiles(files: File[]) {
    if (!files.length || batchRunning) return;
    setBatchNotice("");

    const supported = files.filter(
      (candidate) =>
        ["image/jpeg", "image/png", "image/webp"].includes(candidate.type) &&
        candidate.size <= MAX_IMAGE_BYTES
    );
    const rejected = files.length - supported.length;
    const availableSlots = Math.max(0, MAX_QUEUE_IMAGES - imageQueue.length);
    const accepted = supported.slice(0, availableSlots);
    const overLimit = supported.length - accepted.length;

    if (!accepted.length) {
      setBatchNotice(
        availableSlots === 0
          ? `The queue is full. Remove an image before adding another (maximum ${MAX_QUEUE_IMAGES}).`
          : "No supported images were added. Use JPEG, PNG, or WebP files up to 25 MB each."
      );
      return;
    }

    const added: ImageQueueItem[] = accepted.map((nextFile) => ({
      id: `image-${Date.now()}-${queueSequenceRef.current++}`,
      file: nextFile,
      previewUrl: URL.createObjectURL(nextFile),
      status: "ready"
    }));

    setImageQueue((current) => [...current, ...added]);
    if (!file) selectQueueItem(added[0]);

    added.forEach((item) => {
      createImageBitmap(item.file)
        .then((bitmap) => {
          const dimensions = { width: bitmap.width, height: bitmap.height };
          bitmap.close();
          updateQueueItem(item.id, dimensions);
          if (item.id === activeQueueId || (!activeQueueId && item.id === added[0].id)) {
            setInputDims({ w: dimensions.width, h: dimensions.height });
            setCustomWidth(dimensions.width);
            setCustomHeight(dimensions.height);
          }
        })
        .catch(() => undefined);
    });

    const notices = [
      rejected ? `${rejected} unsupported or oversized ${rejected === 1 ? "file was" : "files were"} skipped.` : "",
      overLimit
        ? `${overLimit} ${overLimit === 1 ? "image was" : "images were"} left out to keep the ${MAX_QUEUE_IMAGES}-image limit.`
        : ""
    ].filter(Boolean);
    setBatchNotice(notices.join(" "));
  }

  function removeQueueItem(id: string) {
    if (batchRunning) return;
    const removed = imageQueue.find((item) => item.id === id);
    if (!removed) return;
    URL.revokeObjectURL(removed.previewUrl);
    const nextQueue = imageQueue.filter((item) => item.id !== id);
    setImageQueue(nextQueue);

    if (activeQueueId === id) {
      const nextActive = nextQueue[0];
      if (nextActive) {
        selectQueueItem(nextActive);
      } else {
        clearActiveResult();
        setActiveQueueId("");
        setFile(null);
        setPreviewUrl("");
        setInputDims(null);
        setDeepCleanJob(null);
        setDeepCleanStatus("");
      }
    }
  }

  function moveQueueItem(sourceId: string, targetId: string) {
    if (!sourceId || sourceId === targetId || batchRunning) return;
    setImageQueue((current) => {
      const sourceIndex = current.findIndex((item) => item.id === sourceId);
      const targetIndex = current.findIndex((item) => item.id === targetId);
      if (sourceIndex < 0 || targetIndex < 0) return current;
      const next = [...current];
      const [moved] = next.splice(sourceIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
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
    const itemsToProcess = imageQueue.filter((item) => item.status !== "completed");
    if (!itemsToProcess.length) {
      setDeepCleanStatus("Add an image to the queue first.");
      return;
    }
    if (hasSupabaseConfig && !userId) {
      setDeepCleanStatus("Sign in before starting the Re-Mint Max queue.");
      return;
    }
    const requiredCredits = itemsToProcess.length * maxCost;
    if (credits.privacyCredits < requiredCredits) {
      setDeepCleanStatus(
        `Not enough credits — this ${itemsToProcess.length}-image queue needs ${requiredCredits}.`
      );
      return;
    }

    setBatchRunning(true);
    setBatchNotice("");
    let completedThisRun = 0;
    let failedThisRun = 0;

    for (const [index, item] of itemsToProcess.entries()) {
      let createdJob: DeepCleanJob | null = null;
      selectQueueItem(item);
      updateQueueItem(item.id, { status: "preparing", error: undefined, job: undefined });
      setDeepCleanJob(null);
      setDeepCleanStatus(
        `Preparing ${index + 1} of ${itemsToProcess.length} · ${item.file.name}`
      );

      try {
        const job = await createDeepCleanJob({
          file: item.file,
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
                device: cxDevice,
                resolutionMode: cxResolutionMode,
                resolutionX: cxResolutionX,
                resolutionY: cxResolutionY
              }
            : undefined,
          dsRemintV6:
            deepCleanProfile === "ds-remint-v6"
              ? {
                  engineMode: dsV6EngineMode,
                  qualityFloor: dsV6QualityFloor,
                  acquisition: dsV6Acquisition,
                  iphoneExif: dsV6IphoneExif,
                  device: "auto",
                  outputTarget:
                    dsV6OutputTarget === "" ? null : Number(dsV6OutputTarget),
                  sharpenPercent: dsV6Sharpen,
                  textureAmount: dsV6Texture / 100,
                  spectralStrength: dsV6Spectral / 100
                }
              : undefined,
          dsRemintV7:
            deepCleanProfile === "ds-remint-v7"
              ? {
                  engineMode: dsV7EngineMode,
                  iphoneExif: dsV7IphoneExif
                }
              : undefined,
          dsRemintV8:
            deepCleanProfile === "ds-remint-v8.1"
              ? {
                  engineMode: dsV8EngineMode,
                  qualityFloor: dsV8QualityFloor,
                  iphoneExif: dsV8IphoneExif,
                  metadataMode: dsV8MetadataMode,
                  device: dsV8Device,
                  resolutionMode: dsV8ResolutionMode,
                  resolutionX: dsV8ResolutionX,
                  resolutionY: dsV8ResolutionY
                }
              : undefined,
          outputNameStyle:
            deepCleanProfile === "ds-remint-v8.1" ||
            deepCleanProfile === "ds-remint-v8.2" ||
            deepCleanProfile === "ds-remint-v8.3" ||
            deepCleanProfile === "ds-remint-v8.8" ||
            deepCleanProfile === "ds-remint-v8.9"
              ? dsV8OutputNameStyle
              : undefined,
          outputNameCustom:
            deepCleanProfile === "ds-remint-v8.1" ||
            deepCleanProfile === "ds-remint-v8.2" ||
            deepCleanProfile === "ds-remint-v8.3" ||
            deepCleanProfile === "ds-remint-v8.8" ||
            deepCleanProfile === "ds-remint-v8.9"
              ? dsV8OutputNameCustom
              : undefined,
          dsRemintV82:
            deepCleanProfile === "ds-remint-v8.2"
              ? {
                  engineMode: dsV82EngineMode,
                  qualityFloor: dsV82QualityFloor,
                  iphoneExif: dsV82IphoneExif,
                  metadataMode: dsV82MetadataMode,
                  restoreEngine: dsV82RestoreEngine
                }
              : undefined,
          dsRemintV83:
            deepCleanProfile === "ds-remint-v8.3"
              ? {
                  engineMode: dsV83EngineMode,
                  qualityFloor: dsV83QualityFloor,
                  washModel: dsV83WashModel,
                  restoreEngine: dsV83RestoreEngine,
                  iphoneExif: dsV83IphoneExif,
                  metadataMode: dsV83MetadataMode
                }
              : undefined,
          dsRemintV88:
            deepCleanProfile === "ds-remint-v8.8"
              ? {
                  engineMode: dsV88EngineMode,
                  washModel: dsV88WashModel,
                  strength: dsV88Strength,
                  iphoneExif: dsV88IphoneExif,
                  metadataMode: dsV88MetadataMode
                }
              : undefined,
          dsRemintV89:
            deepCleanProfile === "ds-remint-v8.9"
              ? {
                  engineMode: dsV88EngineMode,
                  washModel: dsV88WashModel,
                  strength: dsV88Strength,
                  iphoneExif: dsV88IphoneExif,
                  metadataMode: dsV88MetadataMode
                }
              : undefined
        });
        createdJob = job;
        updateQueueItem(item.id, { status: "preparing", job });
        setDeepCleanJob(job);

        let uploadFile = item.file;
        if (isCxProfile(deepCleanProfile) && cxReframe) {
          setDeepCleanStatus(
            `Reframing ${index + 1} of ${itemsToProcess.length} in your browser…`
          );
          try {
            uploadFile = await reframeImageFile(
              item.file,
              reframeOptionsFor(cxReframePreset, {
                zoom: cxReframeZoom,
                rotationDeg: cxReframeTilt
              })
            );
          } catch {
            uploadFile = item.file;
          }
        }

        updateQueueItem(item.id, { status: "uploading", job });
        setDeepCleanStatus(`Uploading ${index + 1} of ${itemsToProcess.length} privately…`);
        await uploadDeepCleanInput(job, uploadFile);

        updateQueueItem(item.id, { status: "queued", job });
        setDeepCleanStatus(`Sending ${index + 1} of ${itemsToProcess.length} to the GPU…`);
        await dispatchDeepCleanJob(job.id);
        await spendCredits(maxCost);

        updateQueueItem(item.id, { status: "processing", job });
        const completedJob = await waitForDeepCleanJob(
          job.id,
          item.id,
          index + 1,
          itemsToProcess.length
        );
        updateQueueItem(item.id, {
          status: "completed",
          job: completedJob,
          error: undefined
        });
        setDeepCleanJob(completedJob);
        completedThisRun += 1;
      } catch (nextError) {
        const message =
          nextError instanceof Error ? nextError.message : "Re-Mint Max could not process this image.";
        if (createdJob) {
          await cancelDeepCleanJob(createdJob.id).catch(() => undefined);
        }
        updateQueueItem(item.id, {
          status: "failed",
          job: createdJob ?? undefined,
          error: message
        });
        setDeepCleanStatus(`${item.file.name}: ${message}`);
        failedThisRun += 1;
      }
    }

    setBatchRunning(false);
    if (userId) await refreshSupabaseCredits(userId);
    setDeepCleanStatus(
      failedThisRun
        ? `Queue finished · ${completedThisRun} completed · ${failedThisRun} failed. Failed images can be retried.`
        : `Queue complete · all ${completedThisRun} ${completedThisRun === 1 ? "image is" : "images are"} ready.`
    );
  }

  async function waitForDeepCleanJob(
    jobId: string,
    itemId: string,
    position: number,
    total: number
  ): Promise<DeepCleanJob> {
    for (;;) {
      const job = await getDeepCleanJob(jobId);
      setDeepCleanJob(job);
      if (job.status === "completed") return job;
      if (job.status === "failed") {
        throw new Error(job.failureReason || "The GPU worker could not process this image.");
      }

      updateQueueItem(itemId, {
        status: job.status === "queued" ? "queued" : "processing",
        job
      });
      setDeepCleanStatus(
        `Processing ${position} of ${total} · ${job.status === "queued" ? "waiting for GPU" : "GPU pass in progress"}…`
      );
      await new Promise<void>((resolve) => window.setTimeout(resolve, 3500));
    }
  }

  function outputNameFor(item: ImageQueueItem, position?: number) {
    const rawBase = item.file.name.replace(/\.[^.]+$/, "");
    const base = rawBase.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-").slice(0, 90) || "image";
    const prefix = position === undefined ? "" : `${String(position + 1).padStart(2, "0")}-`;
    return `${prefix}${base}-remint.jpg`;
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

  async function freshCompletedJob(item: ImageQueueItem) {
    if (!item.job?.id) throw new Error("This image does not have a completed job.");
    const job = await getDeepCleanJob(item.job.id);
    if (job.status !== "completed" || !job.outputUrl) {
      throw new Error("This output is not available yet.");
    }
    updateQueueItem(item.id, { job, status: "completed" });
    return job;
  }

  async function downloadQueueItem(item: ImageQueueItem) {
    if (downloadingItemId || zipBusy) return;
    setDownloadingItemId(item.id);
    setBatchNotice("");
    try {
      const job = await freshCompletedJob(item);
      const response = await fetch(job.outputUrl as string);
      if (!response.ok) throw new Error("The secure download link could not be opened.");
      saveBlob(await response.blob(), outputNameFor(item));
    } catch (nextError) {
      setBatchNotice(
        nextError instanceof Error ? nextError.message : "The image could not be downloaded."
      );
    } finally {
      setDownloadingItemId("");
    }
  }

  async function downloadAllCompleted() {
    const completed = imageQueue.filter((item) => item.status === "completed" && item.job?.id);
    if (!completed.length || zipBusy) return;
    setZipBusy(true);
    setBatchNotice(`Preparing ${completed.length} images for download…`);
    try {
      const files: Record<string, Uint8Array> = {};
      for (const [index, item] of completed.entries()) {
        const job = await freshCompletedJob(item);
        const response = await fetch(job.outputUrl as string);
        if (!response.ok) throw new Error(`Could not download ${item.file.name}.`);
        files[outputNameFor(item, index)] = new Uint8Array(await response.arrayBuffer());
        setBatchNotice(`Packaging ${index + 1} of ${completed.length}…`);
      }
      const { zip } = await import("fflate");
      const zipped = await new Promise<Uint8Array>((resolve, reject) => {
        zip(files, { level: 0 }, (zipError, data) => {
          if (zipError) reject(zipError);
          else resolve(data);
        });
      });
      const zipBuffer = zipped.buffer.slice(
        zipped.byteOffset,
        zipped.byteOffset + zipped.byteLength
      ) as ArrayBuffer;
      saveBlob(new Blob([zipBuffer], { type: "application/zip" }), "remint-images.zip");
      setBatchNotice(`${completed.length} processed images downloaded as a ZIP.`);
    } catch (nextError) {
      setBatchNotice(
        nextError instanceof Error ? nextError.message : "The ZIP could not be created."
      );
    } finally {
      setZipBusy(false);
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
      // Deep (v2/v3/v4/v5) profiles default to the Strong 960px processing
      // floor. v5 upscales the delivered result back above 1080px.
      //
      // The flux fingerprint only dies at the
      // lower resolutions (live tests: clean at ~960px, still flagged at
      // 1280px). Snap the quality-floor slider to the Strong (960px) sweet spot.
      if (isCxDeepProfile(profile)) setCxQualityFloor("strong");
      return;
    }
    if (profile === "ds-remint-v6") {
      // DS ReMint V6 is terminal: stripped output, camera-grade texture and a
      // coherent iPhone EXIF come from the pipeline itself.
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
      return;
    }
    if (profile === "ds-remint-v7") {
      // DS ReMint V7 is terminal: the wash breaks SynthID, the non-generative
      // camera re-life stack replaces the generative fingerprint, the
      // source-aware gate picks the candidate on the delivered bytes. One
      // JPEG encode with coherent EXIF from the pipeline itself.
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
      return;
    }
    if (profile === "ds-remint-v8.1") {
      // DS ReMint V8.1 is terminal like V8 with quality-first floors routed
      // through ghost_lite and metadata mode control. Stripped output;
      // pipeline handles its own EXIF.
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
      return;
    }
    if (profile === "ds-remint-v8.2") {
      // DS ReMint V8.2 Max is terminal: degrade -> low-res ghost launder ->
      // neural restore -> ghost_lite re-life -> single encode.
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
      return;
    }
    if (profile === "ds-remint-v8.3") {
      // DS ReMint V8.3 is terminal like V8.2 with the wash-family lab
      // (qwen | zimage | qwen+zimage) and both restore engines.
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
      return;
    }
    if (profile === "ds-remint-v8.8" || profile === "ds-remint-v8.9") {
      // DS ReMint V8.8/V8.9 Coherent are terminal: wash -> single resample ->
      // coherent camera model (inverse ISP -> optics -> CFA -> MHC ->
      // weak ISP denoise -> forward ISP) -> one encode.
      setDeepCleanOutputMode("stripped");
      setExpertRefinementMode("off");
      setExpertRefinementIntensity(100);
      setExpertRefinementPreserveLines(true);
      setExpertRefinementTechniques(cloneExpertPreset("off"));
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
    if (batchRunning || zipBusy) return;
    imageQueue.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    clearActiveResult();
    setImageQueue([]);
    setActiveQueueId("");
    setFile(null);
    setPreviewUrl("");
    setInputDims(null);
    setBatchNotice("");
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
                Drop up to 20 images, arrange the exact processing order, and run a professional
                Re-Mint Max batch with individual or one-click ZIP downloads.
              </p>

              <Dropzone
                large
                previewUrl=""
                dragging={dragging}
                setDragging={setDragging}
                onPick={openPicker}
                onDropFiles={addFiles}
              />
              {batchNotice ? (
                <p className="rm-hero-upload-notice" role="alert">
                  {batchNotice}
                </p>
              ) : null}

              <div className="rm-trust">
                <span>
                  <Images size={14} aria-hidden="true" /> Up to 20 images
                </span>
                <span>
                  <GripVertical size={14} aria-hidden="true" /> Drag to set the order
                </span>
                <span>
                  <Archive size={14} aria-hidden="true" /> Download all as ZIP
                </span>
              </div>
            </section>

            <section className="rm-section" id="how">
              <SectionHead eyebrow="How it works" title="Three steps to a fresh mint" />
              <div className="rm-steps">
                <Step
                  n={1}
                  icon={<Upload size={18} aria-hidden="true" />}
                  title="Build your queue"
                  body="Add up to 20 JPG, PNG, or WebP images, then drag the previews into order."
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
                  body="Download any result individually, or collect every completed image in one ZIP."
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
                    <Upload size={18} aria-hidden="true" /> Build a queue
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
                <h2>Re-mint one image — or twenty</h2>
                <p>Build the queue now, then choose local or Re-Mint Max processing.</p>
                <button className="rm-btn rm-btn-primary rm-btn-lg" type="button" onClick={openPicker}>
                  <Upload size={18} aria-hidden="true" /> Add images
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
                  {` · ${imageQueue.length} ${imageQueue.length === 1 ? "image" : "images"} in queue`}
                </span>
              </div>
              <div className="rm-studio-top-actions">
                <button
                  className="rm-btn rm-btn-soft rm-btn-sm"
                  type="button"
                  onClick={openPicker}
                  disabled={batchRunning || zipBusy || imageQueue.length >= MAX_QUEUE_IMAGES}
                >
                  <Upload size={15} aria-hidden="true" /> Add images
                </button>
                <button
                  className="rm-btn rm-btn-soft rm-btn-sm"
                  type="button"
                  onClick={resetAll}
                  disabled={batchRunning || zipBusy}
                >
                  <RotateCcw size={15} aria-hidden="true" /> Start over
                </button>
              </div>
            </div>

            <BatchQueue
              items={imageQueue}
              activeId={activeQueueId}
              draggedId={draggedQueueId}
              running={batchRunning || zipBusy}
              notice={batchNotice}
              completedCount={completedBatchItems.length}
              zipBusy={zipBusy}
              downloadingItemId={downloadingItemId}
              onAdd={openPicker}
              onSelect={selectQueueItem}
              onRemove={removeQueueItem}
              onDragStart={setDraggedQueueId}
              onDragEnd={() => setDraggedQueueId("")}
              onMove={moveQueueItem}
              onDownload={downloadQueueItem}
              onDownloadAll={downloadAllCompleted}
            />

            <div className="rm-studio-grid">
              <div className="rm-stage">
                <div
                  className={`rm-stage-frame${
                    state === "processing" || activeBatchBusy ? " is-busy" : ""
                  }`}
                >
                  <img
                    src={stageResultUrl && stageView === "clean" ? stageResultUrl : previewUrl}
                    alt={stageResultUrl && stageView === "clean" ? "Re-Minted result" : "Original image"}
                  />
                  {state === "processing" || activeBatchBusy ? (
                    <div className="rm-stage-veil">
                      <Loader2 className="rm-spin" size={28} aria-hidden="true" />
                      <span>{activeBatchBusy ? "Processing on the GPU…" : "Re-minting…"}</span>
                    </div>
                  ) : null}
                  {stageResultUrl ? (
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

                {!stageResultUrl && state !== "processing" && !activeBatchBusy ? (
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
                      {maxCost} credits / image
                    </span>
                  </div>
                  <p className="rm-card-desc">
                    One setup applies to the full queue. Images run in the order shown, one at a time,
                    with clear progress and isolated failures.
                  </p>

                  <label className={`rm-v6-toggle${dsV6Active ? " is-active" : ""}`}>
                    <input
                      type="checkbox"
                      checked={dsV6Active}
                      disabled={batchRunning}
                      onChange={(event) =>
                        chooseDeepCleanProfile(
                          event.target.checked ? "ds-remint-v6" : "max-cx-remint-v5"
                        )
                      }
                    />
                    <span className="rm-switch-track" aria-hidden="true">
                      <span className="rm-switch-thumb" />
                    </span>
                    <span className="rm-v6-toggle-text">
                      <strong>DS ReMint V6</strong>
                      <small>Flux-fingerprint removal + quality reconstruction</small>
                    </span>
                    <span className="rm-badge">{dsV6Active ? "Enabled" : "Off"}</span>
                  </label>

                  {dsV6Active ? (
                    <div className="rm-v6-panel">
                      <div className="rm-v6-banner">
                        <Sparkles size={15} aria-hidden="true" />
                        <span>
                          Regeneration breaks SynthID, a consolidated resample strips the Flux
                          fingerprint, then classical reconstruction (dehalo · luma sharpen ·
                          masked texture) rebuilds quality. One JPEG encode, final-byte QC.
                        </span>
                      </div>

                      <div className="rm-v6-stats" aria-label="Pipeline indicators">
                        <span className="rm-stat">
                          <em>Process</em>
                          <b>~{dsV6ProcessPx}px</b>
                        </span>
                        <span className="rm-stat">
                          <em>Deliver</em>
                          <b>~{dsV6DeliveryPx}px</b>
                        </span>
                        <span className="rm-stat">
                          <em>Encode</em>
                          <b>JPEG · q94</b>
                        </span>
                        <span className="rm-stat">
                          <em>Engine</em>
                          <b>{dsV6EngineMode === "adaptive" ? "≤5 gated passes" : "1 pass"}</b>
                        </span>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V6 engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV6EngineMode === "adaptive"}
                            className={dsV6EngineMode === "adaptive" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV6EngineMode("adaptive")}
                          >
                            Adaptive (detector-gated)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV6EngineMode === "template"}
                            className={dsV6EngineMode === "template" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV6EngineMode("template")}
                          >
                            Optimised template
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV6EngineMode === "adaptive"
                            ? "Detector-gated escalation: every rung is probed against a live AI detector and the first pass that clears ships — the minimum destruction that passes for THIS image. Up to 5 rungs. +2 credits."
                            : "One deterministic pass at the quality floor below. Fast and predictable, no detector calls."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">
                          Quality floor · {dsV6QualityFloorStop.label} (~{dsV6QualityFloorStop.longEdge}px)
                        </span>
                        <input
                          className="rm-cx-slider"
                          type="range"
                          min={0}
                          max={CX_QUALITY_FLOOR_STOPS.length - 1}
                          step={1}
                          value={dsV6QualityFloorIndex}
                          disabled={batchRunning}
                          onChange={(event) =>
                            setDsV6QualityFloor(
                              CX_QUALITY_FLOOR_STOPS[Number(event.target.value)].value
                            )
                          }
                        />
                        <div className="rm-range-ends">
                          <span>Strongest removal</span>
                          <span>Max quality</span>
                        </div>
                        <p className="rm-hint">
                          {dsV6QualityFloorStop.hint} Laundering runs at this size; V6 then
                          reconstructs to the delivery resolution above — so a lower floor costs
                          detail, never size.
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Camera texture</span>
                        <div className="rm-seg rm-seg-sm" role="radiogroup" aria-label="Camera texture">
                          {(["conservative", "balanced", "aggressive"] as CxRemintAcquisition[]).map(
                            (level) => (
                              <button
                                key={level}
                                type="button"
                                role="radio"
                                aria-checked={dsV6Acquisition === level}
                                className={dsV6Acquisition === level ? "is-active" : ""}
                                disabled={batchRunning}
                                onClick={() => setDsV6Acquisition(level)}
                              >
                                {level === "conservative"
                                  ? "Conservative"
                                  : level === "balanced"
                                  ? "Balanced"
                                  : "Aggressive"}
                              </button>
                            )
                          )}
                        </div>
                        <p className="rm-hint">
                          Masked sensor grain at final resolution: flat areas (skies, gradients)
                          stay clean, textured areas inherit a real-camera high-frequency
                          signature. Aggressive helps stubbornly AI-flagged images.
                        </p>
                      </div>

                      <div className="rm-field-grid">
                        <label className="rm-field">
                          <span className="rm-field-label">Delivery long edge</span>
                          <input
                            className="rm-input"
                            type="number"
                            min={256}
                            max={8192}
                            placeholder="Auto · min(source, 1440)"
                            value={dsV6OutputTarget}
                            disabled={batchRunning}
                            onChange={(event) => setDsV6OutputTarget(event.target.value)}
                          />
                          <p className="rm-hint">
                            {dsV6InputLong > 0
                              ? `Your first image is ${dsV6InputLong}px — delivery will be ~${dsV6DeliveryPx}px.`
                              : "Auto never enlarges past the source image."}
                          </p>
                        </label>
                        <label className="rm-switch">
                          <input
                            type="checkbox"
                            checked={dsV6IphoneExif}
                            disabled={batchRunning}
                            onChange={(event) => setDsV6IphoneExif(event.target.checked)}
                          />
                          <span className="rm-switch-track" aria-hidden="true">
                            <span className="rm-switch-thumb" />
                          </span>
                          <span>iPhone EXIF</span>
                        </label>
                      </div>

                      <details className="rm-disc">
                        <summary>
                          <Gauge size={15} aria-hidden="true" /> Expert tuning — sharpening ·
                          texture · fingerprint scrub
                          <ChevronDown className="rm-chev" size={16} aria-hidden="true" />
                        </summary>
                        <div className="rm-disc-body">
                          <label className="rm-range">
                            <span className="rm-field-label">
                              Sharpening <em>{dsV6Sharpen}%</em>
                            </span>
                            <input
                              type="range"
                              min={0}
                              max={60}
                              step={2}
                              value={dsV6Sharpen}
                              disabled={batchRunning}
                              onChange={(event) => setDsV6Sharpen(Number(event.target.value))}
                            />
                            <span className="rm-range-ends">
                              <span>Softer</span>
                              <span>Crisper</span>
                            </span>
                            <p className="rm-hint">
                              Luma-only unsharp applied after dehalo. Too high re-adds edge halos
                              that detectors read as GAN ringing. 24% is the A/B-tuned sweet spot.
                            </p>
                          </label>
                          <label className="rm-range">
                            <span className="rm-field-label">
                              Texture strength <em>{dsV6Texture}%</em>
                            </span>
                            <input
                              type="range"
                              min={0}
                              max={150}
                              step={5}
                              value={dsV6Texture}
                              disabled={batchRunning}
                              onChange={(event) => setDsV6Texture(Number(event.target.value))}
                            />
                            <span className="rm-range-ends">
                              <span>Clean</span>
                              <span>Grainy</span>
                            </span>
                            <p className="rm-hint">
                              Multiplies the masked sensor grain at final resolution. 90% is the
                              tuned default; push higher only for images that still read as
                              AI-generated.
                            </p>
                          </label>
                          <label className="rm-range">
                            <span className="rm-field-label">
                              Fingerprint scrub <em>{dsV6Spectral}%</em>
                            </span>
                            <input
                              type="range"
                              min={0}
                              max={60}
                              step={5}
                              value={dsV6Spectral}
                              disabled={batchRunning}
                              onChange={(event) => setDsV6Spectral(Number(event.target.value))}
                            />
                            <span className="rm-range-ends">
                              <span>Subtle</span>
                              <span>Deep</span>
                            </span>
                            <p className="rm-hint">
                              Spectral amplitude reshape toward a real-camera 1/f curve at final
                              resolution — the Flux-fingerprint killer. 30% is the A/B-tuned
                              default; too deep flattens fine texture.
                            </p>
                          </label>
                        </div>
                      </details>
                    </div>
                  ) : null}

                  <label className={`rm-v6-toggle${dsV7Active ? " is-active" : ""}`}>
                    <input
                      type="checkbox"
                      checked={dsV7Active}
                      disabled={batchRunning}
                      onChange={(event) =>
                        chooseDeepCleanProfile(
                          event.target.checked ? "ds-remint-v7" : "max-cx-remint-v5"
                        )
                      }
                    />
                    <span className="rm-switch-track" aria-hidden="true">
                      <span className="rm-switch-thumb" />
                    </span>
                    <span className="rm-v6-toggle-text">
                      <strong>DS ReMint V7</strong>
                      <small>Wash once · camera re-life · source-aware gate</small>
                    </span>
                    <span className="rm-badge">{dsV7Active ? "Enabled" : "Off"}</span>
                  </label>

                  {dsV7Active ? (
                    <div className="rm-v6-panel">
                      <div className="rm-v6-banner">
                        <Sparkles size={15} aria-hidden="true" />
                        <span>
                          The proven SynthID-breaking regeneration runs unchanged, then a
                          non-generative camera re-life pass (Bayer CFA · sensor noise · lens ·
                          colour pipeline) replaces the generative fingerprint with camera
                          statistics. One JPEG encode, source-aware detector gate.
                        </span>
                      </div>

                      <div className="rm-v6-stats" aria-label="Pipeline indicators">
                        <span className="rm-stat">
                          <em>Wash</em>
                          <b>Qwen · denoise .08–.15</b>
                        </span>
                        <span className="rm-stat">
                          <em>Re-life</em>
                          <b>Bayer CFA + noise</b>
                        </span>
                        <span className="rm-stat">
                          <em>Encode</em>
                          <b>JPEG · q94</b>
                        </span>
                        <span className="rm-stat">
                          <em>Engine</em>
                          <b>{dsV7EngineMode === "adaptive" ? "≤3 gated passes" : "1 pass"}</b>
                        </span>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V7 engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV7EngineMode === "adaptive"}
                            className={dsV7EngineMode === "adaptive" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV7EngineMode("adaptive")}
                          >
                            Adaptive (detector-gated)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV7EngineMode === "template"}
                            className={dsV7EngineMode === "template" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV7EngineMode("template")}
                          >
                            Optimised template
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV7EngineMode === "adaptive"
                            ? "Each re-life rung (light → balanced → strong) is probed against the live detector on the DELIVERED bytes; the first pass that clears ships. Gates ai ≤ 45%, flux-family ≤ 30%, deepfake ≤ 10%. +2 credits."
                            : "One deterministic balanced pass. Fast and predictable, no detector calls."}
                        </p>
                      </div>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={dsV7IphoneExif}
                          disabled={batchRunning}
                          onChange={(event) => setDsV7IphoneExif(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Coherent device EXIF</span>
                      </label>
                    </div>
                  ) : null}

                  <label className={`rm-v6-toggle${dsV8Active ? " is-active" : ""}`}>
                    <input
                      type="checkbox"
                      checked={dsV8Active}
                      disabled={batchRunning}
                      onChange={(event) =>
                        chooseDeepCleanProfile(
                          event.target.checked ? "ds-remint-v8.1" : "max-cx-remint-v5"
                        )
                      }
                    />
                    <span className="rm-switch-track" aria-hidden="true">
                      <span className="rm-switch-thumb" />
                    </span>
                    <span className="rm-v6-toggle-text">
                      <strong>DS ReMint V8.1 · Ghost</strong>
                      <small>Quality-first floors · ghost_lite · device, metadata & naming</small>
                    </span>
                    <span className="rm-badge">{dsV8Active ? "Enabled" : "Off"}</span>
                  </label>

                  {dsV8Active ? (
                    <div className="rm-v6-panel">
                      <div className="rm-v6-banner">
                        <Sparkles size={15} aria-hidden="true" />
                        <span>
                          V8.1 keeps V8's quality floor but routes it through
                          ghost_lite (Malvar CFA + noise-floor matching, without the heavy
                          FPN signature) — quality stays closer to V7 while CFA/noise-mapping
                          graders still see camera structure. Metadata mode isolates grader
                          reactions to EXIF.
                        </span>
                      </div>

                      <div className="rm-v6-stats" aria-label="Pipeline indicators">
                        <span className="rm-stat">
                          <em>Wash</em>
                          <b>Qwen · denoise .08–.15</b>
                        </span>
                        <span className="rm-stat">
                          <em>Re-life</em>
                          <b>
                            {dsV8QualityFloor === "strong"
                              ? "ghost_lite → ghost"
                              : dsV8QualityFloor === "studio"
                              ? "light only"
                              : "light → ghost_lite"}
                          </b>
                        </span>
                        <span className="rm-stat">
                          <em>Encode</em>
                          <b>JPEG · q94</b>
                        </span>
                        <span className="rm-stat">
                          <em>Engine</em>
                          <b>{dsV8EngineMode === "adaptive" ? "≤3 gated passes" : "1 pass"}</b>
                        </span>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Quality floor</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8 quality floor">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV8QualityFloor === "studio"}
                            className={dsV8QualityFloor === "studio" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV8QualityFloor("studio")}
                          >
                            Studio
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV8QualityFloor === "balanced"}
                            className={dsV8QualityFloor === "balanced" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV8QualityFloor("balanced")}
                          >
                            Balanced
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV8QualityFloor === "strong"}
                            className={dsV8QualityFloor === "strong" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV8QualityFloor("strong")}
                          >
                            Strong
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV8QualityFloor === "studio"
                            ? "Studio: maximum fidelity, lightest re-life — for images that already grade well. Fewer pixels are touched, so detector headroom is lowest."
                            : dsV8QualityFloor === "strong"
                            ? "Strong: routes through ghost_lite and full ghost for maximum detector headroom — accept slightly softer fine detail."
                            : "Balanced: the recommended trade — ends on ghost_lite so CFA/noise-mapping graders see camera structure without the heavy FPN signature."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8 engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV8EngineMode === "adaptive"}
                            className={dsV8EngineMode === "adaptive" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV8EngineMode("adaptive")}
                          >
                            Adaptive (detector-gated)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV8EngineMode === "template"}
                            className={dsV8EngineMode === "template" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV8EngineMode("template")}
                          >
                            Optimised template
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV8EngineMode === "adaptive"
                            ? "Each rung of the quality-floor ladder is probed against the live detector on the DELIVERED bytes; the first pass that clears ships. +2 credits."
                            : "One deterministic pass at the chosen quality floor. Fast and predictable, no detector calls."}
                        </p>
                      </div>

                      <div className="rm-field-grid">
                        <label className="rm-field">
                          <span className="rm-field-label">File name</span>
                          <select
                            className="rm-select"
                            value={dsV8OutputNameStyle}
                            disabled={batchRunning}
                            onChange={(event) =>
                              setDsV8OutputNameStyle(
                                event.target.value as "photo-style" | "original" | "custom"
                              )
                            }
                          >
                            <option value="photo-style">Photo style (IMG_0000.JPG)</option>
                            <option value="original">Original name + -clean</option>
                            <option value="custom">Custom prefix…</option>
                          </select>
                        </label>
                        {dsV8OutputNameStyle === "custom" ? (
                          <label className="rm-field">
                            <span className="rm-field-label">Custom prefix</span>
                            <input
                              className="rm-input"
                              type="text"
                              value={dsV8OutputNameCustom}
                              disabled={batchRunning}
                              placeholder="ResMarke"
                              maxLength={60}
                              onChange={(event) => setDsV8OutputNameCustom(event.target.value)}
                            />
                          </label>
                        ) : null}
                      </div>

                      <div className="rm-field-grid">
                        <label className="rm-field">
                          <span className="rm-field-label">Device (EXIF)</span>
                          <select
                            className="rm-select"
                            value={dsV8Device}
                            disabled={batchRunning}
                            onChange={(event) => setDsV8Device(event.target.value as CxRemintDevice)}
                          >
                            <option value="auto">Auto</option>
                            <option value="iphone-16-pro-max">iPhone 16 Pro Max</option>
                            <option value="iphone-16-pro">iPhone 16 Pro</option>
                            <option value="iphone-16">iPhone 16</option>
                            <option value="iphone-15-pro-max">iPhone 15 Pro Max</option>
                            <option value="iphone-15-pro">iPhone 15 Pro</option>
                            <option value="iphone-15">iPhone 15</option>
                            <option value="iphone-14-pro">iPhone 14 Pro</option>
                          </select>
                        </label>
                        <label className="rm-field">
                          <span className="rm-field-label">Resolution metadata</span>
                          <select
                            className="rm-select"
                            value={dsV8ResolutionMode}
                            disabled={batchRunning}
                            onChange={(event) =>
                              setDsV8ResolutionMode(event.target.value as CxRemintResolutionMode)
                            }
                          >
                            <option value="off">Off</option>
                            <option value="standard">Standard (72 DPI)</option>
                            <option value="custom">Custom…</option>
                          </select>
                        </label>
                      </div>

                      {dsV8ResolutionMode === "custom" ? (
                        <div className="rm-field-grid">
                          <label className="rm-field">
                            <span className="rm-field-label">X resolution (DPI)</span>
                            <input
                              className="rm-input"
                              type="number"
                              min={1}
                              max={12000}
                              value={dsV8ResolutionX}
                              disabled={batchRunning}
                              onChange={(event) => setDsV8ResolutionX(Number(event.target.value))}
                            />
                          </label>
                          <label className="rm-field">
                            <span className="rm-field-label">Y resolution (DPI)</span>
                            <input
                              className="rm-input"
                              type="number"
                              min={1}
                              max={12000}
                              value={dsV8ResolutionY}
                              disabled={batchRunning}
                              onChange={(event) => setDsV8ResolutionY(Number(event.target.value))}
                            />
                          </label>
                        </div>
                      ) : null}

                      <div className="rm-field">
                        <span className="rm-field-label">Metadata</span>
                        <select
                          className="rm-select"
                          value={dsV8MetadataMode}
                          disabled={batchRunning}
                          onChange={(event) =>
                            setDsV8MetadataMode(event.target.value as "device" | "minimal")
                          }
                        >
                          <option value="device">Device EXIF (coherent)</option>
                          <option value="minimal">Minimal (no EXIF)</option>
                        </select>
                        <p className="rm-hint">
                          {dsV8MetadataMode === "device"
                            ? "Writes coherent device metadata. Some graders read metadata — switch to Minimal to isolate its effect on the verdict."
                            : "No EXIF bytes written. Use this to test graders whose metadata check is the residual signal."}
                        </p>
                      </div>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={dsV8IphoneExif}
                          disabled={batchRunning}
                          onChange={(event) => setDsV8IphoneExif(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Coherent device EXIF</span>
                      </label>
                    </div>
                  ) : null}

                  <label className={`rm-v6-toggle${dsV82Active ? " is-active" : ""}`}>
                    <input
                      type="checkbox"
                      checked={dsV82Active}
                      disabled={batchRunning}
                      onChange={(event) =>
                        chooseDeepCleanProfile(
                          event.target.checked ? "ds-remint-v8.2" : "max-cx-remint-v5"
                        )
                      }
                    />
                    <span className="rm-switch-track" aria-hidden="true">
                      <span className="rm-switch-thumb" />
                    </span>
                    <span className="rm-v6-toggle-text">
                      <strong>DS ReMint V8.2 · Max</strong>
                      <small>Degrade → deep clean → neural restore → re-life</small>
                    </span>
                    <span className="rm-badge">{dsV82Active ? "Enabled" : "Off"}</span>
                  </label>

                  {dsV82Active ? (
                    <div className="rm-v6-panel">
                      <div className="rm-v6-banner">
                        <Sparkles size={15} aria-hidden="true" />
                        <span>
                          V8.2 Max cleans the frame at reduced resolution where the
                          generator's fingerprint is cheapest to destroy, restores the detail
                          with a neural upscaler, then re-lifes the restoration so the
                          upscaler's own fingerprint never reaches the grader.
                        </span>
                      </div>

                      <div className="rm-v6-stats" aria-label="Pipeline indicators">
                        <span className="rm-stat">
                          <em>Degrade</em>
                          <b>
                            {dsV82QualityFloor === "strong"
                              ? "~50% scale"
                              : dsV82QualityFloor === "studio"
                              ? "~78% scale"
                              : "~62% scale"}
                          </b>
                        </span>
                        <span className="rm-stat">
                          <em>Clean</em>
                          <b>ghost @ low res</b>
                        </span>
                        <span className="rm-stat">
                          <em>Restore</em>
                          <b>Real-ESRGAN · ghost_lite</b>
                        </span>
                        <span className="rm-stat">
                          <em>Engine</em>
                          <b>{dsV82EngineMode === "adaptive" ? "≤3 gated floors" : "1 pass"}</b>
                        </span>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Quality floor</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.2 quality floor">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV82QualityFloor === "studio"}
                            className={dsV82QualityFloor === "studio" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV82QualityFloor("studio")}
                          >
                            Studio
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV82QualityFloor === "balanced"}
                            className={dsV82QualityFloor === "balanced" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV82QualityFloor("balanced")}
                          >
                            Balanced
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV82QualityFloor === "strong"}
                            className={dsV82QualityFloor === "strong" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV82QualityFloor("strong")}
                          >
                            Strong
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV82QualityFloor === "studio"
                            ? "Studio: lightest degradation (~78%), most original detail survives — for images that already grade well."
                            : dsV82QualityFloor === "strong"
                            ? "Strong: deepest degradation (~50%), most total fingerprint destruction, then neural restore rebuilds the detail."
                            : "Balanced: the recommended trade — ~62% degrade, full ghost clean at low res, neural restore + ghost_lite re-life."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Restore engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.2 restore engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV82RestoreEngine === "neural"}
                            className={dsV82RestoreEngine === "neural" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV82RestoreEngine("neural")}
                          >
                            Neural (Real-ESRGAN)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV82RestoreEngine === "classical"}
                            className={dsV82RestoreEngine === "classical" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV82RestoreEngine("classical")}
                          >
                            Classical (no re-stamp)
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV82RestoreEngine === "neural"
                            ? "Real-ESRGAN rebuilds detail, but stamps its own GAN fingerprint — the final re-life strips most of it. Use when quality beats detection."
                            : "Lanczos + dehalo + luma sharpening: zero new fingerprint. Use when a grader reads the restorer (Hive's flux2 signal) — quality trades slightly."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.2 engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV82EngineMode === "adaptive"}
                            className={dsV82EngineMode === "adaptive" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV82EngineMode("adaptive")}
                          >
                            Adaptive (detector-gated)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV82EngineMode === "template"}
                            className={dsV82EngineMode === "template" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV82EngineMode("template")}
                          >
                            Optimised template
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV82EngineMode === "adaptive"
                            ? "Floors run lightest-first (Studio → Balanced → Strong); each candidate is probed on the DELIVERED bytes and the first that clears ships. +2 credits."
                            : "One deterministic pass at the chosen floor. Fast and predictable, no detector calls."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Metadata</span>
                        <select
                          className="rm-select"
                          value={dsV82MetadataMode}
                          disabled={batchRunning}
                          onChange={(event) =>
                            setDsV82MetadataMode(event.target.value as "device" | "minimal")
                          }
                        >
                          <option value="device">Device EXIF (coherent)</option>
                          <option value="minimal">Minimal (no EXIF)</option>
                        </select>
                      </div>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={dsV82IphoneExif}
                          disabled={batchRunning}
                          onChange={(event) => setDsV82IphoneExif(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Coherent device EXIF</span>
                      </label>
                    </div>
                  ) : null}

                  <label className={`rm-v6-toggle${dsV83Active ? " is-active" : ""}`}>
                    <input
                      type="checkbox"
                      checked={dsV83Active}
                      disabled={batchRunning}
                      onChange={(event) =>
                        chooseDeepCleanProfile(
                          event.target.checked ? "ds-remint-v8.3" : "max-cx-remint-v5"
                        )
                      }
                    />
                    <span className="rm-switch-track" aria-hidden="true">
                      <span className="rm-switch-thumb" />
                    </span>
                    <span className="rm-v6-toggle-text">
                      <strong>DS ReMint V8.3 · Wash Lab</strong>
                      <small>Wash family · restore engine · degrade floors</small>
                    </span>
                    <span className="rm-badge">{dsV83Active ? "Enabled" : "Off"}</span>
                  </label>

                  {dsV83Active ? (
                    <div className="rm-v6-panel">
                      <div className="rm-v6-banner">
                        <Sparkles size={15} aria-hidden="true" />
                        <span>
                          The wash-family unlock: graders read Z-Image at ~4-6% where they
                          read Qwen at 12-72%. V8.3 lets you wash with Qwen, Z-Image, or a
                          50/50 blend of both, then runs the full degrade → restore → re-life
                          chain. SynthID removal must be re-verified per wash choice.
                        </span>
                      </div>

                      <div className="rm-v6-stats" aria-label="Pipeline indicators">
                        <span className="rm-stat">
                          <em>Wash</em>
                          <b>{dsV83WashModel === "qwen+zimage" ? "Qwen ⊕ Z-Image" : dsV83WashModel}</b>
                        </span>
                        <span className="rm-stat">
                          <em>Degrade</em>
                          <b>
                            {dsV83QualityFloor === "strong"
                              ? "~50% scale"
                              : dsV83QualityFloor === "studio"
                              ? "~78% scale"
                              : "~62% scale"}
                          </b>
                        </span>
                        <span className="rm-stat">
                          <em>Restore</em>
                          <b>{dsV83RestoreEngine === "neural" ? "Real-ESRGAN" : "Classical (0 stamp)"}</b>
                        </span>
                        <span className="rm-stat">
                          <em>Engine</em>
                          <b>{dsV83EngineMode === "adaptive" ? "≤3 gated floors" : "1 pass"}</b>
                        </span>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Wash model</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.3 wash model">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83WashModel === "qwen"}
                            className={dsV83WashModel === "qwen" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83WashModel("qwen")}
                          >
                            Qwen (proven)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83WashModel === "zimage"}
                            className={dsV83WashModel === "zimage" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83WashModel("zimage")}
                          >
                            Z-Image (~4-6%)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83WashModel === "qwen+zimage"}
                            className={dsV83WashModel === "qwen+zimage" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83WashModel("qwen+zimage")}
                          >
                            Qwen ⊕ Z-Image
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV83WashModel === "qwen"
                            ? "The proven SynthID breaker — also the strongest flux attribution source (12-72%)."
                            : dsV83WashModel === "zimage"
                            ? "The low-attribution family: full-frame Z-Image img2img at low denoise. Verify SynthID removal before trusting it as the default."
                            : "Both washes blended 50/50 — splits the source-attribution vote between families while every pixel is still reconstructed. Recommended first test."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Restore engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.3 restore engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83RestoreEngine === "neural"}
                            className={dsV83RestoreEngine === "neural" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83RestoreEngine("neural")}
                          >
                            Neural (Real-ESRGAN)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83RestoreEngine === "classical"}
                            className={dsV83RestoreEngine === "classical" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83RestoreEngine("classical")}
                          >
                            Classical (no re-stamp)
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV83RestoreEngine === "neural"
                            ? "Real-ESRGAN rebuilds detail but stamps its own GAN fingerprint — final re-life strips most of it."
                            : "Lanczos + dehalo + luma sharpening: zero new fingerprint, slightly softer detail."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Quality floor</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.3 quality floor">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83QualityFloor === "studio"}
                            className={dsV83QualityFloor === "studio" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83QualityFloor("studio")}
                          >
                            Studio
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83QualityFloor === "balanced"}
                            className={dsV83QualityFloor === "balanced" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83QualityFloor("balanced")}
                          >
                            Balanced
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83QualityFloor === "strong"}
                            className={dsV83QualityFloor === "strong" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83QualityFloor("strong")}
                          >
                            Strong
                          </button>
                        </div>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.3 engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83EngineMode === "adaptive"}
                            className={dsV83EngineMode === "adaptive" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83EngineMode("adaptive")}
                          >
                            Adaptive (detector-gated)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV83EngineMode === "template"}
                            className={dsV83EngineMode === "template" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV83EngineMode("template")}
                          >
                            Optimised template
                          </button>
                        </div>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Metadata</span>
                        <select
                          className="rm-select"
                          value={dsV83MetadataMode}
                          disabled={batchRunning}
                          onChange={(event) =>
                            setDsV83MetadataMode(event.target.value as "device" | "minimal")
                          }
                        >
                          <option value="device">Device EXIF (coherent)</option>
                          <option value="minimal">Minimal (no EXIF)</option>
                        </select>
                      </div>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={dsV83IphoneExif}
                          disabled={batchRunning}
                          onChange={(event) => setDsV83IphoneExif(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Coherent device EXIF</span>
                      </label>
                    </div>
                  ) : null}

                  <label className={`rm-v6-toggle${dsV88Active ? " is-active" : ""}`}>
                    <input
                      type="checkbox"
                      checked={dsV88Active}
                      disabled={batchRunning}
                      onChange={(event) =>
                        chooseDeepCleanProfile(
                          event.target.checked ? "ds-remint-v8.9" : "max-cx-remint-v5"
                        )
                      }
                    />
                    <span className="rm-switch-track" aria-hidden="true">
                      <span className="rm-switch-thumb" />
                    </span>
                    <span className="rm-v6-toggle-text">
                      <strong>DS ReMint V8.9 · Coherent Pro</strong>
                      <small>Data-tuned coherent model · baseline routing</small>
                    </span>
                    <span className="rm-badge">{dsV88Active ? "Enabled" : "Off"}</span>
                  </label>

                  {dsV88Active ? (
                    <div className="rm-v6-panel">
                      <div className="rm-v6-banner">
                        <Sparkles size={15} aria-hidden="true" />
                        <span>
                          V8.9 is the live-test winner: Qwen wash + coherent model read
                          ~0% flux on source graders, Light/Balanced ship "not likely AI", and
                          baseline routing starts heavier only when the input already grades
                          flagged. Deep now degrades 75% (was 68%) for far better quality.
                        </span>
                      </div>

                      <div className="rm-v6-stats" aria-label="Pipeline indicators">
                        <span className="rm-stat">
                          <em>Wash</em>
                          <b>{dsV88WashModel === "qwen+zimage" ? "Qwen ⊕ Z-Image" : dsV88WashModel}</b>
                        </span>
                        <span className="rm-stat">
                          <em>Camera</em>
                          <b>{dsV88Strength} model</b>
                        </span>
                        <span className="rm-stat">
                          <em>Resample</em>
                          <b>1× · ≤1250px</b>
                        </span>
                        <span className="rm-stat">
                          <em>Engine</em>
                          <b>{dsV88EngineMode === "adaptive" ? "≤3 gated strengths" : "1 pass"}</b>
                        </span>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Wash model</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.8 wash model">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88WashModel === "qwen"}
                            className={dsV88WashModel === "qwen" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88WashModel("qwen")}
                          >
                            Qwen (proven)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88WashModel === "zimage"}
                            className={dsV88WashModel === "zimage" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88WashModel("zimage")}
                          >
                            Z-Image (~4-6%)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88WashModel === "qwen+zimage"}
                            className={dsV88WashModel === "qwen+zimage" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88WashModel("qwen+zimage")}
                          >
                            Qwen ⊕ Z-Image
                          </button>
                        </div>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Strength</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.8 strength">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88Strength === "light"}
                            className={dsV88Strength === "light" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88Strength("light")}
                          >
                            Light
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88Strength === "balanced"}
                            className={dsV88Strength === "balanced" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88Strength("balanced")}
                          >
                            Balanced
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88Strength === "deep"}
                            className={dsV88Strength === "deep" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88Strength("deep")}
                          >
                            Deep
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV88Strength === "light"
                            ? "Light: faintest optics, minimal noise, ~cleanup 10% — for images that already grade well."
                            : dsV88Strength === "deep"
                            ? "Deep (legacy rescue): degrade 75% → low-res pass → restore. Only when Balanced cannot clear — it costs visible quality."
                            : "Balanced: the recommended coherent model — paired inverse/forward CCM, MHC demosaic, SNR-coupled denoise, multiscale cleanup."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Engine</span>
                        <div className="rm-seg" role="radiogroup" aria-label="DS ReMint V8.8 engine">
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88EngineMode === "adaptive"}
                            className={dsV88EngineMode === "adaptive" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88EngineMode("adaptive")}
                          >
                            Adaptive (detector-gated)
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={dsV88EngineMode === "template"}
                            className={dsV88EngineMode === "template" ? "is-active" : ""}
                            disabled={batchRunning}
                            onClick={() => setDsV88EngineMode("template")}
                          >
                            Optimised template
                          </button>
                        </div>
                        <p className="rm-hint">
                          {dsV88EngineMode === "adaptive"
                            ? "Strengths run lightest-first; each is probed on the DELIVERED bytes and the least destructive pass that clears ships. +2 credits."
                            : "One deterministic pass at the chosen strength. No detector calls."}
                        </p>
                      </div>

                      <div className="rm-field">
                        <span className="rm-field-label">Metadata</span>
                        <select
                          className="rm-select"
                          value={dsV88MetadataMode}
                          disabled={batchRunning}
                          onChange={(event) =>
                            setDsV88MetadataMode(event.target.value as "device" | "minimal")
                          }
                        >
                          <option value="device">Device EXIF (coherent)</option>
                          <option value="minimal">Minimal (no EXIF)</option>
                        </select>
                      </div>

                      <label className="rm-switch">
                        <input
                          type="checkbox"
                          checked={dsV88IphoneExif}
                          disabled={batchRunning}
                          onChange={(event) => setDsV88IphoneExif(event.target.checked)}
                        />
                        <span className="rm-switch-track" aria-hidden="true">
                          <span className="rm-switch-thumb" />
                        </span>
                        <span>Coherent device EXIF</span>
                      </label>
                    </div>
                  ) : null}

                  {!dsV6Active && !dsV7Active && !dsV8Active && !dsV82Active && !dsV83Active && !dsV88Active ? (
                  <div className="rm-field-grid">
                    <label className="rm-field">
                      <span className="rm-field-label">Profile</span>
                      <select
                        className="rm-select"
                        value={deepCleanProfile}
                        disabled={batchRunning}
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
                        <option value="ds-remint-v6">DS ReMint V6 (new)</option>
                        <option value="ds-remint-v7">DS ReMint V7 (new)</option>
                        <option value="ds-remint-v8">DS ReMint V8</option>
                        <option value="ds-remint-v8.1">DS ReMint V8.1 (new)</option>
                        <option value="ds-remint-v8.2">DS ReMint V8.2 Max (new)</option>
                        <option value="ds-remint-v8.3">DS ReMint V8.3 Wash Lab (new)</option>
                        <option value="ds-remint-v8.8">DS ReMint V8.8 Coherent</option>
                        <option value="ds-remint-v8.9">DS ReMint V8.9 Coherent Pro (new)</option>
                      </select>
                    </label>
                    <label className="rm-field">
                      <span className="rm-field-label">Output</span>
                      <select
                        className="rm-select"
                        value={deepCleanOutputMode}
                        disabled={batchRunning}
                        onChange={(event) => setDeepCleanOutputMode(event.target.value as DeepCleanOutputMode)}
                      >
                        <option value="stripped">Stripped only</option>
                        <option value="sealed">Stripped + Creator Seal</option>
                        <option value="sealed-stamped">Stripped + seal + stamp</option>
                      </select>
                    </label>
                  </div>
                  ) : null}

                  {deepCleanProfile === "max" ? (
                    <label className="rm-switch">
                      <input
                        type="checkbox"
                        checked={deepCleanMicroTextureJitter}
                        disabled={batchRunning}
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
                            disabled={batchRunning}
                            onClick={() => setCxEngineMode("template")}
                          >
                            Optimised template
                          </button>
                          <button
                            type="button"
                            role="radio"
                            aria-checked={cxEngineMode === "adaptive"}
                            className={cxEngineMode === "adaptive" ? "is-active" : ""}
                            disabled={batchRunning}
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
                          disabled={batchRunning}
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
                          disabled={batchRunning}
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
                          disabled={batchRunning}
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
                                  disabled={batchRunning}
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
                              disabled={batchRunning}
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
                              disabled={batchRunning}
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
                        <div className="rm-cx-subpanel">
                          <label className="rm-field">
                            <span className="rm-field-label">Device</span>
                            <select
                              className="rm-select"
                              value={cxDevice}
                              disabled={batchRunning}
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

                          <div className="rm-field">
                            <span className="rm-field-label">Resolution metadata (DPI)</span>
                            <div
                              className="rm-seg rm-seg-sm"
                              role="radiogroup"
                              aria-label="Resolution metadata"
                            >
                              {([
                                ["off", "Off"],
                                ["standard", "On · 72 DPI"],
                                ["custom", "Custom"]
                              ] as const).map(([mode, label]) => (
                                <button
                                  key={mode}
                                  type="button"
                                  role="radio"
                                  aria-checked={cxResolutionMode === mode}
                                  className={cxResolutionMode === mode ? "is-active" : ""}
                                  disabled={batchRunning}
                                  onClick={() => setCxResolutionMode(mode)}
                                >
                                  {label}
                                </button>
                              ))}
                            </div>
                            <p className="rm-hint">
                              This controls print/layout metadata only. It does not resize the image
                              or change its pixel detail.
                            </p>
                          </div>

                          {cxResolutionMode === "custom" ? (
                            <div className="rm-field-grid">
                              <label className="rm-field">
                                <span className="rm-field-label">Horizontal DPI</span>
                                <input
                                  className="rm-input"
                                  type="number"
                                  min={1}
                                  max={12000}
                                  step={1}
                                  value={cxResolutionX}
                                  disabled={batchRunning}
                                  onChange={(event) => {
                                    const value = event.currentTarget.valueAsNumber;
                                    if (Number.isFinite(value)) setCxResolutionX(value);
                                  }}
                                />
                              </label>
                              <label className="rm-field">
                                <span className="rm-field-label">Vertical DPI</span>
                                <input
                                  className="rm-input"
                                  type="number"
                                  min={1}
                                  max={12000}
                                  step={1}
                                  value={cxResolutionY}
                                  disabled={batchRunning}
                                  onChange={(event) => {
                                    const value = event.currentTarget.valueAsNumber;
                                    if (Number.isFinite(value)) setCxResolutionY(value);
                                  }}
                                />
                              </label>
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      <div className="rm-disc-note">
                        {deepCleanProfile === "max-cx-remint-v5"
                          ? "CX Remint v5 (recommended) applies maximum removal at your chosen quality floor, then upscales the delivered image back above 1080px with sharpening and fresh grain. The Strong ~960px floor is the recommended balance. Everything from v4 — SynthID regeneration, histogram tone matching, and realism — is included."
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
                    {batchRunning ? (
                      <>
                        <Loader2 className="rm-spin" size={18} aria-hidden="true" />
                        Processing queue…
                      </>
                    ) : (
                      <>
                        <Cloud size={18} aria-hidden="true" />
                        {pendingBatchItems.some((item) => item.status === "failed")
                          ? "Retry unfinished"
                          : `Process ${pendingBatchItems.length} ${pendingBatchItems.length === 1 ? "image" : "images"}`}
                        {batchRequiredCost ? ` · ${batchRequiredCost} credits` : ""}
                      </>
                    )}
                  </button>

                  {pendingBatchItems.length > 0 &&
                  credits.privacyCredits < batchRequiredCost ? (
                    <div className="rm-warn">
                      <span>
                        This queue needs {batchRequiredCost} credits; you have{" "}
                        {credits.privacyCredits}.
                      </span>
                    </div>
                  ) : null}

                  {deepCleanProfile !== "max-remint" &&
                  deepCleanProfile !== "max-optimised-remint" &&
                  !isCxProfile(deepCleanProfile) &&
                  !dsV6Active &&
                  !dsV7Active &&
                  !dsV8Active &&
                  !dsV82Active &&
                  !dsV83Active &&
                  !dsV88Active ? (
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
                                disabled={batchRunning}
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
                            disabled={batchRunning || expertRefinementMode === "off"}
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
                                      disabled={batchRunning || disabled || lockedByLines}
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
                                      disabled={
                                        batchRunning || disabled || !techConfig.enabled || lockedByLines
                                      }
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
                                disabled={batchRunning || expertRefinementMode === "off"}
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
                          {(() => {
                            const rating = readRating88(deepCleanJob.report);
                            if (rating === null) return null;
                            const band = rating <= 29 ? "low" : rating <= 58 ? "mid" : "high";
                            return (
                              <div className={`rm-flagrisk rm-flagrisk-${band}`}>
                                AI-flag risk: {rating}/88
                              </div>
                            );
                          })()}
                          <button
                            className="rm-btn rm-btn-max rm-btn-block"
                            type="button"
                            disabled={!activeQueueItem || downloadingItemId === activeQueueItem.id}
                            onClick={() => {
                              if (activeQueueItem) void downloadQueueItem(activeQueueItem);
                            }}
                          >
                            {activeQueueItem && downloadingItemId === activeQueueItem.id ? (
                              <Loader2 className="rm-spin" size={18} aria-hidden="true" />
                            ) : (
                              <Download size={18} aria-hidden="true" />
                            )}
                            Download this image
                          </button>
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
        multiple
        accept="image/jpeg,image/png,image/webp"
        onChange={(event) => {
          addFiles(Array.from(event.target.files ?? []));
          event.currentTarget.value = "";
        }}
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

function BatchQueue({
  items,
  activeId,
  draggedId,
  running,
  notice,
  completedCount,
  zipBusy,
  downloadingItemId,
  onAdd,
  onSelect,
  onRemove,
  onDragStart,
  onDragEnd,
  onMove,
  onDownload,
  onDownloadAll
}: {
  items: ImageQueueItem[];
  activeId: string;
  draggedId: string;
  running: boolean;
  notice: string;
  completedCount: number;
  zipBusy: boolean;
  downloadingItemId: string;
  onAdd: () => void;
  onSelect: (item: ImageQueueItem) => void;
  onRemove: (id: string) => void;
  onDragStart: (id: string) => void;
  onDragEnd: () => void;
  onMove: (sourceId: string, targetId: string) => void;
  onDownload: (item: ImageQueueItem) => void;
  onDownloadAll: () => void;
}) {
  return (
    <section className="rm-batch" aria-labelledby="rm-batch-title">
      <div className="rm-batch-head">
        <div className="rm-batch-heading">
          <span className="rm-card-icon">
            <Images size={18} aria-hidden="true" />
          </span>
          <div>
            <div className="rm-batch-title-row">
              <h2 id="rm-batch-title">Processing queue</h2>
              <span className="rm-queue-count">
                {items.length} / {MAX_QUEUE_IMAGES}
              </span>
            </div>
            <p>
              {running
                ? "Queue locked while processing. Each image runs in the order shown."
                : "Drag tiles to set the processing order. Select one to inspect it."}
            </p>
          </div>
        </div>
        <div className="rm-batch-actions">
          <button
            className="rm-btn rm-btn-soft rm-btn-sm"
            type="button"
            onClick={onAdd}
            disabled={running || items.length >= MAX_QUEUE_IMAGES}
          >
            <Upload size={15} aria-hidden="true" /> Add
          </button>
          <button
            className="rm-btn rm-btn-primary rm-btn-sm"
            type="button"
            onClick={onDownloadAll}
            disabled={!completedCount || zipBusy}
          >
            {zipBusy ? (
              <Loader2 className="rm-spin" size={15} aria-hidden="true" />
            ) : (
              <Archive size={15} aria-hidden="true" />
            )}
            Download all{completedCount ? ` (${completedCount})` : ""}
          </button>
        </div>
      </div>

      <div className="rm-queue-list" role="list" aria-label="Images in processing order">
        {items.map((item, index) => {
          const isBusy = ["preparing", "uploading", "queued", "processing"].includes(item.status);
          return (
            <article
              className={[
                "rm-queue-item",
                activeId === item.id ? "is-active" : "",
                draggedId === item.id ? "is-dragging" : "",
                item.status === "failed" ? "has-failed" : "",
                item.status === "completed" ? "is-complete" : ""
              ]
                .filter(Boolean)
                .join(" ")}
              key={item.id}
              role="listitem"
              draggable={!running}
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("text/plain", item.id);
                onDragStart(item.id);
              }}
              onDragOver={(event) => {
                if (!running) {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                onMove(draggedId || event.dataTransfer.getData("text/plain"), item.id);
                onDragEnd();
              }}
              onDragEnd={onDragEnd}
            >
              <div className="rm-queue-item-top">
                <span className="rm-queue-order">{String(index + 1).padStart(2, "0")}</span>
                <span className="rm-queue-grip" title="Drag to reorder">
                  <GripVertical size={15} aria-hidden="true" />
                </span>
                <button
                  className="rm-queue-icon-btn"
                  type="button"
                  onClick={() => onRemove(item.id)}
                  disabled={running}
                  title={`Remove ${item.file.name}`}
                  aria-label={`Remove ${item.file.name}`}
                >
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </div>

              <button
                className="rm-queue-select"
                type="button"
                disabled={running}
                aria-current={activeId === item.id ? "true" : undefined}
                onClick={() => onSelect(item)}
                onKeyDown={(event) => {
                  if (running || !event.altKey) return;
                  if (event.key === "ArrowLeft" && index > 0) {
                    event.preventDefault();
                    onMove(item.id, items[index - 1].id);
                  }
                  if (event.key === "ArrowRight" && index < items.length - 1) {
                    event.preventDefault();
                    onMove(item.id, items[index + 1].id);
                  }
                }}
              >
                <span className="rm-queue-thumb">
                  <img src={item.previewUrl} alt="" draggable={false} />
                  {isBusy ? (
                    <span className="rm-queue-thumb-veil">
                      <Loader2 className="rm-spin" size={19} aria-hidden="true" />
                    </span>
                  ) : item.status === "completed" ? (
                    <span className="rm-queue-thumb-done">
                      <Check size={14} aria-hidden="true" />
                    </span>
                  ) : null}
                </span>
                <span className="rm-queue-file">
                  <strong title={item.file.name}>{item.file.name}</strong>
                  <small>
                    {item.width && item.height ? `${item.width}×${item.height} · ` : ""}
                    {(item.file.size / 1_000_000).toFixed(2)} MB
                  </small>
                </span>
              </button>

              <div className="rm-queue-item-foot">
                <span className={`rm-queue-status is-${item.status}`}>
                  {queueStatusLabel(item.status)}
                </span>
                {item.status === "completed" ? (
                  <button
                    className="rm-queue-download"
                    type="button"
                    onClick={() => onDownload(item)}
                    disabled={Boolean(downloadingItemId) || zipBusy}
                    title={`Download ${item.file.name}`}
                    aria-label={`Download processed ${item.file.name}`}
                  >
                    {downloadingItemId === item.id ? (
                      <Loader2 className="rm-spin" size={14} aria-hidden="true" />
                    ) : (
                      <Download size={14} aria-hidden="true" />
                    )}
                  </button>
                ) : null}
              </div>
              {item.error ? <p className="rm-queue-error">{item.error}</p> : null}
            </article>
          );
        })}
      </div>

      {notice ? (
        <p className="rm-batch-notice" role="status">
          {notice}
        </p>
      ) : null}
    </section>
  );
}

function queueStatusLabel(status: QueueItemStatus) {
  switch (status) {
    case "preparing":
      return "Preparing";
    case "uploading":
      return "Uploading";
    case "queued":
      return "Queued";
    case "processing":
      return "Processing";
    case "completed":
      return "Ready";
    case "failed":
      return "Failed";
    default:
      return "Ready to run";
  }
}

function Dropzone({
  large = false,
  previewUrl,
  dragging,
  setDragging,
  onPick,
  onDropFiles
}: {
  large?: boolean;
  previewUrl: string;
  dragging: boolean;
  setDragging: (next: boolean) => void;
  onPick: () => void;
  onDropFiles: (files: File[]) => void;
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
        onDropFiles(Array.from(event.dataTransfer.files));
      }}
    >
      {previewUrl ? (
        <img src={previewUrl} alt="Selected image preview" />
      ) : (
        <div className="rm-drop-inner">
          <span className="rm-drop-icon">
            <Upload size={26} aria-hidden="true" />
          </span>
          <div className="rm-drop-title">Drop up to 20 images to begin</div>
          <div className="rm-drop-sub">
            or <span className="rm-drop-browse">browse files</span> · JPEG, PNG, WebP · 25MB each
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

/**
 * Pull the 0-88 AI-flag risk score out of a DeepClean job report.
 *
 * The worker nests its engine report under `report.engine`, so that is the
 * canonical path; the top-level fallback covers any caller that hands us the
 * engine report directly. Returns null whenever there is no usable score
 * (template mode, no detector configured, or a detector infra error), in which
 * case the chip is hidden rather than showing a misleading zero.
 */
function readRating88(report: Record<string, unknown> | undefined): number | null {
  if (!report) return null;
  const engine = report.engine;
  const candidates = [
    engine && typeof engine === "object" ? (engine as Record<string, unknown>).rating_88 : undefined,
    report.rating_88,
  ];
  for (const value of candidates) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Math.max(0, Math.min(88, Math.round(value)));
    }
  }
  return null;
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
