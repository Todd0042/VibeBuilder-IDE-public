// Auto-save: a file is saved 3 minutes after its last change; every new change restarts its timer.

export const AUTOSAVE_DELAY_MS = 3 * 60 * 1000;

export class AutoSave {
  private timers = new Map<string, { handle: ReturnType<typeof setTimeout>; due: number }>();

  constructor(private save: (key: string) => void, private delayMs = AUTOSAVE_DELAY_MS) {}

  /** Call on every edit. */
  touch(key: string) {
    this.cancel(key);
    const handle = setTimeout(() => {
      this.timers.delete(key);
      this.save(key);
    }, this.delayMs);
    this.timers.set(key, { handle, due: Date.now() + this.delayMs });
  }

  cancel(key: string) {
    const t = this.timers.get(key);
    if (t) clearTimeout(t.handle);
    this.timers.delete(key);
  }

  cancelAll() {
    for (const k of [...this.timers.keys()]) this.cancel(k);
  }

  /** When the soonest pending save happens (ms epoch), for the status bar countdown. */
  nextDue(): number | null {
    let min: number | null = null;
    for (const t of this.timers.values()) if (min === null || t.due < min) min = t.due;
    return min;
  }

  dueFor(key: string): number | null {
    return this.timers.get(key)?.due ?? null;
  }
}
