// Quick-open matching (Ctrl+P): letters in order, rewarded for word starts, runs and the file name.

export interface FuzzyHit { item: string; score: number; marks: number[] }

export function fuzzyMatch(query: string, item: string): FuzzyHit | null {
  const q = query.toLowerCase().replace(/\s+/g, "");
  if (!q) return { item, score: 0, marks: [] };
  const s = item.toLowerCase();
  const nameStart = item.lastIndexOf("/") + 1;
  const marks: number[] = [];
  let score = 0, qi = 0, prev = -2;
  for (let i = 0; i < s.length && qi < q.length; i++) {
    if (s[i] !== q[qi]) continue;
    let bonus = 1;
    const before = i > 0 ? item[i - 1] : "/";
    if (before === "/" || before === "_" || before === "-" || before === "." || before === " ") bonus += 6;
    else if (item[i] >= "A" && item[i] <= "Z" && before >= "a" && before <= "z") bonus += 5;
    if (prev === i - 1) bonus += 4;
    if (i >= nameStart) bonus += 3;
    score += bonus;
    marks.push(i);
    prev = i;
    qi++;
  }
  if (qi < q.length) return null;
  score -= item.length * 0.02; // shorter paths first when equal
  return { item, score, marks };
}

export function fuzzyFilter(query: string, items: string[], limit = 80): FuzzyHit[] {
  const hits: FuzzyHit[] = [];
  for (const it of items) {
    const h = fuzzyMatch(query, it);
    if (h) hits.push(h);
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, limit);
}
