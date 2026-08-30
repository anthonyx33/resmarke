import original1 from "../round-remint-1-01/full-corpus/IMG-1_source.jpg";
import original2 from "../round-remint-1-01/full-corpus/IMG-2_source.jpg";
import original3 from "../round-remint-1-01/full-corpus/IMG-3_source.png";
import original4 from "../round-remint-1-01/full-corpus/IMG-4_source.png";
import original5 from "../round-remint-1-01/full-corpus/IMG-5_source.png";
import original6 from "../round-remint-1-01/full-corpus/IMG-6_source.png";
import original7 from "../round-remint-1-01/full-corpus/IMG-7_source.png";
import original8 from "../round-remint-1-01/full-corpus/IMG-8_source.png";
import original9 from "../round-remint-1-01/full-corpus/IMG-9_source.png";
import original10 from "../round-remint-1-01/full-corpus/IMG-10_source.png";
import original11 from "../round-remint-1-01/full-corpus/IMG-11_source.jpeg";
import delivered1 from "../round-remint-1-01/full-corpus/1.01_IMG-1_lab-ctla1.jpg";
import delivered2 from "../round-remint-1-01/full-corpus/1.01_IMG-2_lab-ctla1.jpg";
import delivered3 from "../round-remint-1-01/full-corpus/1.01_IMG-3_lab-ctla1.jpg";
import delivered4 from "../round-remint-1-01/full-corpus/1.01_IMG-4_lab-ctla1.jpg";
import delivered5 from "../round-remint-1-01/full-corpus/1.01_IMG-5_lab-ctla1.jpg";
import delivered6 from "../round-remint-1-01/full-corpus/1.01_IMG-6_lab-ctla1.jpg";
import delivered7 from "../round-remint-1-01/full-corpus/1.01_IMG-7_lab-ctla1.jpg";
import delivered8 from "../round-remint-1-01/full-corpus/1.01_IMG-8_lab-ctla1.jpg";
import delivered9 from "../round-remint-1-01/full-corpus/1.01_IMG-9_lab-ctla1.jpg";
import delivered10 from "../round-remint-1-01/full-corpus/1.01_IMG-10_lab-ctla1.jpg";
import delivered11 from "../round-remint-1-01/full-corpus/1.01_IMG-11_lab-ctla1.jpg";
import phaseBLedger from "../round-remint-1-01/full-corpus/ledger.jsonl?raw";
import {
  parseSlashBaseSeedLedger,
  type SlashBaseGrade,
  type SlashBaseSeedRow,
} from "./lib/slashbaseSeed";

export type SlashBaseCardSide = {
  fileName: string;
  imageUrl: string;
  grade: SlashBaseGrade;
  timestamp: string;
};

export type SlashBaseCard = {
  id: string;
  imageName: string;
  preset: "ReMint 1.01";
  sequenceCode: string;
  timestamp: string;
  original: SlashBaseCardSide;
  delivered: SlashBaseCardSide;
};

const imageAssets: Record<
  string,
  { original: string; delivered: string }
> = {
  "IMG-1": { original: original1, delivered: delivered1 },
  "IMG-2": { original: original2, delivered: delivered2 },
  "IMG-3": { original: original3, delivered: delivered3 },
  "IMG-4": { original: original4, delivered: delivered4 },
  "IMG-5": { original: original5, delivered: delivered5 },
  "IMG-6": { original: original6, delivered: delivered6 },
  "IMG-7": { original: original7, delivered: delivered7 },
  "IMG-8": { original: original8, delivered: delivered8 },
  "IMG-9": { original: original9, delivered: delivered9 },
  "IMG-10": { original: original10, delivered: delivered10 },
  "IMG-11": { original: original11, delivered: delivered11 },
};

export const slashBaseSeedRows = parseSlashBaseSeedLedger(phaseBLedger, {
  expectedRows: 22,
});

export const slashBaseCards = pairSeedRows(slashBaseSeedRows);

function pairSeedRows(rows: SlashBaseSeedRow[]): SlashBaseCard[] {
  const byImage = new Map<string, Partial<Record<"original" | "delivered", SlashBaseSeedRow>>>();
  for (const row of rows) {
    const pair = byImage.get(row.imageName) ?? {};
    pair[row.side] = row;
    byImage.set(row.imageName, pair);
  }

  return [...byImage.entries()].map(([imageName, pair]) => {
    if (!pair.original || !pair.delivered) {
      throw new Error(`SlashBase is missing a before/after pair for ${imageName}.`);
    }
    const assets = imageAssets[imageName];
    if (!assets) throw new Error(`SlashBase is missing image assets for ${imageName}.`);
    if (pair.original.sequenceCode !== pair.delivered.sequenceCode) {
      throw new Error(`SlashBase found mismatched SEQ codes for ${imageName}.`);
    }

    return {
      id: `${pair.delivered.preset}:${imageName}`,
      imageName,
      preset: pair.delivered.preset,
      sequenceCode: pair.delivered.sequenceCode,
      timestamp: pair.delivered.timestamp,
      original: {
        fileName: pair.original.fileName,
        imageUrl: assets.original,
        grade: pair.original.grade,
        timestamp: pair.original.timestamp,
      },
      delivered: {
        fileName: pair.delivered.fileName,
        imageUrl: assets.delivered,
        grade: pair.delivered.grade,
        timestamp: pair.delivered.timestamp,
      },
    };
  });
}
