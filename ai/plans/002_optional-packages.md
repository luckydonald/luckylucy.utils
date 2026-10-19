# Make packages optional to install

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Source todo: `todo:3cde8dfa-dd95-4c9e-95f6-f8222cccdd25` in `ai/todos.md`.

## Goal

Split `luckydonald-utils` into per-module distributions under the `luckylucy.utils` namespace, so `pip install luckylucy.utils.uvicorns.log_config` pulls in only that module and its dependencies.
The outer packages (`luckylucy.utils.uvicorns`, `luckylucy.utils`) just depend on their inner ones.
All distributions share one release version, and building and uploading them is automated, including creating new sub-packages.

## Decisions made

- **Legacy handling:** move, drop legacy. `luckydonaldUtils` is `git mv`'d to `luckylucy/utils/` with no shims. The old `luckydonald-utils` releases stay on PyPI and in git history and are not updated.
- **Naming:** imports mirror the dist names exactly, `from luckylucy.utils.uvicorns.log_config import ...`. No camelCase, no dash-vs-underscore differences, so `luckydonaldUtils.tg_bots` becomes `luckylucy.utils.tg_bots`.
- **Namespace:** `luckylucy` and `luckylucy/utils/` should have no `__init__.py` where possible, so separately installed dists can overlap into the same directories (implicit namespace packages).
- **Module marker: hybrid** (see path of decision below).

## Path of decision: how to mark and build a module

Two options appealed, and the hybrid takes the best of both.

### Option A: `module.toml` plus a generator

```toml
# luckylucy/utils/uvicorns/log_config/module.toml
dependencies = ["uvicorn"]
```

A module is a directory containing `module.toml`. A build script derives the name from the path and generates everything else (the `pyproject.toml`, version, parent→child dependencies).
Pros: minimal to write, no import-time cost. Cons: a non-standard file that tools and IDEs don't understand.

### Option B: a real `pyproject.toml` in every module directory

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "luckylucy.utils.uvicorns.log_config"
dynamic = ["version"]
dependencies = ["luckylucy.utils.uvicorns", "uvicorn"]

[tool.hatch.build.targets.wheel]
packages = ["."]
```

Pros: standard, tools understand it. Cons: about 10 lines of boilerplate per module (version, build-system, namespace layout, child dependencies) that drift if edited by hand.

### Chosen: hybrid

The marker and source of truth is a standard `pyproject.toml` that contains only the module-specific part, and a script fills in the rest at build time.

```toml
[project]
dependencies = ["uvicorn"]

[tool.luckylucy]
module = true
```

The script generates `name` (from the path), `version` (shared), `build-system`, the wheel file selection, and the parent→child dependencies.

### Single-file modules

`luckydonaldUtils/uvicorns/log_config.py` is a file, not a directory, so it cannot hold a `pyproject.toml`.
Files use the same hybrid idea as an inline metadata block at the top of the file, in the style of PEP 723, with the same keys as the `pyproject.toml` form:

```py
# /// luckylucy-module
# dependencies = ["uvicorn"]
# ///
```

- Directory modules (a package with `__init__.py`) use a `pyproject.toml` with `[tool.luckylucy] module = true`.
- File modules use the `# /// luckylucy-module` block, parsed with `tomllib` without importing the file.
- A directory can be a module while its child files and directories are separate modules. The directory module's wheel contains only its own `__init__.py` (and non-module files), not the child modules.

## Implementation steps

Each step is its own commit (rule 8: land the pure move before changing content).

1. **Pure move.** `git mv luckydonaldUtils luckylucy/utils`, with no content changes. Rename the directories that are not snake_case already, if any.
2. **Rename imports.** Replace `luckydonaldUtils` with `luckylucy.utils` in the code, tests, docs, `README.md`, `.bumpversion.cfg` and `ai/skills/uvicorn-app-logging`. Check the relative imports still work. Remove `luckylucy/utils/__init__.py` content (`__version__`) into the build script's version source (see step 4).
3. **Mark modules.** Add the `pyproject.toml` or inline blocks with per-module dependencies, taken from `dependencies-full.txt` (`python-magic` for `files.mime`, `requests` for `download`, `django` for `djangos`, and so on).
4. **Generator script** `scripts/build_modules.py`.
   - Discover modules (the `pyproject.toml` files with `[tool.luckylucy]` and the inline blocks).
   - Generate one dist per module into a build directory, with the shared version from a single source of truth that `bump-my-version` updates.
   - Build the dependency tree: each module depends on its marked children, and the root `luckylucy.utils` depends on all top-level modules.
   - Use `uv build` per module.
5. **Upload automation.** Update the `Makefile` `pip-build`, `pip` and `test-pip` targets to build and upload every generated dist, with `--skip-existing`.
6. **Tests.** Add tests for the discovery and generation (dependency tree, names, shared version), and keep the existing tests passing under the new import paths.
7. **Docs.** Update `README.md` and `CHANGELOG.md` with the new install options and the migration note (`luckydonald-utils` is frozen, switch to `luckylucy.utils`).

## Open points

- The build backend (`hatchling` assumed) must support selecting a single file and excluding child modules.
- PyPI normalizes dots in names, so `luckylucy.utils.uvicorns` is published as `luckylucy-utils-uvicorns`. Check that `luckylucy.utils` is available on PyPI before the first upload.
- The first upload of each new sub-package name needs to be done by the owner's credentials.

## Revision: PEP 723 as the single marker

The hybrid was simplified after the first implementation, only the marker format changed.

- The custom `# /// luckylucy-module` block became the standard PEP 723 `# /// script` block, with the luckylucy settings in `[tool.luckylucy]` inside of it, so `uv run file.py` and editors understand it.
- `module = true` in a file's block makes the file its own distribution, the same in a folder's `__init__.py` makes the folder one. A `pyproject.toml` in a folder with `[tool.luckylucy] module = true` still works.
- Unmarked files are part of their closest folder module and their `dependencies` are merged into it. A file with no module above it is an error, since the root `luckylucy.utils` contains no code.
- The 22 folder `pyproject.toml` files were converted into blocks in the `__init__.py` files, the resulting module tree is identical.
