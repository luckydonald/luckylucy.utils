# Prefer per-file PEP 723, derive everything above it

## Context

The current hybrid has two marker formats, a `pyproject.toml` for package directories and a custom `# /// luckylucy-module` block for single files, and the directory dependency lists repeat what their files already import.
The goal is to prefer a standard PEP 723 inline block in each file, and let the build script fill in everything above it: folder dependencies merged from their files, names, versions, parent→child dependencies and the root.

## Rules

- **Block format:** the real PEP 723 `# /// script` block, so `uv run file.py` and editors understand it.
  The luckylucy settings go in `[tool.luckylucy]` inside that block, so the custom `luckylucy-module` block type is removed.
- **Dependencies are declared per file** with plain `dependencies = [...]`, in any file, whether or not it is its own package.
- **`[tool.luckylucy] module = true`** in a file's block makes that file its own distribution (as `uvicorns/log_config.py` is now).
  Without it, the file's dependencies are only merged into the parent module and no separate package is built.
- **A file without any marker** is not a package of its own, it belongs to the closest parent folder module.
- **A folder is a module** if it has a `pyproject.toml` with `[tool.luckylucy] module = true`, or an `__init__.py` whose PEP 723 block has `module = true`.
  The `__init__.py` form is preferred, so one format is enough, and the `pyproject.toml` form stays supported.
- **Folder dependencies are merged:** the dependencies of the folder marker itself plus those of every file in it that is not its own module.
  A folder module also depends on the dists of the modules marked inside it (child files and sub-folders), as today.
- A `.py` file with no module folder above it and no `module = true` of its own is still an error, since the meta root `luckylucy.utils` contains no code.

## Changes

1. `scripts/build_modules.py`
   - Replace `INLINE_BLOCK` with PEP 723's reference regex, and parse the block with `tomllib`, returning dependencies and the `tool.luckylucy` table.
   - `discover`: a file is a module if its block says `module = true`, a folder is a module by the rule above, and every other file adds its block dependencies to the module that owns it.
   - Remove `read_inline_dependencies` and `read_directory_dependencies` in favour of one `read_metadata(path)` used for both files and `__init__.py`.
   - Keep `resolve`, `dependencies_of`, `generate` and `parent_name` unchanged.
2. `luckylucy/utils/**`
   - Convert the 6 existing file blocks (`download`, `store`, `eastereggs/quotes`, `files/mime`, `tg_bots/gitinfo`, `tg_bots/language`, `uvicorns/log_config`) to `# /// script` with `[tool.luckylucy] module = true`.
   - Remove the file blocks from files that only had `dependencies = []` and an implicit module (the plain top-level files like `compat.py`, `json.py`) and give them `module = true` blocks instead, because top-level files have no module folder above them and must stay their own packages.
   - Convert each directory `pyproject.toml` marker into a block at the top of that folder's `__init__.py` (22 folders), keeping the dependencies as they are, then delete the `pyproject.toml` files.
   - Optionally spread dependencies to the files that import them (e.g. `pytgbot` onto `tg_bots/peer/user/rights.py`), which the merge makes equivalent, but this is not required for the first pass.
3. `tests/test_build_modules.py`
   - Update the fixtures to the new format and add tests for: dependencies merged from unmarked files into the folder, a `module = true` file excluded from that merge, the `__init__.py` folder marker, and an unmarked file with no module above it being an error.
4. Docs
   - `README.md` "Adding a module" describes the single PEP 723 marker, `ai/plans/002_optional-packages.md` gets a "Revision" section recording this next to the two earlier options.

## Commits (lplp style, each its own)

1. Build script and tests for the PEP 723 markers and merged folder dependencies.
2. Convert the markers in `luckylucy/utils` and delete the directory `pyproject.toml` files.
3. Docs and plan update.

## Verification

- `python3 -W ignore -m unittest tests.test_build_modules tests.test_regex_urls_github`
- `python3 scripts/build_modules.py --list` before and after the marker conversion must show the same modules, the same dependencies and the same `uses` for each.
- Generate and build with `python3 scripts/build_modules.py --out <scratchpad>/modules --build`, then check the wheel file lists of `luckylucy.utils.uvicorns.log_config` (one file), `luckylucy.utils.uvicorns` (only `__init__.py`) and that `luckylucy.utils` still depends on all top-level modules.
