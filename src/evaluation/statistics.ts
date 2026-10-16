/** Small, dependency-free estimators used by evaluation reports. */

/** 95% Wilson score interval for a binomial proportion; null when there are no trials. */
export function wilsonInterval(successes: number, trials: number, z = 1.959964): [number, number] | null {
  if (trials === 0) return null;
  const p = successes / trials;
  const denominator = 1 + z * z / trials;
  const centre = (p + z * z / (2 * trials)) / denominator;
  const half = (z * Math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))) / denominator;
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

function choose(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  let result = 1;
  for (let index = 1; index <= k; index++) result = result * (n - k + index) / index;
  return result;
}

/** Unbiased pass@k: probability that at least one of k draws (without replacement) from n trials with c successes passes. */
export function passAtK(trials: number, successes: number, k: number): number | null {
  if (k < 1 || trials < k) return null;
  return 1 - choose(trials - successes, k) / choose(trials, k);
}

/** Unbiased pass^k (tau-bench): probability that all k draws from n trials with c successes pass. */
export function passHatK(trials: number, successes: number, k: number): number | null {
  if (k < 1 || trials < k) return null;
  return choose(successes, k) / choose(trials, k);
}

// Two-sided 97.5% Student t quantiles for 1-30 degrees of freedom.
const tQuantiles = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
  2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042];

/**
 * Mean of paired per-task differences with a 95% t interval. Each task contributes one
 * difference, so the interval reflects task-level (clustered) variation, not trial counts.
 */
export function pairedDifference(differences: number[]): { tasks: number; mean: number | null; interval: [number, number] | null } {
  const n = differences.length;
  if (n === 0) return { tasks: 0, mean: null, interval: null };
  const mean = differences.reduce((sum, value) => sum + value, 0) / n;
  if (n < 2) return { tasks: n, mean, interval: null };
  const variance = differences.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (n - 1);
  const half = (tQuantiles[n - 2] ?? 1.959964) * Math.sqrt(variance / n);
  // A difference of two rates lies in [-1, 1]; clipping to that range keeps the interval's coverage.
  return { tasks: n, mean, interval: [Math.max(-1, mean - half), Math.min(1, mean + half)] };
}

/**
 * Mean of partial-credit scores in [0, 1] with a conservative 95% interval: the Wilson interval of the score sum.
 * A variable in [0, 1] with mean mu has variance at most mu(1 - mu), the binomial case, so the interval stays honest
 * when a few trials happen to agree. A t interval over three identical scores would claim zero width.
 */
export function meanInterval(values: number[]): { mean: number | null; interval: [number, number] | null } {
  const n = values.length;
  if (n === 0) return { mean: null, interval: null };
  const sum = values.reduce((total, value) => total + value, 0);
  return { mean: sum / n, interval: wilsonInterval(sum, n) };
}

/** Deterministic 32-bit PRNG (mulberry32) for reproducible trial ordering. */
export function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4_294_967_296;
  };
}

export function shuffled<T>(items: readonly T[], random: () => number): T[] {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index--) {
    const swap = Math.floor(random() * (index + 1));
    [copy[index], copy[swap]] = [copy[swap]!, copy[index]!];
  }
  return copy;
}
