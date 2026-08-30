import { LoaderCircle, Maximize2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  gradeSlashBaseImage,
  loadSlashBaseGradeRows,
  slashBaseFileId,
} from "./lib/slashbaseClient";
import {
  SLASHBASE_PRESETS,
  type SlashBaseGrade,
  type SlashBasePreset,
} from "./lib/slashbaseSeed";
import {
  slashBaseCards,
  slashBaseSeedRows,
  type SlashBaseCard,
  type SlashBaseCardSide,
} from "./slashbaseData";
import type { DetectionOnlyLedgerRow, NormalizedGrade } from "./lib/gradeLedger";
import "./slashbase.css";

type DisplayGrade = Pick<
  SlashBaseGrade | NormalizedGrade,
  "ai_probability" | "deepfake_probability" | "verdict"
>;

export default function SlashBaseApp() {
  const [preset, setPreset] = useState<SlashBasePreset>("ReMint 1.01");
  const [savedGrades, setSavedGrades] = useState<DetectionOnlyLedgerRow[]>(
    loadSlashBaseGradeRows,
  );
  const [openCardId, setOpenCardId] = useState("");
  const [gradingCardId, setGradingCardId] = useState("");
  const [cardNotice, setCardNotice] = useState<Record<string, string>>({});

  const cards = preset === "ReMint 1.01" ? slashBaseCards : [];
  const latestGrades = useMemo(() => {
    const latest = new Map<string, DetectionOnlyLedgerRow>();
    for (const row of savedGrades) latest.set(row.file_id, row);
    return latest;
  }, [savedGrades]);
  const activeCard = slashBaseCards.find((card) => card.id === openCardId) ?? null;
  const gradeTimes = [
    ...slashBaseSeedRows.map((row) => row.timestamp),
    ...savedGrades.map((row) => row.timestamp),
  ];
  const lastGradeTime = gradeTimes.reduce(
    (latest, timestamp) => (Date.parse(timestamp) > Date.parse(latest) ? timestamp : latest),
    gradeTimes[0],
  );

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "SlashBase — Real Results";
    document.body.classList.add("slashbase-body");
    return () => {
      document.title = previousTitle;
      document.body.classList.remove("slashbase-body");
    };
  }, []);

  useEffect(() => {
    if (!activeCard) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenCardId("");
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [activeCard]);

  async function gradeCard(card: SlashBaseCard) {
    if (gradingCardId) return;
    setGradingCardId(card.id);
    setCardNotice((current) => ({ ...current, [card.id]: "" }));
    try {
      const row = await gradeSlashBaseImage({
        imageName: card.imageName,
        imageUrl: card.delivered.imageUrl,
        fileName: card.delivered.fileName,
        preset: card.preset,
        sequenceCode: card.sequenceCode,
      });
      setSavedGrades((current) => [...current, row]);
      setCardNotice((current) => ({ ...current, [card.id]: "New real score saved." }));
    } catch {
      setCardNotice((current) => ({
        ...current,
        [card.id]: "The grade could not be completed. Please try again.",
      }));
    } finally {
      setGradingCardId("");
    }
  }

  function deliveredGrade(card: SlashBaseCard): DisplayGrade {
    return (
      latestGrades.get(
        slashBaseFileId({ imageName: card.imageName, preset: card.preset }),
      )?.grade ?? card.delivered.grade
    );
  }

  return (
    <div className="sb-page" id="top">
      <header className="sb-hero">
        <nav className="sb-nav" aria-label="SlashBase">
          <a className="sb-logo" href="/slashbase" aria-label="SlashBase home">
            <span aria-hidden="true">/</span>SLASHBASE
          </a>
          <p>REAL RESULTS</p>
        </nav>

        <div className="sb-title-block">
          <p className="sb-kicker">THE BEFORE → AFTER FEED</p>
          <h1>
            See the image.
            <br />
            See the score.
          </h1>
          <p className="sb-intro">Every image. Before and after. Only real detection results.</p>
        </div>

        <dl className="sb-stats" aria-label="SlashBase totals">
          <div>
            <dt>Total real grades</dt>
            <dd>{slashBaseSeedRows.length + savedGrades.length}</dd>
          </div>
          <div>
            <dt>Images covered</dt>
            <dd>{new Set(slashBaseSeedRows.map((row) => row.imageName)).size}</dd>
          </div>
          <div>
            <dt>Last grade</dt>
            <dd className="sb-stat-date">{formatDateTime(lastGradeTime)}</dd>
          </div>
        </dl>
      </header>

      <main className="sb-main">
        <div className="sb-filter-wrap">
          <p>Preset</p>
          <div className="sb-filters" role="tablist" aria-label="Filter by preset">
            {SLASHBASE_PRESETS.map((option) => (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={preset === option}
                className={preset === option ? "is-active" : ""}
                onClick={() => setPreset(option)}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        {cards.length ? (
          <div className="sb-feed">
            {cards.map((card) => {
              const currentDeliveredGrade = deliveredGrade(card);
              return (
                <article className="sb-card" key={card.id}>
                  <header className="sb-card-header">
                    <h2>{card.imageName}</h2>
                    <div className="sb-card-meta">
                      <span>{card.preset}</span>
                      <code>{card.sequenceCode}</code>
                      <time dateTime={card.timestamp}>{formatDate(card.timestamp)}</time>
                    </div>
                  </header>

                  <div className="sb-compare">
                    <ImageSide
                      label="Original"
                      side={card.original}
                      grade={card.original.grade}
                      onOpen={() => setOpenCardId(card.id)}
                    />
                    <ImageSide
                      label="Delivered"
                      side={card.delivered}
                      grade={currentDeliveredGrade}
                      onOpen={() => setOpenCardId(card.id)}
                    />
                  </div>

                  <div className="sb-card-action">
                    <p aria-live="polite">{cardNotice[card.id] ?? ""}</p>
                    <button
                      type="button"
                      onClick={() => void gradeCard(card)}
                      disabled={Boolean(gradingCardId)}
                    >
                      {gradingCardId === card.id ? (
                        <>
                          <LoaderCircle aria-hidden="true" /> Grading…
                        </>
                      ) : (
                        "Grade"
                      )}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <section className="sb-empty" role="tabpanel">
            <span aria-hidden="true">/</span>
            <h2>Nothing graded here yet.</h2>
            <p>Real results will appear as soon as they are ready.</p>
          </section>
        )}
      </main>

      <footer className="sb-footer">
        <p>Lower AI % is clearer.</p>
        <a href="#top" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
          Back to top ↑
        </a>
      </footer>

      {activeCard ? (
        <div
          className="sb-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={`${activeCard.imageName} comparison`}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setOpenCardId("");
          }}
        >
          <div className="sb-lightbox-inner">
            <header>
              <div>
                <p>{activeCard.preset}</p>
                <h2>{activeCard.imageName}</h2>
              </div>
              <button type="button" onClick={() => setOpenCardId("")} aria-label="Close">
                <X aria-hidden="true" />
              </button>
            </header>
            <div className="sb-lightbox-grid">
              <LightboxSide
                label="Original"
                side={activeCard.original}
                grade={activeCard.original.grade}
              />
              <LightboxSide
                label="Delivered"
                side={activeCard.delivered}
                grade={deliveredGrade(activeCard)}
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ImageSide({
  label,
  side,
  grade,
  onOpen,
}: {
  label: string;
  side: SlashBaseCardSide;
  grade: DisplayGrade;
  onOpen: () => void;
}) {
  return (
    <section className="sb-side">
      <button
        className="sb-image-button"
        type="button"
        onClick={onOpen}
        aria-label={`Enlarge ${label.toLowerCase()} image`}
      >
        <img src={side.imageUrl} alt={`${label} ${side.fileName}`} loading="lazy" />
        <span className="sb-side-label">{label}</span>
        <span className="sb-expand"><Maximize2 aria-hidden="true" /></span>
      </button>
      <Score grade={grade} />
    </section>
  );
}

function LightboxSide({
  label,
  side,
  grade,
}: {
  label: string;
  side: SlashBaseCardSide;
  grade: DisplayGrade;
}) {
  return (
    <section>
      <div className="sb-lightbox-image">
        <img src={side.imageUrl} alt={`${label} ${side.fileName}`} />
        <span>{label}</span>
      </div>
      <Score grade={grade} compact />
    </section>
  );
}

function Score({ grade, compact = false }: { grade: DisplayGrade; compact?: boolean }) {
  return (
    <div className={`sb-score${compact ? " is-compact" : ""}`}>
      <div>
        <strong>{formatPercent(grade.ai_probability)}</strong>
        <span>AI</span>
      </div>
      <span className={`sb-verdict is-${grade.verdict.toLowerCase()}`}>
        {grade.verdict}
      </span>
      <p>Deepfake {formatPercent(grade.deepfake_probability)}</p>
    </div>
  );
}

function formatPercent(probability: number): string {
  const value = (probability * 100).toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  return `${value}%`;
}

function formatDate(timestamp: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(timestamp));
}

function formatDateTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}
