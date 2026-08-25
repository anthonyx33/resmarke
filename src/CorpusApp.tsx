import {
  Archive,
  Check,
  ClipboardCopy,
  Database,
  Download,
  ExternalLink,
  FileJson,
  FlaskConical,
  Image as ImageIcon,
  KeyRound,
  Loader2,
  Lock,
  LogOut,
  Mail,
  Moon,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sun,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  addCorpusSetMember,
  archiveCorpusEntity,
  compactCorpusReport,
  createCorpusExperiment,
  createCorpusSet,
  exportCorpusJsonl,
  fetchCorpusSnapshot,
  lockCorpusSet,
  readCorpusHistory,
  reconcileCorpusGrades,
  removeCorpusSetMember,
  uploadCorpusFile,
  type CorpusExperiment,
  type CorpusImage,
  type CorpusRun,
  type CorpusSet,
  type CorpusSnapshot,
} from "./lib/corpusClient";
import { hasSupabaseConfig } from "./lib/config";
import { supabase } from "./lib/supabase";
import "./corpus.css";

type Theme = "light" | "dark";
type AuthMode = "signin" | "signup";
type UploadRow = { id: string; name: string; progress: number; status: "queued" | "uploading" | "stored" | "dedup" | "failed"; error?: string };

const EMPTY_CAPS: CorpusSnapshot["caps"] = {
  max_images: 200,
  max_outputs_per_image: 20,
  storage_byte_limit: null,
  used_bytes: 0,
  download_ttl_seconds: 120,
};

