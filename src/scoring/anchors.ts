/**
 * Anchored normalisation (MEASUREMENT §3): a raw metric value mapped piecewise-linearly through declared anchor
 * points, extended above the top anchor with the last segment's slope and never capped, floored at 0. An anchor a
 * trial exceeds stays as it is; the value goes above its mapped point and is flagged as extrapolated.
 */

export interface AnchorPoint {
  /** The anchor's name: naive, baseline, strong, bound, or a human reference such as median-contestant. */
  name: string;
  /** The normalised value the anchor maps to (default naive 0, baseline 0.5, strong 1). */
  maps: number;
  /** The anchor's raw value for this task. */
  value: number;
}

export interface Normalised {
  value: number;
  /** The raw value lies beyond the highest anchor, so the mapping is an extrapolation of its last segment. */
  extrapolated: boolean;
}

/** Anchors ordered by how good they are; raw values must strictly improve along that order. */
export function orderedAnchors(points: AnchorPoint[], direction: "higher" | "lower"): AnchorPoint[] {
  if (points.length < 2) throw new Error("ANCHORS_TOO_FEW");
  const ordered = [...points].sort((left, right) => left.maps - right.maps);
  for (let index = 1; index < ordered.length; index++) {
    const previous = ordered[index - 1]!;
    const current = ordered[index]!;
    if (current.maps <= previous.maps) throw new Error("ANCHORS_MAPS_NOT_INCREASING");
    const better = direction === "higher" ? current.value > previous.value : current.value < previous.value;
    if (!better) throw new Error("ANCHORS_VALUES_NOT_ORDERED");
  }
  for (const point of ordered) if (!Number.isFinite(point.value) || !Number.isFinite(point.maps)) throw new Error("ANCHORS_NOT_FINITE");
  return ordered;
}

/**
 * Maps a raw value through the anchors. Below the lowest anchor the first segment's slope continues down to the floor
 * of 0; above the highest the last segment's slope continues upwards without a cap.
 */
export function normalise(raw: number, points: AnchorPoint[], direction: "higher" | "lower"): Normalised {
  if (!Number.isFinite(raw)) throw new Error("METRIC_NOT_FINITE");
  const ordered = orderedAnchors(points, direction);
  // Work in "goodness" units, so that a lower-is-better metric reads like a higher-is-better one.
  const good = (value: number) => direction === "higher" ? value : -value;
  const x = good(raw);
  const xs = ordered.map(point => good(point.value));
  const ys = ordered.map(point => point.maps);
  const segment = (index: number) => (x - xs[index]!) / (xs[index + 1]! - xs[index]!) * (ys[index + 1]! - ys[index]!) + ys[index]!;
  if (x <= xs[0]!) return { value: Math.max(0, segment(0)), extrapolated: false };
  const top = xs.length - 1;
  if (x > xs[top]!) return { value: Math.max(0, segment(top - 1)), extrapolated: true };
  for (let index = 0; index < top; index++) {
    if (x <= xs[index + 1]!) return { value: Math.max(0, segment(index)), extrapolated: false };
  }
  return { value: ys[top]!, extrapolated: false };
}
