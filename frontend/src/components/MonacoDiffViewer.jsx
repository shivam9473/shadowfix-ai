import { DiffEditor } from "@monaco-editor/react";

export default function MonacoDiffViewer({ original = "", patched = "" }) {
  if (!original && !patched) {
    return (
      <div className="rounded-lg border border-line p-6 text-sm text-mute">
        The diff appears after the coder finishes.
      </div>
    );
  }

  return (
    <div className="h-[420px] overflow-hidden rounded-lg border border-line">
      <DiffEditor
        original={original}
        modified={patched}
        language="python"
        theme="vs-dark"
        options={{ readOnly: true, renderSideBySide: true, minimap: { enabled: false } }}
      />
    </div>
  );
}
