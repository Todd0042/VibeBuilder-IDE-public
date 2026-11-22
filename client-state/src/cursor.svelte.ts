// Cursor position of the active editor.
class CursorState {
  path = $state("");
  line = $state(1);
  col = $state(1);
  cursors = $state(1);
  selected = $state(0);

  set(path: string, line: number, col: number, cursors: number, selected: number) {
    this.path = path; this.line = line; this.col = col; this.cursors = cursors; this.selected = selected;
  }
}

export const cursor = new CursorState();
