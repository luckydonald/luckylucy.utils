# Prefer per-file PEP 723, derive everything above it

## Context

The current hybrid marks package directories with a `pyproject.toml` (`[tool.luckylucy] module = true`) and single files with a custom `# /// luckylucy-module` block.
That is two marker formats, and directories still need hand-written boilerplate plus hand-maintained dependency lists that repeat what their files already say.
The goal is one marker, a standard PEP 723 inline block in each file, with the build script deriving everything above the file level: folder modules, their merged dependencies, names, versions and the root.

## Assumptions to confirm (flag in the final message if any turn out wrong)

- The block type is the real PEP 723 `# /// script`, so `uv run file.py` and editors understand it, instead of the custom `luckylucy-module` type. Only `dependencies` is read, other keys are ignored.
- A file without a block is still a module with no third-party dependencies, so the "file is not part of any module" error goes away and new files just work.
- A folder is a module automatically when it is a Python package (has `__init__.py`).
  Its dist depends on every child dist (files and sub-folders), so its dependencies are the merged dependencies of everything inside it, reached transitively.
  Its dist contains only its own files (`__init__.py` and any non-Python data), as today.
- The folder's own `__init__.py` can carry a PEP 723 block for dependencies only that file needs, like any other file.
- Folders without `__init__.py` (currently only `jinja2/`) get no dist of their own, their files hang directly off the nearest enclosing package, as `jinja2.filters` does now.

## Changes

1. `scripts/build_modules.py`
   - `read_inline_dependencies`: match PEP 723's `# /// script ... # ///` block (the regex from the PEP, `INLINE_BLOCK`), return `[]` when absent instead of `None`.
   - Delete `read_directory_dependencies` and the `pyproject.toml` marker handling (`IGNORED_FILES` stays so stray `pyproject.toml` files are never packaged).
   - `discover`: every `.py` file (except `__init__.py`) is a file module, every directory containing `__init__.py` is a directory module whose external dependencies come from its `__init__.py` block.
     Attach `.pyi` stubs and non-Python files to the owning module as now, and drop the `SystemExit` for unmarked files.
   - `dependencies_of`: unchanged shape (externals, imports, children), since children dependencies already give the merged result.
     Add an option `--flatten` only if asked later, not now.
2. `luckylucy/utils/**`
   - Delete all 22 marker `pyproject.toml` files.
   - Convert the 22 `# /// luckylucy-module` blocks to `# /// script`, and move the dependencies of the removed directory markers into the matching `__init__.py` or, where they belong to one file, that file (for example `flasks`' `flask`/`werkzeug` into `flasks/launcher.py` and `routing.py`, `images`' `Pillow` into `images/color.py`, `time`' `pytz` into `time/__init__.py`, `djangos` `django` into the four files using it).
     Derive the placement from the existing import scan so each file declares what it really imports.
   - Add no blocks to files without third-party dependencies.
3. `tests/test_build_modules.py`
   - Rewrite the fixtures to PEP 723 blocks and `__init__.py` packages, remove the unmarked-file error test, add a test that a folder's dist depends on the dists of its files and sub-folders, and that a file without a block becomes a module with no external dependencies.
4. Docs
   - `README.md` "Adding a module" becomes a single marker description (PEP 723 block, optional), `ai/plans/002_optional-packages.md` gets a short "Revision" section recording this decision next to the two earlier options, `CHANGELOG.md` unchanged.

## Commits (lplp style, each its own)

1. Build script and tests switch to PEP 723 and automatic folder modules.
2. Move the dependencies into per-file blocks and delete the directory `pyproject.toml` markers (separate so the diff is reviewable).
3. Docs and plan update.

## Verification

- `python3 -W ignore -m unittest tests.test_build_modules tests.test_regex_urls_github`
- `python3 scripts/build_modules.py --list` shows the same module tree and the same external dependencies per module as before the change (compare with the current output, nothing should differ except the removed dependency-free noise).
- `python3 scripts/build_modules.py --out <scratchpad>/modules --build` builds, then check the wheels of `luckylucy.utils.uvicorns.log_config` (one file) and `luckylucy.utils.uvicorns` (only `__init__.py`), and that `luckylucy.utils` still depends on all top-level modules.
