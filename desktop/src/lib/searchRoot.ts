// "Search in Folder" from the explorer hands the folder to the search view.
type Listener = (dir: string) => void;
const listeners = new Set<Listener>();

export const searchRoot = {
  set(dir: string) { for (const l of listeners) l(dir); },
  listen(l: Listener) { listeners.add(l); return () => listeners.delete(l); },
};
