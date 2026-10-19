# Extend `link-subproject-claude.sh` scaffolding

## Context

`scripts/°base/init/link-subproject-claude.sh` currently symlinks `.claude`,
`.codex`, `ai/tool-settings`, `.mcp.json`, and `AGENTS.md`↔`CLAUDE.md` from a
monorepo subfolder to the shared root. Everything else under `ai/` (query
log, error/output/plan scratch dirs, references, skills) and the JetBrains
`.run/*.run.xml` configs currently have to be set up by hand in every new
subproject, which is error-prone and easy to forget. This change makes the
script create/link all of that too, so a single script run fully wires a
subproject.

Two different sharing strategies are needed, matching how the content
behaves per-subproject:

- **Symlink** things that must stay identical across subprojects and the
  root (`ai/references`, `ai/skills`, each `.run/*.run.xml`, and the four
  `.gitignore` scratch-dir markers — a shared canonical file each, per the
  "gitignore's can be even symlinked, lol" instruction).
- **Copy-if-missing** things that are per-subproject content the user will
  edit and that a symlink would otherwise clobber back to the template
  (`ai/query.md`, `CLAUDE.md`).

## Plan

### 1. Add canonical scratch-dir `.gitignore` content

New template file: `scripts/°base/init/templates/ai-scratch.gitignore`
```
*
!.gitignore
!.gitkeep
```
This is the file that gets symlinked into all four scratch dirs.

### 2. Add scaffolding templates for `query.md` and `CLAUDE.md`

- `scripts/°base/init/templates/query.md` — copy of the current
  `ai/query.md` header (the "AI query log file" preamble + guidelines
  section, without any prior-prompts content).
- `scripts/°base/init/templates/CLAUDE.md` — minimal subproject stub, e.g.
  pointing at `ai/°base/AGENTS.md`-style guidance placeholder text (mirrors
  the root `CLAUDE.md`'s own boilerplate, adapted to say this file should be
  filled in / is subproject-specific).

These are new template files with no existing analog to copy verbatim, so
their exact wording is written during implementation, not fixed by this
plan — keep them short.

### 3. Extend `link-subproject-claude.sh`

In `scripts/°base/init/link-subproject-claude.sh`:

- **`copy_if_missing <rel> <template>` helper**: if `$sub_dir/$rel` doesn't
  exist, `cp` the template there and `git add` it. Never touches an existing
  file (no backup dance — it's meant to seed, not overwrite).
- **`link_shared_dir`**: reuse existing `link_shared` for whole-directory
  symlinks — it already works for any path, so just add calls for
  `ai/references` and `ai/skills`.
- **`.run/*.run.xml`, one by one**: loop over
  `"$git_root"/.run/*.run.xml`, and for each, `link_shared ".run/$(basename "$f")"`.
  Skip (no-op) if `$git_root/.run` doesn't exist.
- **Scratch-dir `.gitignore`s**: for each of
  `ai/errors`, `ai/output/agents`, `ai/output/explore`, `ai/plans`:
  `mkdir -p "$sub_dir/$rel"` then symlink `$sub_dir/$rel/.gitignore` to the
  new `scripts/°base/init/templates/ai-scratch.gitignore` (relative symlink,
  same backup-if-conflicting logic as `link_shared`, since target lives
  outside `git_root`-relative space — write a small variant,
  `link_template(rel, template_name)`, that resolves the source as
  `$git_root/scripts/°base/init/templates/$template_name` instead of
  `$git_root/$rel`).
- **`ai/query.md`**: `copy_if_missing "ai/query.md" ".../templates/query.md"`.
- **`CLAUDE.md`**: call `copy_if_missing "CLAUDE.md" ".../templates/CLAUDE.md"`
  *before* `link_agents_claude`, so a fresh subproject gets seeded content
  and then `AGENTS.md` gets symlinked to it as today. Existing subprojects
  with a real `CLAUDE.md` are untouched (copy_if_missing no-ops).

Final call order at the bottom of the script:
```bash
link_shared ".claude"
link_shared ".codex"
link_shared "ai/tool-settings"
link_shared "ai/references"
link_shared "ai/skills"
link_shared ".mcp.json"
link_run_configs        # loops .run/*.run.xml
link_scratch_gitignores # loops the 4 scratch dirs
copy_if_missing "ai/query.md" "query.md"
copy_if_missing "CLAUDE.md" "CLAUDE.md"
link_agents_claude
```

### Verification

- Run `shellcheck` on the modified script if available, else visually
  re-check quoting.
- Manually test in a scratch monorepo layout: create a throwaway subfolder
  under a checkout with `base` merged at root, run the script twice
  (idempotency check), and confirm:
  - `ai/references`, `ai/skills` become symlinks to root.
  - `.run/*.run.xml` each become individual symlinks (not a directory
    symlink).
  - `ai/errors/.gitignore`, `ai/output/agents/.gitignore`,
    `ai/output/explore/.gitignore`, `ai/plans/.gitignore` are symlinks to
    the one canonical template.
  - `ai/query.md` and `CLAUDE.md` are real (non-symlink) files, seeded from
    templates, created only when absent.
  - Second run makes no changes (no spurious backups).
</content>
