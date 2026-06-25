import { fnv1a32, xorshift32 } from "./hash";

export type FibonacciMarkOptions = {
  creatorId: string;
  strength: number;
  repetitions?: number;
};

const PAYLOAD_BITS = 88;
const BLOCK_SIZE = 8;

function payloadBits(creatorId: string): number[] {
  const normalized = creatorId.trim().toLowerCase() || "anonymous";
  const day = Math.floor(Date.now() / 86_400_000);
  const seeds = [
    fnv1a32(`creator:${normalized}`),
    fnv1a32(`seal:${normalized}:${day}`),
    fnv1a32(`resmarke:${normalized}`)
  ];

  const bits: number[] = [];
  for (const seed of seeds) {
    for (let bit = 0; bit < 32 && bits.length < PAYLOAD_BITS; bit += 1) {
      bits.push((seed >>> bit) & 1);
    }
  }
  return bits;
}

function uniqueFibonacciBlocks(
  width: number,
  height: number,
  count: number,
  seed: number
): number[] {
  const blocksX = Math.max(1, Math.floor(width / BLOCK_SIZE));
  const blocksY = Math.max(1, Math.floor(height / BLOCK_SIZE));
  const totalBlocks = blocksX * blocksY;
  const used = new Set<number>();
  const blocks: number[] = [];
  const random = xorshift32(seed);

  let fibA = 1 + (seed % 13);
  let fibB = 1 + ((seed >>> 4) % 17);

  while (blocks.length < count && used.size < totalBlocks) {
    const next = (fibA + fibB + random()) >>> 0;
    fibA = fibB;
    fibB = next;

    const block = next % totalBlocks;
    if (!used.has(block)) {
      used.add(block);
      blocks.push(block);
    }
  }

  return blocks;
}

export function applyFibonacci88Mark(
  imageData: ImageData,
  options: FibonacciMarkOptions
): ImageData {
  const { width, height, data } = imageData;
  const strength = Math.max(1, Math.min(8, Math.round(options.strength)));
  const repetitions = options.repetitions ?? 9;
  const payload = payloadBits(options.creatorId);
  const seed = fnv1a32(`${options.creatorId}:fibonacci-88`);
  const blocks = uniqueFibonacciBlocks(width, height, PAYLOAD_BITS * repetitions, seed);
  const blocksX = Math.max(1, Math.floor(width / BLOCK_SIZE));

  for (let index = 0; index < blocks.length; index += 1) {
    const bit = payload[index % PAYLOAD_BITS];
    const block = blocks[index];
    const blockX = block % blocksX;
    const blockY = Math.floor(block / blocksX);
    const startX = blockX * BLOCK_SIZE;
    const startY = blockY * BLOCK_SIZE;
    const direction = bit === 1 ? 1 : -1;

    for (let y = startY; y < Math.min(startY + BLOCK_SIZE, height); y += 1) {
      for (let x = startX; x < Math.min(startX + BLOCK_SIZE, width); x += 1) {
        const offset = (y * width + x) * 4;
        const checker = (x + y + index) % 2 === 0 ? 1 : -1;
        const delta = direction * checker * strength;

        data[offset + 1] = clampByte(data[offset + 1] - delta);
        data[offset + 2] = clampByte(data[offset + 2] + delta);
      }
    }
  }

  return imageData;
}

function clampByte(value: number): number {
  return Math.max(0, Math.min(255, Math.round(value)));
}
