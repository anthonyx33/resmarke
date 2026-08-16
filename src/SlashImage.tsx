import {
  ArrowRight,
  Check,
  ChevronDown,
  Download,
  Fingerprint,
  ImagePlus,
  Loader2,
  LogOut,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Upload,
  X
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { hasSupabaseConfig } from "./lib/config";
import { supabase } from "./lib/supabase";
import {
  cancelDeepCleanJob,
  createDeepCleanJob,
  dispatchDeepCleanJob,
  getDeepCleanJob,
  uploadDeepCleanInput,
  type CxRemintEngineMode,
  type DeepCleanJob
} from "./lib/deepcleanClient";

type Mode = "sequence" | "remint" | "finish";
type QueueStatus =
  | "waiting"
  | "preparing"
  | "uploading"
  | "queued"
  | "processing"
  | "completed"
  | "failed";

type QueueItem = {
  id: string;
  file: File;
  preview: string;
  status: QueueStatus;
  job?: DeepCleanJob;
  error?: string;
  outputUrl?: string;
  report?: string;
};

const COST: Record<Mode, number> = { sequence: 17, remint: 15, finish: 6 };

const MODE_META: Record<
  Mode,
  { title: string; blurb: string; badge: string; steps: string[] }
> = {
  sequence: {
    title: "V8.9 → Quality Finish",
    blurb: "The full two-step flow: break the carrier, then restore the photograph.",
    badge: "Recommended",
    steps: ["Wash · Qwen", "Coherent camera", "Gate", "Selective restoration", "Q95 4:4:4"]
  },
  remint: {
    title: "V8.9 Coherent Pro",
    blurb: "Fingerprint removal only. Frozen, proven, byte-stable.",
    badge: "Step 1",
    steps: ["Wash · Qwen", "Coherent camera", "Gate", "Q92 4:2:0"]
  },
  finish: {
    title: "Quality Finish",
    blurb: "Polish an already-reminted file. Non-generative, deterministic.",
    badge: "Step 2",
    steps: ["JPEG cleanup", "Noise floor kept", "Chroma repair", "1.6× HD", "Q95 4:4:4"]
  }
};

export default function SlashImage() {
  const [userId, setUserId] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [credits, setCredits] = useState<number | null>(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authStatus, setAuthStatus] = useState("");
  const [authBusy, setAuthBusy] = useState(false);

  const [mode, setMode] = useState<Mode>("sequence");
  const [expertOpen, setExpertOpen] = useState(false);

  // Remint (V8.9) options.
  const [washModel, setWashModel] = useState<"qwen" | "zimage" | "qwen+zimage">("qwen");
  const [strength, setStrength] = useState<"light" | "balanced" | "deep">("balanced");
  const [engineMode, setEngineMode] = useState<CxRemintEngineMode>("adaptive");
  const [iphoneExif, setIphoneExif] = useState(true);
  const [metadataMode, setMetadataMode] = useState<"device" | "minimal">("device");
  // Finish options.
  const [finishPreset, setFinishPreset] = useState<"conservative" | "standard" | "strong">("standard");
  const [finishScale, setFinishScale] = useState<"native" | "1.6" | "2">("1.6");
  // Output naming.
  const [nameStyle, setNameStyle] = useState<"photo-style" | "original" | "custom">("photo-style");
  const [nameCustom, setNameCustom] = useState("");

  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [running, setRunning] = useState(false);
  const [statusLine, setStatusLine] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
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

  async function refreshCredits(uid: string) {
    if (!supabase) return;
    const { data, error } = await supabase
      .from("creator_profiles")
      .select("deepclean_credits")
      .eq("user_id", uid)
      .single();
    if (!error && data) setCredits(data.deepclean_credits);
  }

  async function submitAuth() {
    if (!supabase) return;
    setAuthBusy(true);
    setAuthStatus("");
    try {
      if (!authEmail || !authPassword) {
        setAuthStatus("Enter your email and password.");
        return;
      }
      const { error } = await supabase.auth.signInWithPassword({
        email: authEmail.trim(),
        password: authPassword
      });
      if (error) setAuthStatus(error.message);
    } finally {
      setAuthBusy(false);
    }
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUserId("");
    setUserEmail("");
    setCredits(null);
    setQueue([]);
  }

  function addFiles(files: File[]) {
    const images = files
      .filter((f) => f.type.startsWith("image/"))
      .slice(0, 20);
    const next: QueueItem[] = images.map((file) => ({
      id: crypto.randomUUID(),
      file,
      preview: URL.createObjectURL(file),
      status: "waiting"
    }));
    setQueue((q) => [...q, ...next].slice(0, 20));
  }

  function removeItem(id: string) {
    setQueue((q) => q.filter((item) => item.id !== id));
  }

  const doneCount = queue.filter((q) => q.status === "completed").length;
  const failedCount = queue.filter((q) => q.status === "failed").length;

  async function spendCredits(amount: number) {
    if (!supabase || !userId || amount <= 0) return;
    const { data, error } = await supabase.functions.invoke("spend-privacy-credit", {
      body: { amount }
    });
    if (error) throw error;
    if (data?.deepCleanCredits !== undefined) setCredits(data.deepCleanCredits);
  }

  function buildJobOptions() {
    const finishOptions = {
      preset: finishPreset,
      scale: finishScale === "native" ? null : Number(finishScale)
    };
    const remintOptions = {
      engineMode,
      washModel,
      strength,
      iphoneExif,
      metadataMode
    };
    const naming = {
      outputNameStyle: nameStyle,
      outputNameCustom: nameStyle === "custom" ? nameCustom : undefined
    };
    if (mode === "sequence") {
      return {
        profile: "ds-remint-v8.9-hd" as const,
        dsRemintV89Hd: { remint: remintOptions, finish: finishOptions },
        ...naming
      };
    }
    if (mode === "remint") {
      return { profile: "ds-remint-v8.9" as const, dsRemintV89: remintOptions, ...naming };
    }
    return { profile: "quality-finish" as const, qualityFinish: finishOptions };
  }

  async function runQueue() {
    if (!supabase || !userId) return;
    if (queue.length === 0 || running) return;
    setRunning(true);
    let completed = 0;
    let failed = 0;

    for (const item of queue) {
      if (item.status === "completed") {
        completed += 1;
        continue;
      }
      let job: DeepCleanJob | undefined;
      try {
        setQueue((q) =>
          q.map((x) => (x.id === item.id ? { ...x, status: "preparing" } : x))
        );
        setStatusLine(`Preparing ${item.file.name}…`);
        const options = buildJobOptions();
        job = await createDeepCleanJob({
          file: item.file,
          creatorId: userId,
          profile: options.profile,
          outputMode: "stripped",
          dsRemintV89: "dsRemintV89" in options ? options.dsRemintV89 : undefined,
          qualityFinish: "qualityFinish" in options ? options.qualityFinish : undefined,
          dsRemintV89Hd: "dsRemintV89Hd" in options ? options.dsRemintV89Hd : undefined,
          outputNameStyle: "outputNameStyle" in options ? options.outputNameStyle : undefined,
          outputNameCustom: "outputNameCustom" in options ? options.outputNameCustom : undefined
        });

        setQueue((q) =>
          q.map((x) => (x.id === item.id ? { ...x, status: "uploading", job } : x))
        );
        setStatusLine(`Uploading ${item.file.name} privately…`);
        await uploadDeepCleanInput(job, item.file);

        setQueue((q) =>
          q.map((x) => (x.id === item.id ? { ...x, status: "queued" } : x))
        );
        setStatusLine(`Sending ${item.file.name} to the GPU…`);
        await dispatchDeepCleanJob(job.id);
        await spendCredits(COST[mode]);

        setQueue((q) =>
          q.map((x) => (x.id === item.id ? { ...x, status: "processing", job } : x))
        );

        const completedJob = await pollJob(job.id);
        const report = summarizeReport(completedJob.report, mode);
        setQueue((q) =>
          q.map((x) =>
            x.id === item.id
              ? { ...x, status: "completed", job: completedJob, outputUrl: completedJob.outputUrl, report }
              : x
          )
        );
        completed += 1;
        if (userId) void refreshCredits(userId);
      } catch (err) {
        const message = err instanceof Error ? err.message : "This image could not be processed.";
        if (job) await cancelDeepCleanJob(job.id).catch(() => undefined);
        setQueue((q) =>
          q.map((x) =>
            x.id === item.id ? { ...x, status: "failed", error: message, job } : x
          )
        );
        failed += 1;
        setStatusLine(`${item.file.name}: ${message}`);
      }
    }

    setRunning(false);
    setStatusLine(
      failed > 0
        ? `Done · ${completed} completed · ${failed} failed`
        : `Done · all ${completed} ${completed === 1 ? "image is" : "images are"} ready`
    );
  }

  async function pollJob(jobId: string): Promise<DeepCleanJob> {
    const deadline = Date.now() + 12 * 60 * 1000;
    for (;;) {
      await new Promise((r) => setTimeout(r, 4000));
      const job = await getDeepCleanJob(jobId);
      if (job.status === "completed" || job.status === "failed") return job;
      if (Date.now() > deadline) throw new Error("Timed out waiting for the worker.");
    }
  }

  const activeJobCount = queue.filter(
    (q) => q.status === "preparing" || q.status === "uploading" || q.status === "processing" || q.status === "queued"
  ).length;
  const waitingCount = queue.filter((q) => q.status === "waiting").length;

  const canRun =
    !running &&
    userId !== "" &&
    (waitingCount > 0 || (queue.length > 0 && failedCount > 0 && queue.every((q) => q.status === "completed" || q.status === "failed" || q.status === "waiting"))) &&
    queue.length > 0;

  const meta = MODE_META[mode];

  if (!hasSupabaseConfig) {
    return (
      <div className="slash-root">
        <div className="slash-center-card">
          <h2>Slash Image needs Supabase configuration.</h2>
          <p>Set the VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY environment variables.</p>
        </div>
      </div>
    );
  }

  if (!userId) {
    return (
      <div className="slash-root">
        <div className="slash-center-card">
          <div className="slash-brand">
            <span className="slash-logo">SI</span>
            <div>
              <h1>SLASH IMAGE</h1>
              <p className="slash-tagline">Remint · Finish · Ship. One clean pipeline.</p>
            </div>
          </div>
          <p className="slash-auth-intro">
            Sign in to run V8.9 and Quality Finish on your images. Professional
            creators only — every file is processed privately.
          </p>
          <input
            className="slash-input"
            type="email"
            placeholder="Email"
            value={authEmail}
            onChange={(e) => setAuthEmail(e.target.value)}
          />
          <input
            className="slash-input"
            type="password"
            placeholder="Password"
            value={authPassword}
            onChange={(e) => setAuthPassword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void submitAuth();
            }}
          />
          <button className="slash-btn slash-btn-primary" disabled={authBusy} onClick={() => void submitAuth()}>
            {authBusy ? <Loader2 size={16} className="slash-spin" /> : <ShieldCheck size={16} />}
            Sign in
          </button>
          {authStatus ? <p className="slash-auth-status">{authStatus}</p> : null}
        </div>
      </div>
    );
  }

  return (
    <div className="slash-root">
      <header className="slash-header">
        <div className="slash-header-inner">
          <div className="slash-brand">
            <span className="slash-logo">SI</span>
            <div>
              <h1>SLASH IMAGE</h1>
              <p className="slash-tagline">V8.9 → Quality Finish. The professional pipeline.</p>
            </div>
          </div>
          <div className="slash-header-right">
            <span className="slash-credits" title="DeepClean credits">
              <Sparkles size={14} />
              {credits === null ? "…" : credits} credits
            </span>
            <span className="slash-user">{userEmail}</span>
            <button className="slash-icon-btn" title="Sign out" onClick={() => void signOut()}>
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <main className="slash-main">
        <aside className="slash-sidebar">
          <section className="slash-section">
            <h3 className="slash-section-title">Pipeline</h3>
            <div className="slash-modes">
              {(Object.keys(MODE_META) as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`slash-mode${mode === m ? " is-active" : ""}`}
                  disabled={running}
                  onClick={() => setMode(m)}
                >
                  <span className="slash-mode-badge">{MODE_META[m].badge}</span>
                  <strong>{MODE_META[m].title}</strong>
                  <small>{MODE_META[m].blurb}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="slash-section">
            <button
              type="button"
              className="slash-expert-toggle"
              onClick={() => setExpertOpen((v) => !v)}
            >
              <SlidersHorizontal size={15} />
              Expert options
              <ChevronDown size={15} className={expertOpen ? "is-open" : ""} />
            </button>

            {expertOpen ? (
              <div className="slash-expert">
                {(mode === "sequence" || mode === "remint") && (
                  <>
                    <div className="slash-field">
                      <label className="slash-label">Wash model</label>
                      <div className="slash-seg">
                        {(["qwen", "zimage", "qwen+zimage"] as const).map((w) => (
                          <button
                            key={w}
                            type="button"
                            className={washModel === w ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setWashModel(w)}
                          >
                            {w === "qwen+zimage" ? "Qwen ⊕ Z" : w}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="slash-field">
                      <label className="slash-label">Camera strength</label>
                      <div className="slash-seg">
                        {(["light", "balanced", "deep"] as const).map((s) => (
                          <button
                            key={s}
                            type="button"
                            className={strength === s ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setStrength(s)}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="slash-field">
                      <label className="slash-label">Engine</label>
                      <div className="slash-seg">
                        {(["adaptive", "template"] as const).map((e) => (
                          <button
                            key={e}
                            type="button"
                            className={engineMode === e ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setEngineMode(e)}
                          >
                            {e}
                          </button>
                        ))}
                      </div>
                    </div>
                    <label className="slash-check">
                      <input
                        type="checkbox"
                        checked={iphoneExif}
                        disabled={running}
                        onChange={(e) => setIphoneExif(e.target.checked)}
                      />
                      Coherent device EXIF
                    </label>
                    <div className="slash-field">
                      <label className="slash-label">Metadata</label>
                      <div className="slash-seg">
                        {(["device", "minimal"] as const).map((m) => (
                          <button
                            key={m}
                            type="button"
                            className={metadataMode === m ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setMetadataMode(m)}
                          >
                            {m}
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                {(mode === "sequence" || mode === "finish") && (
                  <>
                    <div className="slash-field">
                      <label className="slash-label">Restoration preset</label>
                      <div className="slash-seg">
                        {(["conservative", "standard", "strong"] as const).map((p) => (
                          <button
                            key={p}
                            type="button"
                            className={finishPreset === p ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setFinishPreset(p)}
                          >
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="slash-field">
                      <label className="slash-label">Delivery size</label>
                      <div className="slash-seg">
                        {(["native", "1.6", "2"] as const).map((s) => (
                          <button
                            key={s}
                            type="button"
                            className={finishScale === s ? "is-active" : ""}
                            disabled={running}
                            onClick={() => setFinishScale(s)}
                          >
                            {s === "native" ? "native" : `${s}×`}
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                <div className="slash-field">
                  <label className="slash-label">File name</label>
                  <div className="slash-seg">
                    {(["photo-style", "original", "custom"] as const).map((n) => (
                      <button
                        key={n}
                        type="button"
                        className={nameStyle === n ? "is-active" : ""}
                        disabled={running}
                        onClick={() => setNameStyle(n)}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                {nameStyle === "custom" ? (
                  <input
                    className="slash-input"
                    placeholder="Custom prefix"
                    value={nameCustom}
                    disabled={running}
                    onChange={(e) => setNameCustom(e.target.value)}
                  />
                ) : null}
              </div>
            ) : null}
          </section>

          <section className="slash-section">
            <h3 className="slash-section-title">What runs</h3>
            <ol className="slash-steps">
              {meta.steps.map((step, i) => (
                <li key={step}>
                  <span className="slash-step-num">{i + 1}</span>
                  <span>{step}</span>
                  {i < meta.steps.length - 1 ? <ArrowRight size={12} className="slash-step-arrow" /> : null}
                </li>
              ))}
            </ol>
            <p className="slash-note">
              {mode === "sequence"
                ? "One job, two frozen stages. If the finisher's self-QC fails, your remint file ships untouched."
                : mode === "remint"
                  ? "The frozen, live-test-winning V8.9 pipeline. Single q92 encode."
                  : "Non-generative selective restoration. QC failure ships your original bytes."}
            </p>
          </section>
        </aside>

        <section className="slash-work">
          <div
            className={`slash-drop${dragging ? " is-dragging" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              addFiles(Array.from(e.dataTransfer.files));
            }}
            onClick={() => fileInput.current?.click()}
          >
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files) addFiles(Array.from(e.target.files));
                e.target.value = "";
              }}
            />
            <ImagePlus size={34} strokeWidth={1.5} />
            <h2>Drop images here</h2>
            <p>
              Up to 20 files · {mode === "sequence" ? "V8.9 remint → Quality Finish" : MODE_META[mode].title}
              {" "}· {COST[mode]} credits each
            </p>
            <span className="slash-btn slash-btn-ghost">
              <Upload size={15} /> Browse files
            </span>
          </div>

          {queue.length > 0 ? (
            <>
              <div className="slash-summary">
                <span>
                  {queue.length} {queue.length === 1 ? "image" : "images"}
                  {doneCount > 0 ? ` · ${doneCount} done` : ""}
                  {failedCount > 0 ? ` · ${failedCount} failed` : ""}
                </span>
                <div className="slash-summary-actions">
                  {queue.length > 1 && doneCount === 0 && failedCount === 0 ? (
                    <button className="slash-btn slash-btn-ghost" onClick={() => setQueue([])}>
                      <Trash2 size={14} /> Clear
                    </button>
                  ) : null}
                  <button className="slash-btn slash-btn-primary" disabled={!canRun} onClick={() => void runQueue()}>
                    {running ? <Loader2 size={15} className="slash-spin" /> : <Sparkles size={15} />}
                    {running
                      ? `Processing ${activeJobCount + 1} of ${queue.length}…`
                      : queue.some((q) => q.status === "failed")
                        ? "Retry failed"
                        : `Process ${queue.length}`}
                  </button>
                </div>
              </div>

              <ul className="slash-queue">
                {queue.map((item) => (
                  <li key={item.id} className={`slash-item is-${item.status}`}>
                    <div className="slash-item-thumb">
                      {item.status === "completed" && item.outputUrl ? (
                        <img src={item.outputUrl} alt={item.file.name} />
                      ) : (
                        <img src={item.preview} alt={item.file.name} />
                      )}
                    </div>
                    <div className="slash-item-body">
                      <div className="slash-item-name">{item.file.name}</div>
                      {item.status === "waiting" && <span className="slash-item-status">Waiting</span>}
                      {item.status === "preparing" && <span className="slash-item-status">Preparing…</span>}
                      {item.status === "uploading" && <span className="slash-item-status">Uploading…</span>}
                      {item.status === "queued" && <span className="slash-item-status">On the GPU…</span>}
                      {item.status === "processing" && (
                        <span className="slash-item-status">
                          <Loader2 size={12} className="slash-spin" /> Processing on GPU…
                        </span>
                      )}
                      {item.status === "completed" && (
                        <span className="slash-item-status is-done">
                          <Check size={12} /> {item.report ?? "Ready"}
                        </span>
                      )}
                      {item.status === "failed" && (
                        <span className="slash-item-status is-error">
                          <X size={12} /> {item.error ?? "Failed"}
                        </span>
                      )}
                    </div>
                    <div className="slash-item-actions">
                      {item.status === "completed" && item.outputUrl ? (
                        <a
                          className="slash-icon-btn"
                          href={item.outputUrl}
                          title="Download"
                          download={item.job?.outputName ?? item.file.name}
                        >
                          <Download size={16} />
                        </a>
                      ) : null}
                      {!running && item.status !== "processing" ? (
                        <button
                          className="slash-icon-btn"
                          title="Remove"
                          onClick={() => removeItem(item.id)}
                        >
                          <X size={16} />
                        </button>
                      ) : null}
                      {item.status === "failed" && running ? (
                        <RefreshCw size={14} className="slash-spin" />
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {statusLine ? <p className="slash-status-line">{statusLine}</p> : null}
        </section>
      </main>

      <footer className="slash-footer">
        <span>
          <Fingerprint size={12} /> Slash Image · V8.9 + Quality Finish · deterministic · private
        </span>
      </footer>
    </div>
  );
}

function summarizeReport(report: Record<string, unknown> | undefined, mode: Mode): string {
  if (!report) return "Ready";
  const requested = (report.requested_options ?? {}) as Record<string, unknown>;
  const layout = typeof requested.profile_layout === "string" ? requested.profile_layout : mode;
  const engine = (report.engine ?? {}) as Record<string, unknown>;
  const qf = (engine.quality_finish ?? {}) as Record<string, unknown>;
  const qc = (qf.qc ?? {}) as Record<string, unknown>;
  if (qf && qf.applied === true) {
    return `Finished · ${qf.preset ?? "standard"} · ${qf.scale ?? "native"}× · SSIM ${qc.ssim ?? "?"}`;
  }
  if (qf && qf.applied === false) {
    return "Reminted · finish QC tripped · original shipped";
  }
  return layout === "quality-finish" ? "Finished" : "Reminted";
}
