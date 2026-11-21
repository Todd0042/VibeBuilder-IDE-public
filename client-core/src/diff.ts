// A line diff in the browser, for "Compare" when a file changed on disk while you were editing it
// (both texts are local, so there's nothing to ask the server). Same hunk shape the server sends.
import type { DiffLine, Hunk } from "./types";

/** Myers' O(ND) diff over lines; returns the edit script as equal/delete/insert runs. */
function myers(a: string[], b: string[]): Array<["=" | "-" | "+", number, number]> {
  const n = a.length, m = b.length, max = n + m;
  const v = new Int32Array(2 * max + 2);
  const trace: Int32Array[] = [];
  outer: for (let d = 0; d <= max; d++) {
    trace.push(v.slice());
    for (let k = -d; k <= d; k += 2) {
      let x = k === -d || (k !== d && v[max + k - 1] < v[max + k + 1]) ? v[max + k + 1] : v[max + k - 1] + 1;
      let y = x - k;
      while (x < n && y < m && a[x] === b[y]) { x++; y++; }
      v[max + k] = x;
      if (x >= n && y >= m) break outer;
    }
    if (d > 20000) break; // pathological input: give up on minimality
  }
  const ops: Array<["=" | "-" | "+", number, number]> = [];
  let x = n, y = m;
  for (let d = trace.length - 1; d >= 0 && (x > 0 || y > 0); d--) {
    const vv = trace[d], k = x - y;
    const prevK = k === -d || (k !== d && vv[max + k - 1] < vv[max + k + 1]) ? k + 1 : k - 1;
    const prevX = vv[max + prevK], prevY = prevX - prevK;
    while (x > prevX && y > prevY) { ops.push(["=", x - 1, y - 1]); x--; y--; }
    if (d > 0) {
      if (x === prevX) ops.push(["+", x, y - 1]);
      else ops.push(["-", x - 1, y]);
    }
    x = prevX; y = prevY;
  }
  while (x > 0 && y > 0) { ops.push(["=", x - 1, y - 1]); x--; y--; }
  return ops.reverse();
}

export function diffLines(oldText: string, newText: string, context = 3): { hunks: Hunk[]; added: number; removed: number } {
  const a = oldText.split("\n"), b = newText.split("\n");
  const lines: DiffLine[] = [];
  let added = 0, removed = 0;
  for (const [t, i, j] of myers(a, b)) {
    if (t === "=") lines.push({ t: " ", o: i + 1, n: j + 1, s: a[i] });
    else if (t === "-") { lines.push({ t: "-", o: i + 1, n: null, s: a[i] }); removed++; }
    else { lines.push({ t: "+", o: null, n: j + 1, s: b[j] }); added++; }
  }
  const hunks: Hunk[] = [];
  let i = 0;
  while (i < lines.length) {
    if (lines[i].t === " ") { i++; continue; }
    let start = Math.max(0, i - context), end = i;
    while (end < lines.length) {
      if (lines[end].t !== " ") { end++; continue; }
      let run = 0;
      while (end + run < lines.length && lines[end + run].t === " ") run++;
      if (end + run >= lines.length || run > context * 2) { end = Math.min(lines.length, end + context); break; }
      end += run;
    }
    const slice = lines.slice(start, end);
    const firstOld = slice.find((l) => l.o !== null)?.o ?? 1;
    const firstNew = slice.find((l) => l.n !== null)?.n ?? 1;
    hunks.push({
      old_start: firstOld, new_start: firstNew, lines: slice,
      old_count: slice.filter((l) => l.t !== "+").length, new_count: slice.filter((l) => l.t !== "-").length,
    });
    i = end;
  }
  return { hunks, added, removed };
}
