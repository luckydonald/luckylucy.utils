---
name: project-codex-memory-orphan-resource-bug
description: "record-codex-memory hook can leave an orphaned resource copy in ~/.codex/memories that isn't tracked in its own sources metadata, causing delete_scoped_memory to silently fail to remove it and the file to keep resyncing back into the repo."
metadata: 
  node_type: memory
  type: project
  originSessionId: a25e02e3-6045-40dc-b481-2ed444335951
  modified: 2026-08-18T00:55:51.272Z
---

`scripts/°base/ai/hooks/record-codex-memory/hook.py` mirrors `ai/°base/memory/*.md` into a separate cross-device shared store at `~/.codex/memories/extensions/base_synced/resources/<project-key>/`, tracked via a `.codex-sync.json` `sources`/`ignored` metadata map. This hook runs independently of, and in addition to, the Claude-side `record-memory` hook.

**Why:** Observed 2026-08-18 during a test-memory cleanup: a memory file was recorded and deleted via the normal Claude-side hook, but kept reappearing in the repo on every subsequent tool call. Root cause: the Codex hook had copied it into the `resources/<project-key>/` dir as a project→resource reverse-sync, but never added a corresponding entry to that dir's `sources` metadata. `delete_scoped_memory()` in the same hook only unlinks resource files it finds a matching `sources` entry for (by `entry.get("target") == name`), so with no metadata entry it silently did nothing to the orphaned file, and the next sync copied it straight back into `ai/°base/memory/`. Manually deleting the orphaned file under `~/.codex/memories/.../resources/-home-user-git-luckydonald-base/` was what actually stopped the resurrection.

**How to apply:** If a memory file in this repo keeps reappearing after deletion despite `ai/memory/delete.py` or the record-memory hook reporting success, check `~/.codex/memories/extensions/base_synced/resources/-home-user-git-luckydonald-base/` for an orphaned copy not listed in that directory's `.codex-sync.json` `sources` map, and remove it directly. This looks like a genuine gap in `delete_scoped_memory()` (doesn't handle resource files with no metadata entry) — worth a proper fix in `record-codex-memory/hook.py` if it recurs.
