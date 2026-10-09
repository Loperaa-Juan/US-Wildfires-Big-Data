/** Round to 2 significant digits, so class limits read as 120 or 1.300, not 1.287. */
export function niceRound(value: number): number {
  if (value <= 0) return 0;
  const magnitude = 10 ** (Math.floor(Math.log10(value)) - 1);
  return Math.round(value / magnitude) * magnitude;
}

/**
 * Upper limits of `classes` quantile classes (classes - 1 limits; the last class is open).
 *
 * Fire counts per cell are very skewed (most cells have a few fires, a few have thousands),
 * so equal-width classes would paint almost every cell in the first color. Quantiles put
 * about the same number of cells in each class.
 */
export function quantileBreaks(values: number[], classes: number): number[] {
  if (values.length === 0) return [];
  const sorted = [...values].sort((a, b) => a - b);
  const breaks: number[] = [];
  for (let i = 1; i < classes; i++) {
    const limit = niceRound(sorted[Math.floor((i * sorted.length) / classes)]);
    if (limit > (breaks.at(-1) ?? 0)) breaks.push(limit);
  }
  return breaks;
}

/** Index of the class `value` falls in: 0 when value < breaks[0], ..., breaks.length. */
export function classify(value: number, breaks: number[]): number {
  const index = breaks.findIndex((limit) => value < limit);
  return index === -1 ? breaks.length : index;
}

/** Axis ticks: 0 and clean steps (1, 2 or 5 × 10^n) up to at least `max`. */
export function niceTicks(max: number, target = 4): number[] {
  if (max <= 0) return [0];
  const rough = max / target;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= rough) ?? 10 * power;
  const ticks: number[] = [];
  for (let t = 0; t < max + step; t += step) ticks.push(t);
  return ticks;
}
