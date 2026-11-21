// File operations shared by the explorer (buttons, right-click, F2/Del) and the File menu.
import { ApiError, basename, dirname, join } from "@core/index";
import { editors } from "./editors.svelte";
import { session } from "./session.svelte";
import { tree } from "./tree.svelte";
import { ui } from "./ui.svelte";

/** Where "New File" goes: the selected folder, the selected file's folder, or the project. */
export function targetDir(): string {
  const sel = tree.selected;
  if (!sel || !sel.startsWith(ui.project)) return ui.project;
  const entries = tree.children[dirname(sel)] ?? [];
  const isDir = entries.find((e) => e.name === basename(sel))?.kind === "dir";
  return isDir ? sel : dirname(sel) || ui.project;
}

export async function newItem(kind: "file" | "dir", dir = targetDir()) {
  if (!dir) return ui.toast("Pick a project first", "error");
  const name = await ui.prompt(kind === "file" ? `New file in ${dir}` : `New folder in ${dir}`, "",
    kind === "file" ? "name.ext (or sub/folder/name.ext)" : "folder name");
  if (!name) return;
  const path = join(dir, name);
  try {
    const parts = name.split("/").filter(Boolean); // make missing parent folders for "a/b/c.txt"
    for (let i = 1; i < parts.length; i++) {
      try {
        await session.api.create(join(dir, ...parts.slice(0, i)), "dir");
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 409)) throw e;  // only "already exists" is fine here
      }
    }
    await session.api.create(path, kind);
    await tree.load(dirname(path));
    tree.expanded[dir] = true;
    if (kind === "file") void editors.open(path);
    tree.selected = path;
  } catch (e) {
    ui.error(e);
  }
}

export async function renameItem(path: string) {
  const name = await ui.prompt(`Rename ${basename(path)}`, basename(path));
  if (!name || name === basename(path)) return;
  const dst = join(dirname(path), name);
  try {
    await session.api.rename(path, dst);
    editors.renamed(path, dst);
    await tree.load(dirname(path));
    tree.selected = dst;
  } catch (e) {
    ui.error(e);
  }
}

export async function deleteItem(path: string) {
  if (!(await ui.confirm(`Delete ${basename(path)}?`, "It can be brought back from Changes → its change set, if it was recorded in history.", "Delete", true))) return;
  try {
    await session.api.remove(path);
    for (const t of [...editors.tabs]) if (t.kind === "file" && (t.path === path || t.path.startsWith(path + "/"))) await editors.close(t.id, false);
    await tree.load(dirname(path));
  } catch (e) {
    ui.error(e);
  }
}