export default function CorpusApp() {
  const uploadInput = useRef<HTMLInputElement | null>(null);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [userId, setUserId] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authStatus, setAuthStatus] = useState("");
  const [snapshot, setSnapshot] = useState<CorpusSnapshot | null>(null);
  const [history, setHistory] = useState<CorpusRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [selectedImageId, setSelectedImageId] = useState("");
  const [selectedSetId, setSelectedSetId] = useState("");
  const [selectedExperimentId, setSelectedExperimentId] = useState("");
  const [setName, setSetName] = useState("Fixed corpus");
  const [setVersion, setSetVersion] = useState(1);
  const [engineRelease, setEngineRelease] = useState("");
  const [detectorVendor, setDetectorVendor] = useState("g1");
  const [detectorModel, setDetectorModel] = useState("ai_generated_media");
  const [detectorVersion, setDetectorVersion] = useState("");
  const [copyState, setCopyState] = useState("");

  const caps = snapshot?.caps ?? EMPTY_CAPS;
  const selectedSet = snapshot?.sets.find((set) => set.id === selectedSetId) ?? null;
  const selectedImage = snapshot?.images.find((image) => image.id === selectedImageId) ?? null;
  const selectedExperiment = snapshot?.experiments.find((experiment) => experiment.id === selectedExperimentId) ?? null;
  const setMembers = useMemo(
    () => (snapshot?.members ?? []).filter((member) => member.corpus_set_id === selectedSetId).sort((a, b) => a.position - b.position),
    [selectedSetId, snapshot?.members],
  );
  const selectedSetImageIds = useMemo(() => new Set(setMembers.map((member) => member.corpus_image_id)), [setMembers]);
  const filteredHistory = useMemo(
    () => history.filter((run) => (!selectedImageId || run.corpus_image_id === selectedImageId) && (!selectedExperimentId || run.experiment_id === selectedExperimentId)),
    [history, selectedExperimentId, selectedImageId],
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("resmarke:theme", theme);
  }, [theme]);

  useEffect(() => {
    document.title = "/CORPUS — Fixed Corpus Registry";
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => applySession(data.session?.user));
    const { data } = supabase.auth.onAuthStateChange((_event, session) => applySession(session?.user));
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!userId) return;
    void refresh();
  }, [userId]);

  useEffect(() => {
    if (!selectedImageId && !selectedExperimentId) {
      setHistory(snapshot?.runs ?? []);
      return;
    }
    void loadHistory();
  }, [selectedExperimentId, selectedImageId]);

  useEffect(() => {
    if (!copyState) return;
    const timer = window.setTimeout(() => setCopyState(""), 1400);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  function applySession(user?: { id: string; email?: string | null }) {
    setUserId(user?.id ?? "");
    setUserEmail(user?.email ?? "");
    if (!user) setSnapshot(null);
  }

  async function refresh() {
    setLoading(true);
    try {
      const next = await fetchCorpusSnapshot();
      setSnapshot(next);
      setHistory(next.runs);
      setSelectedSetId((current) => next.sets.some((set) => set.id === current) ? current : next.sets[0]?.id || "");
      setSelectedExperimentId((current) => next.experiments.some((experiment) => experiment.id === current) ? current : next.experiments[0]?.id || "");
      setSelectedImageId((current) => next.images.some((image) => image.id === current) ? current : next.images[0]?.id || "");
      setEngineRelease((current) => current || next.engine_releases[0] || "");
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load the corpus registry.");
    } finally {
      setLoading(false);
    }
  }

  async function loadHistory() {
    try {
      const result = await readCorpusHistory({
        corpusImageId: selectedImageId || undefined,
        experimentId: selectedExperimentId || undefined,
      });
      setHistory(result.runs);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load corpus history.");
    }
  }

  async function submitAuth() {
    if (!supabase) return;
    if (!authEmail.trim() || !authPassword) return setAuthStatus("Enter an email and password.");
    setAuthStatus(authMode === "signin" ? "Signing in…" : "Creating account…");
    const result = authMode === "signin"
      ? await supabase.auth.signInWithPassword({ email: authEmail.trim(), password: authPassword })
      : await supabase.auth.signUp({ email: authEmail.trim(), password: authPassword, options: { emailRedirectTo: window.location.href } });
    setAuthStatus(result.error ? result.error.message : authMode === "signin" ? "Signed in." : "Account created. Confirm by email if prompted.");
    if (!result.error) setAuthPassword("");
  }

  async function signOut() {
    await supabase?.auth.signOut();
    setUserId("");
    setUserEmail("");
  }

  async function uploadFiles(files: File[]) {
    const accepted = files.slice(0, 50).filter((file) => ["image/jpeg", "image/png", "image/webp"].includes(file.type) && file.size > 0 && file.size <= 25 * 1024 * 1024);
    const jobs = accepted.map((file, index) => ({ file, id: `${Date.now()}-${index}-${file.name}` }));
    setUploads(jobs.map(({ file, id }) => ({ id, name: file.name, progress: 0, status: "queued" })));
    let cursor = 0;
    const worker = async () => {
      while (cursor < jobs.length) {
        const job = jobs[cursor++];
        patchUpload(job.id, { status: "uploading" });
        try {
          const result = await uploadCorpusFile(job.file, (progress) => patchUpload(job.id, { progress }));
          patchUpload(job.id, { status: result.stored === false || result.duplicate ? "dedup" : "stored", progress: 1 });
        } catch (error) {
          patchUpload(job.id, { status: "failed", error: error instanceof Error ? error.message : "Upload failed." });
        }
      }
    };
    await Promise.all(Array.from({ length: Math.min(3, jobs.length) }, () => worker()));
    await refresh();
  }

  function patchUpload(id: string, patch: Partial<UploadRow>) {
    setUploads((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row));
  }

  async function runAction(key: string, action: () => Promise<unknown>, success: string) {
    setBusy(key);
    setNotice("");
    try {
      await action();
      setNotice(success);
      await refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Corpus action failed.");
    } finally {
      setBusy("");
    }
  }

  async function addSelectedImage(image: CorpusImage) {
    if (!selectedSet || selectedSet.locked_at) return;
    const nextPosition = Math.max(0, ...setMembers.map((member) => member.position)) + 1;
    await runAction(`add-${image.id}`, () => addCorpusSetMember(selectedSet.id, image.id, nextPosition), `${image.file_name} added to ${selectedSet.name} v${selectedSet.version}.`);
  }

  async function removeSelectedImage(image: CorpusImage) {
    if (!selectedSet || selectedSet.locked_at) return;
    await runAction(`remove-${image.id}`, () => removeCorpusSetMember(selectedSet.id, image.id), `${image.file_name} removed from the draft set.`);
  }

  async function copyText(value: string, key: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopyState(key);
    } catch {
      setNotice("Clipboard access was denied.");
    }
  }

  function downloadText(value: string, fileName: string) {
    const url = URL.createObjectURL(new Blob([value], { type: "application/x-ndjson" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (!hasSupabaseConfig) {
    return <div className="corpus"><div className="cp-gate"><Database size={30} /><h1>Corpus is not configured</h1><p>Set the existing Supabase browser environment values to open the admin console.</p></div></div>;
  }

  if (!userId) {
    return (
      <div className="corpus">
        <div className="cp-auth">
          <ShieldCheck size={30} />
          <h1>Corpus admin</h1>
          <p>Sign in with an allowlisted, verified owner account.</p>
          <div className="cp-segment"><button className={authMode === "signin" ? "is-active" : ""} onClick={() => setAuthMode("signin")}>Sign in</button><button className={authMode === "signup" ? "is-active" : ""} onClick={() => setAuthMode("signup")}>Sign up</button></div>
          <label><Mail size={14} /><input type="email" placeholder="owner@email.com" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} /></label>
          <label><KeyRound size={14} /><input type="password" placeholder="Password" value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void submitAuth(); }} /></label>
          <button className="cp-btn cp-primary" onClick={() => void submitAuth()}>{authMode === "signin" ? "Sign in" : "Create account"}</button>
          {authStatus ? <small>{authStatus}</small> : null}
        </div>
      </div>
    );
  }

  return (
    <div className="corpus">
      <input ref={uploadInput} hidden type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={(event) => { void uploadFiles(Array.from(event.target.files ?? [])); event.target.value = ""; }} />
      <header className="cp-topbar">
        <div className="cp-brand"><Database size={17} /><span><b>/CORPUS</b><small>Fixed registry · immutable evidence</small></span></div>
        <span className="cp-law"><Lock size={12} /> Mechanical L4</span>
        <span className="cp-spacer" />
        <a className="cp-btn" href="/relab"><FlaskConical size={13} /> Open /relab</a>
        <button className="cp-btn" onClick={() => void refresh()} disabled={loading}>{loading ? <Loader2 className="cp-spin" size={13} /> : <RefreshCw size={13} />} Refresh</button>
        <span className="cp-account"><UserRound size={13} /> {userEmail}</span>
        <button className="cp-icon" aria-label="Sign out" onClick={() => void signOut()}><LogOut size={14} /></button>
        <button className="cp-icon" aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}</button>
      </header>

      <div className="cp-status">{notice || (loading ? "Loading corpus registry…" : "Ready · admin-only read/write path")}</div>

      <section className="cp-metrics">
        <Metric label="Registry" value={`${snapshot?.images.length ?? 0}/${caps.max_images}`} detail="content-addressed originals" />
        <Metric label="Storage" value={formatBytes(caps.used_bytes)} detail={caps.storage_byte_limit ? `${formatBytes(caps.storage_byte_limit)} ceiling` : "owner ceiling required"} warn={!caps.storage_byte_limit} />
        <Metric label="Sets" value={String(snapshot?.sets.length ?? 0)} detail={`${snapshot?.sets.filter((set) => set.locked_at).length ?? 0} locked manifests`} />
        <Metric label="Experiments" value={String(snapshot?.experiments.length ?? 0)} detail="compatibility-isolated" />
        <Metric label="Runs" value={String(snapshot?.stats.total_runs ?? 0)} detail={`${snapshot?.stats.pending_runs ?? 0} grades pending`} />
      </section>

      <div className="cp-grid">
        <section className="cp-card cp-upload-card">
          <div className="cp-card-head"><div><Upload size={14} /><b>Upload corpus originals</b></div><span>50 files · concurrency 3</span></div>
          <button className="cp-drop" onClick={() => uploadInput.current?.click()}><Upload size={20} /><b>Select JPEG, PNG, or WebP</b><span>≤6 MB direct · larger files resumable TUS · 25 MB max</span></button>
          <div className="cp-upload-list">
            {uploads.map((row) => <div key={row.id} className={`cp-upload-row is-${row.status}`}><span><b>{row.name}</b><small>{row.error ?? uploadStatus(row.status)}</small></span><div><i style={{ width: `${row.progress * 100}%` }} /></div>{row.status === "uploading" ? <Loader2 className="cp-spin" size={13} /> : row.status === "failed" ? <X size={13} /> : row.status === "stored" || row.status === "dedup" ? <Check size={13} /> : null}</div>)}
            {!uploads.length ? <p>No uploads in this session.</p> : null}
          </div>
        </section>

        <section className="cp-card cp-sets-card">
          <div className="cp-card-head"><div><Lock size={14} /><b>Sets & experiments</b></div><span>versioned manifests</span></div>
          <div className="cp-form-row"><input value={setName} onChange={(event) => setSetName(event.target.value)} placeholder="Set name" /><input className="cp-number" type="number" min={1} value={setVersion} onChange={(event) => setSetVersion(Number(event.target.value))} /><button className="cp-btn cp-primary" disabled={!!busy} onClick={() => void runAction("create-set", () => createCorpusSet(setName, setVersion), "Draft corpus set created.")}><Plus size={13} /> Set</button></div>
          <label className="cp-field"><span>Active set</span><select value={selectedSetId} onChange={(event) => setSelectedSetId(event.target.value)}><option value="">Select a set</option>{snapshot?.sets.map((set) => <option key={set.id} value={set.id}>{set.name} v{set.version} · {set.locked_at ? "LOCKED" : "DRAFT"}</option>)}</select></label>
          {selectedSet ? <div className="cp-set-summary"><span><b>{setMembers.length}</b><small>ordered members</small></span><span><b>{selectedSet.locked_at ? "LOCKED" : "DRAFT"}</b><small>{selectedSet.manifest_sha256 ? shortHash(selectedSet.manifest_sha256) : "no manifest yet"}</small></span>{!selectedSet.locked_at ? <button className="cp-btn cp-danger" disabled={!setMembers.length || !!busy} onClick={() => { if (window.confirm("Lock this corpus set permanently? Membership cannot change after locking.")) void runAction("lock", () => lockCorpusSet(selectedSet.id), "Corpus set locked; immutable manifest created."); }}><Lock size={13} /> Lock permanently</button> : null}<button className="cp-icon" title="Archive set" disabled={!!busy} onClick={() => { if (window.confirm(`Archive ${selectedSet.name} v${selectedSet.version}?`)) void runAction("archive-set", () => archiveCorpusEntity("set", selectedSet.id), "Corpus set archived."); }}><Archive size={12} /></button></div> : null}
          <div className="cp-divider" />
          <label className="cp-field"><span>Locked set for experiment</span><select value={selectedSet?.locked_at ? selectedSetId : ""} onChange={(event) => setSelectedSetId(event.target.value)}><option value="">Select locked set</option>{snapshot?.sets.filter((set) => set.locked_at).map((set) => <option key={set.id} value={set.id}>{set.name} v{set.version}</option>)}</select></label>
          <label className="cp-field"><span>Exact engine release</span><input list="engine-releases" value={engineRelease} onChange={(event) => setEngineRelease(event.target.value)} placeholder="Worker engine_version" /><datalist id="engine-releases">{snapshot?.engine_releases.map((release) => <option key={release} value={release} />)}</datalist></label>
          <div className="cp-form-row"><input value={detectorVendor} onChange={(event) => setDetectorVendor(event.target.value)} placeholder="Detector vendor" title="mock for MOCK grades · g1 for real G1 grades" /><input value={detectorModel} onChange={(event) => setDetectorModel(event.target.value)} placeholder="Detector model" /><input value={detectorVersion} onChange={(event) => setDetectorVersion(event.target.value)} placeholder="Detector version (optional)" /></div>
          <button className="cp-btn cp-primary" disabled={!selectedSet?.locked_at || !engineRelease.trim() || !!busy} onClick={() => void runAction("experiment", () => createCorpusExperiment({ corpusSetId: selectedSet!.id, engineRelease: engineRelease.trim(), detectorVendor: detectorVendor.trim() || "g1", detectorMode: "real", detectorModel: detectorModel.trim() || undefined, detectorVersion: detectorVersion.trim() || undefined, configSet: ["A", "1A", "2B"] }), "Comparable experiment created.")}><FlaskConical size={13} /> Create experiment</button>
          <label className="cp-field"><span>History experiment</span><select value={selectedExperimentId} onChange={(event) => setSelectedExperimentId(event.target.value)}><option value="">All experiments</option>{snapshot?.experiments.map((experiment) => <option key={experiment.id} value={experiment.id}>{experiment.engine_release} · {experiment.detector_vendor}/{experiment.detector_mode}</option>)}</select></label>
          {selectedExperiment ? <button className="cp-btn cp-small" disabled={!!busy} onClick={() => { if (window.confirm("Archive this experiment? Its durable history remains stored.")) void runAction("archive-experiment", () => archiveCorpusEntity("experiment", selectedExperiment.id), "Experiment archived."); }}><Archive size={12} /> Archive experiment</button> : null}
        </section>
      </div>

      <section className="cp-card cp-registry">
        <div className="cp-card-head"><div><ImageIcon size={14} /><b>Registry</b></div><span>{snapshot?.images.length ?? 0} originals · SHA-256 dedup</span></div>
        <div className="cp-table-wrap"><table><thead><tr><th>Original</th><th>SHA-256</th><th>Dimensions</th><th>Bytes</th><th>Uploaded</th><th>Runs</th><th>{selectedSet?.locked_at ? "Membership" : "Draft set"}</th><th>Lifecycle</th></tr></thead><tbody>
          {snapshot?.images.map((image) => <tr key={image.id} className={selectedImageId === image.id ? "is-selected" : ""} onClick={() => setSelectedImageId(image.id)}><td><div className="cp-image-cell">{image.signed_url ? <img src={image.signed_url} alt="" /> : <span />}<b>{image.file_name}</b></div></td><td><code title={image.sha256}>{shortHash(image.sha256)}</code></td><td>{image.width}×{image.height}</td><td>{formatBytes(image.byte_size)}</td><td>{new Date(image.created_at).toLocaleDateString()}</td><td>{image.run_count}/{caps.max_outputs_per_image}</td><td>{selectedSet ? selectedSetImageIds.has(image.id) ? (!selectedSet.locked_at ? <button className="cp-btn cp-small" disabled={!!busy} onClick={(event) => { event.stopPropagation(); void removeSelectedImage(image); }}><X size={12} /> Remove</button> : <span className="cp-badge is-locked">IN MANIFEST</span>) : (!selectedSet.locked_at ? <button className="cp-btn cp-small" disabled={!!busy} onClick={(event) => { event.stopPropagation(); void addSelectedImage(image); }}><Plus size={12} /> Add</button> : "—") : "Select a set"}</td><td><button className="cp-icon" title="Archive image" disabled={!!busy} onClick={(event) => { event.stopPropagation(); if (window.confirm(`Archive ${image.file_name}?`)) void runAction(`archive-${image.id}`, () => archiveCorpusEntity("image", image.id), "Image archived."); }}><Archive size={13} /></button></td></tr>)}
          {!snapshot?.images.length ? <tr><td colSpan={8} className="cp-empty">Upload fixed-corpus originals to begin.</td></tr> : null}
        </tbody></table></div>
      </section>

      <section className="cp-card cp-history">
        <div className="cp-card-head"><div><Database size={14} /><b>Run history</b></div><span>{selectedImage?.file_name ?? "all images"} · {selectedExperiment ? `${selectedExperiment.detector_vendor}/${selectedExperiment.detector_mode}` : "all experiments"}</span><span className="cp-spacer" /><button className="cp-btn cp-small" disabled={!selectedExperimentId || !!busy} onClick={() => void runAction("reconcile", async () => { const result = await reconcileCorpusGrades({ experimentId: selectedExperimentId }); setNotice(`Reconcile complete: ${result.completed} completed, ${result.still_pending} pending · zero vendor calls.`); }, "Grades reconciled without vendor spend.")}><RefreshCw size={12} /> Reconcile</button><button className="cp-btn cp-small" disabled={!filteredHistory.length} onClick={() => downloadText(exportCorpusJsonl(filteredHistory), "corpus-runs.jsonl")}><FileJson size={12} /> JSONL</button><button className="cp-btn cp-small" disabled={!filteredHistory.length} onClick={() => void copyText(compactCorpusReport(filteredHistory), "compact")}>{copyState === "compact" ? <Check size={12} /> : <ClipboardCopy size={12} />} Compact</button></div>
        <div className="cp-table-wrap"><table><thead><tr><th>Timestamp</th><th>Config</th><th>Settings code</th><th>OG AI%</th><th>Remint AI%</th><th>Δ</th><th>Top sources</th><th>Swap / retain</th><th>Verdict</th><th>QA</th><th>Copy</th></tr></thead><tbody>
          {filteredHistory.map((run) => <tr key={run.id}><td>{new Date(run.created_at).toLocaleString()}</td><td><b>{run.config_label}</b><small>{run.config_key}</small></td><td><code>{run.requested_settings_code}</code></td><td>{run.og_grade ? percent(run.og_grade.ai_probability) : "PENDING"}</td><td>{run.remint_grade ? percent(run.remint_grade.ai_probability) : "PENDING"}</td><td className={(run.delta ?? 0) >= 0 ? "is-good" : "is-bad"}>{run.delta == null ? "—" : signedPercent(run.delta)}</td><td>{run.og_grade?.top_source ?? "—"} → {run.remint_grade?.top_source ?? "—"}</td><td>{run.swap_index == null ? "—" : `${percent(run.swap_index)} / ${percent(run.retention_index ?? 0)}`}</td><td><span className={`cp-badge is-${(run.remint_grade?.verdict ?? run.grade_status).toLowerCase()}`}>{run.remint_grade?.verdict ?? run.grade_status}</span></td><td>{run.qa_flag ? <span className="cp-flag">FLAG</span> : "—"}</td><td><button className="cp-icon" onClick={() => void copyText(compactCorpusReport([run]), run.id)}>{copyState === run.id ? <Check size={12} /> : <ClipboardCopy size={12} />}</button>{run.output_url ? <a className="cp-icon" href={run.output_url} target="_blank" rel="noreferrer"><ExternalLink size={12} /></a> : null}</td></tr>)}
          {!filteredHistory.length ? <tr><td colSpan={11} className="cp-empty">No matching registered runs.</td></tr> : null}
        </tbody></table></div>
      </section>

      <section className="cp-card cp-leaderboard">
        <div className="cp-card-head"><div><ShieldCheck size={14} /><b>Deterministic leaderboard</b></div><span>best run per image × config × compatibility key · sanitized view</span><span className="cp-spacer" /><button className="cp-btn cp-small" disabled={!snapshot?.leaderboard.length} onClick={() => downloadText((snapshot?.leaderboard ?? []).map((row) => JSON.stringify(row)).join("\n") + "\n", "corpus-leaderboard.jsonl")}><Download size={12} /> Export</button></div>
        <div className="cp-table-wrap"><table><thead><tr><th>#</th><th>Image</th><th>Config</th><th>Engine / detector</th><th>OG → Remint</th><th>Δ</th><th>Verdict</th><th>Swap / retain</th><th>QA</th><th>Runtime</th></tr></thead><tbody>
          {snapshot?.leaderboard.map((row, index) => <tr key={row.corpus_run_id}><td>{index + 1}</td><td><b>{row.file_name}</b><small>{shortHash(row.corpus_image_id)}</small></td><td><b>{row.config_label}</b><code>{row.requested_settings_code}</code></td><td><small>{row.engine_release}</small><b>{row.detector_vendor}/{row.detector_mode}{row.mock ? " · MOCK" : ""}</b></td><td>{row.og_ai == null ? "—" : percent(row.og_ai)} → {row.remint_ai == null ? "—" : percent(row.remint_ai)}</td><td className={(row.delta ?? 0) >= 0 ? "is-good" : "is-bad"}>{row.delta == null ? "—" : signedPercent(row.delta)}</td><td><span className={`cp-badge is-${(row.remint_verdict ?? row.grade_status).toLowerCase()}`}>{row.remint_verdict ?? row.grade_status}</span></td><td>{row.swap_index == null ? "—" : `${percent(row.swap_index)} / ${percent(row.retention_index ?? 0)}`}</td><td>{row.qa_flag ? <span className="cp-flag">FLAG</span> : "—"}</td><td>{row.runtime_ms == null ? "—" : `${(row.runtime_ms / 1000).toFixed(1)}s`}</td></tr>)}
          {!snapshot?.leaderboard.length ? <tr><td colSpan={10} className="cp-empty">Completed registered grades will produce ranked cells.</td></tr> : null}
        </tbody></table></div>
      </section>
    </div>
  );
}

function Metric({ label, value, detail, warn = false }: { label: string; value: string; detail: string; warn?: boolean }) {
  return <div className={`cp-metric${warn ? " is-warn" : ""}`}><small>{label}</small><b>{value}</b><span>{detail}</span></div>;
}

function initialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const saved = localStorage.getItem("resmarke:theme");
  return saved === "light" || saved === "dark" ? saved : "dark";
}

function uploadStatus(status: UploadRow["status"]): string {
  return { queued: "Queued", uploading: "Uploading and verifying…", stored: "Stored and registered", dedup: "Deduplicated · existing original reused", failed: "Failed" }[status];
}

function shortHash(value: string): string {
  return value.length > 16 ? `${value.slice(0, 12)}…${value.slice(-4)}` : value;
}

function formatBytes(value: number): string {
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024).toFixed(1)} KB`;
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function signedPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}
