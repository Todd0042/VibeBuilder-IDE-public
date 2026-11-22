// CodeMirror setup: editing features without the frills, dark theme, lazy language loading.
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import {
  bracketMatching, foldGutter, foldKeymap, HighlightStyle, indentOnInput, indentUnit, LanguageDescription, syntaxHighlighting,
} from "@codemirror/language";
import { languages } from "@codemirror/language-data";
import { highlightSelectionMatches, search, searchKeymap } from "@codemirror/search";
import { Compartment, EditorState, type Extension } from "@codemirror/state";
import {
  crosshairCursor, drawSelection, dropCursor, EditorView, highlightActiveLine, highlightActiveLineGutter,
  highlightSpecialChars, keymap, lineNumbers, rectangularSelection,
} from "@codemirror/view";
import { tags as t } from "@lezer/highlight";

const theme = EditorView.theme({
  "&": { height: "100%", fontSize: "13.5px", backgroundColor: "var(--editor-bg)", color: "var(--text)" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.55" },
  ".cm-content": { caretColor: "var(--accent)" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--accent)", borderLeftWidth: "2px" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": { backgroundColor: "#2f4168 !important" },
  ".cm-gutters": { backgroundColor: "var(--editor-bg)", color: "#4d5566", border: "none" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "#aab2c0" },
  ".cm-activeLine": { backgroundColor: "#ffffff07" },
  ".cm-selectionMatch": { backgroundColor: "#3b4a5c80" },
  ".cm-searchMatch": { backgroundColor: "#e8b04a40", outline: "1px solid #e8b04a90" },
  ".cm-searchMatch.cm-searchMatch-selected": { backgroundColor: "#e8b04a90" },
  ".cm-matchingBracket": { backgroundColor: "#3a4a6a", outline: "none" },
  ".cm-foldPlaceholder": { backgroundColor: "#2a2f3a", border: "none", color: "#9aa3b2" },
  ".cm-tooltip": { backgroundColor: "#1d2129", border: "1px solid #303644" },
  ".cm-tooltip-autocomplete > ul > li[aria-selected]": { backgroundColor: "#2f4168" },
  ".cm-panels": { backgroundColor: "#1a1d24", color: "var(--text)" },
  ".cm-panels.cm-panels-top": { borderBottom: "1px solid var(--line)" },
  ".cm-panel.cm-search": { padding: "6px 10px", fontFamily: "var(--ui)" },
  ".cm-panel.cm-search input, .cm-panel.cm-search button": { fontFamily: "var(--ui)", fontSize: "12.5px" },
  ".cm-textfield": { backgroundColor: "#0f1116", border: "1px solid #303644", borderRadius: "4px", color: "var(--text)", padding: "3px 6px" },
  ".cm-button": { backgroundImage: "none", backgroundColor: "#262b36", border: "1px solid #343b4a", borderRadius: "4px", color: "var(--text)" },
  ".cm-panel.cm-search label": { fontSize: "12px" },
}, { dark: true });

const highlight = HighlightStyle.define([
  { tag: [t.keyword, t.moduleKeyword, t.controlKeyword, t.operatorKeyword], color: "#c792ea" },
  { tag: [t.definitionKeyword, t.modifier], color: "#c792ea" },
  { tag: [t.string, t.special(t.string), t.regexp], color: "#a5d88a" },
  { tag: [t.number, t.bool, t.null, t.atom], color: "#f4a261" },
  { tag: [t.comment, t.lineComment, t.blockComment, t.docComment], color: "#6b7385", fontStyle: "italic" },
  { tag: [t.function(t.variableName), t.function(t.propertyName), t.macroName], color: "#82aaff" },
  { tag: [t.definition(t.variableName), t.definition(t.function(t.variableName))], color: "#82aaff" },
  { tag: [t.typeName, t.className, t.namespace, t.standard(t.typeName)], color: "#ffcb6b" },
  { tag: [t.propertyName, t.attributeName], color: "#89ddff" },
  { tag: [t.tagName], color: "#f07178" },
  { tag: [t.variableName], color: "#d4d7de" },
  { tag: [t.operator, t.punctuation, t.separator, t.bracket], color: "#9aa5b8" },
  { tag: [t.meta, t.annotation, t.processingInstruction], color: "#ffcb6b" },
  { tag: [t.heading], color: "#82aaff", fontWeight: "bold" },
  { tag: [t.emphasis], fontStyle: "italic" },
  { tag: [t.strong], fontWeight: "bold" },
  { tag: [t.link, t.url], color: "#89ddff", textDecoration: "underline" },
  { tag: [t.inserted], color: "#a5d88a" },
  { tag: [t.deleted], color: "#f07178" },
  { tag: [t.invalid], color: "#ff5370" },
]);

export const languageSlot = new Compartment();
export const readOnlySlot = new Compartment();

export function baseExtensions(onSaveKey: () => void, mobile = false): Extension[] {
  return [
    lineNumbers(), highlightActiveLineGutter(), highlightSpecialChars(), history(), foldGutter(), drawSelection(),
    dropCursor(), EditorState.allowMultipleSelections.of(true), indentOnInput(), bracketMatching(), closeBrackets(),
    autocompletion({ activateOnTyping: true }),
    ...(mobile ? [] : [rectangularSelection(), crosshairCursor()]),
    highlightActiveLine(),
    highlightSelectionMatches(), search({ top: true }), indentUnit.of("    "), EditorState.tabSize.of(4),
    syntaxHighlighting(highlight), theme, languageSlot.of([]), readOnlySlot.of([]),
    ...(mobile
      ? [EditorView.contentAttributes.of({ autocorrect: "off", autocapitalize: "off", spellcheck: "false" })]
      : []),
    keymap.of([
      { key: "Mod-s", preventDefault: true, run: () => { onSaveKey(); return true; } },
      ...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, ...foldKeymap, ...completionKeymap, indentWithTab,
    ]),
  ];
}

export async function languageFor(path: string): Promise<Extension | null> {
  const name = path.slice(path.lastIndexOf("/") + 1);
  const special: Record<string, string> = { "CMakeLists.txt": "CMake", Dockerfile: "Dockerfile", Containerfile: "Dockerfile", Makefile: "Makefile" };
  let desc = special[name] ? LanguageDescription.matchLanguageName(languages, special[name]) : null;
  desc = desc ?? LanguageDescription.matchFilename(languages, name);
  if (!desc && /\.(qml|kts|gradle)$/.test(name)) desc = LanguageDescription.matchLanguageName(languages, name.endsWith(".qml") ? "JavaScript" : "Kotlin");
  if (!desc && /\.(fish|bashrc|zshrc|env)$|^\.?(bash|zsh)rc$/.test(name)) desc = LanguageDescription.matchLanguageName(languages, "Shell");
  if (!desc) return null;
  try {
    return await desc.load();
  } catch {
    return null;
  }
}

export function languageName(path: string): string {
  const name = path.slice(path.lastIndexOf("/") + 1);
  return LanguageDescription.matchFilename(languages, name)?.name ?? "Plain Text";
}

export { EditorState, EditorView };
