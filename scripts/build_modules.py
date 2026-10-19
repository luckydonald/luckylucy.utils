#!/usr/bin/env python3
"""
Generates one distribution per marked `luckylucy.utils` module, so each one is installable on its own.

The markers are standard PEP 723 inline blocks at the top of a file, which can also list the `dependencies` of that file:
```py
# /// script
# dependencies = ["uvicorn"]
#
# [tool.luckylucy]
# module = true
# ///
```

- `module = true` in a file makes that file a distribution of its own.
- `module = true` in the block of an `__init__.py` (or in a `pyproject.toml` with `[tool.luckylucy]`) makes that folder a distribution.
- Every other file is part of its closest folder module, and its `dependencies` are merged into the ones of that folder.

Everything else is derived:

- The distribution name is the import path, e.g. `luckylucy.utils.uvicorns.log_config`.
- The version is shared, taken from the root `pyproject.toml`.
- Dependencies on other modules are found by scanning the imports.
- An outer module depends on all marked modules directly inside of it.
- The root `luckylucy.utils` contains no code and depends on all top-level modules.

Usage:
    scripts/build_modules.py --list
    scripts/build_modules.py --out build/modules [--build]
"""
import argparse
import ast
import json
import re
import shutil
import subprocess
import tomllib
import warnings
from dataclasses import dataclass, field
from pathlib import Path

ROOT_NAME = "luckylucy.utils"
# The reference regex of PEP 723.
INLINE_BLOCK = re.compile(r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$")
IGNORED_FILES = {"pyproject.toml"}
IGNORED_DIRS = {"__pycache__"}


@dataclass
class Metadata:
    dependencies: list[str]
    module: bool
# end class


@dataclass
class Module:
    name: str
    path: Path
    is_file: bool
    external_dependencies: list[str]
    files: list[Path] = field(default_factory=list)
    imported_modules: set[str] = field(default_factory=set)
    children: list[str] = field(default_factory=list)
# end class


def read_metadata(path: Path) -> Metadata | None:
    """Reads the PEP 723 `script` block of a python file, or the `pyproject.toml` of a folder, `None` if there is none."""
    if path.is_dir():
        pyproject = path / "pyproject.toml"
        if not pyproject.is_file():
            return None
        # end if
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return Metadata(
            list(data.get("project", {}).get("dependencies", [])),
            bool(data.get("tool", {}).get("luckylucy", {}).get("module", False)),
        )
    # end if
    for match in INLINE_BLOCK.finditer(path.read_text(encoding="utf-8")):
        if match.group("type") != "script":
            continue
        # end if
        content = "".join(line[2:] if line.startswith("# ") else line[1:] for line in match.group("content").splitlines(keepends=True))
        data = tomllib.loads(content)
        return Metadata(
            list(data.get("dependencies", [])),
            bool(data.get("tool", {}).get("luckylucy", {}).get("module", False)),
        )
    # end for
    return None
# end def


def merge(existing: list[str], new: list[str]) -> list[str]:
    return [*existing, *(dependency for dependency in new if dependency not in existing)]
# end def


def dotted(source_root: Path, path: Path) -> str:
    parts = path.relative_to(source_root).with_suffix("").parts
    return ".".join((ROOT_NAME, *parts))
# end def


def discover(source_root: Path) -> dict[str, Module]:
    """Finds all marked modules below the source root and assigns each of the files to the closest module."""
    paths = [
        path for path in sorted(source_root.rglob("*"))
        if not any(part in IGNORED_DIRS for part in path.parts) and path.suffix != ".pyc"
    ]
    modules: dict[str, Module] = {}
    metadata: dict[Path, Metadata] = {}
    for path in paths:
        if path.is_dir():
            found = read_metadata(path)
            if found is not None and found.module:
                modules[dotted(source_root, path)] = Module(dotted(source_root, path), path, False, found.dependencies)
            # end if
        elif path.suffix == ".py":
            found = read_metadata(path)
            if found is None:
                continue
            # end if
            metadata[path] = found
            if not found.module:
                continue
            # end if
            if path.name == "__init__.py":
                name = dotted(source_root, path.parent)
                modules.setdefault(name, Module(name, path.parent, False, []))
            else:
                modules[dotted(source_root, path)] = Module(dotted(source_root, path), path, True, found.dependencies)
            # end if
        # end if
    # end for

    directories = {module.path: module for module in modules.values() if not module.is_file}
    for path in paths:
        if path.is_dir() or path.name in IGNORED_FILES:
            continue
        # end if
        file_module = modules.get(dotted(source_root, path))
        if file_module is not None and file_module.is_file and file_module.path == path:
            file_module.files.append(path)
            continue
        # end if
        if path.suffix == ".pyi" and (stub_module := modules.get(dotted(source_root, path))) is not None:
            stub_module.files.append(path)
            continue
        # end if
        owner = next((directories[parent] for parent in path.parents if parent in directories), None)
        if owner is None:
            if path.suffix in {".py", ".pyi"}:
                raise SystemExit(f"{path} is not part of any module, mark it with `module = true` or put it into a folder module.")
            # end if
            continue
        # end if
        owner.files.append(path)
        if path in metadata:
            owner.external_dependencies = merge(owner.external_dependencies, metadata[path].dependencies)
        # end if
    # end for
    return modules
# end def


def parent_name(name: str, modules: dict[str, Module]) -> str:
    """The closest enclosing marked module, or the root."""
    parts = name.split(".")
    for length in range(len(parts) - 1, len(ROOT_NAME.split(".")), -1):
        candidate = ".".join(parts[:length])
        if candidate in modules and not modules[candidate].is_file:
            return candidate
        # end if
    # end for
    return ROOT_NAME
# end def


def imported_names(source_root: Path, path: Path) -> set[str]:
    """All the dotted names a file might import, with relative imports resolved."""
    package = dotted(source_root, path.parent / "__init__.py").split(".")[:-1] if path.name == "__init__.py" \
        else dotted(source_root, path).split(".")[:-1]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tree = ast.parse(path.read_text(encoding="utf-8"))
    # end with
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - (node.level - 1)]
                module = ".".join([*base, *([node.module] if node.module else [])])
            else:
                module = node.module or ""
            # end if
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
        # end if
    # end for
    return {name for name in names if name.startswith(ROOT_NAME + ".")}
# end def


def owner_of(name: str, modules: dict[str, Module]) -> str | None:
    parts = name.split(".")
    for length in range(len(parts), len(ROOT_NAME.split(".")), -1):
        candidate = ".".join(parts[:length])
        if candidate in modules:
            return candidate
        # end if
    # end for
    return None
# end def


def resolve(source_root: Path, modules: dict[str, Module]) -> None:
    """Fills in `imported_modules` and `children` of every module."""
    for module in modules.values():
        for file in module.files:
            if file.suffix != ".py":
                continue
            # end if
            for name in imported_names(source_root, file):
                owner = owner_of(name, modules)
                if owner is not None and owner != module.name:
                    module.imported_modules.add(owner)
                # end if
            # end for
        # end for
    # end for
    for module in modules.values():
        parent = parent_name(module.name, modules)
        if parent in modules:
            modules[parent].children.append(module.name)
        # end if
    # end for
# end def


def toml_list(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"
# end def


def render_pyproject(name: str, version: str, dependencies: list[str], root_project: dict) -> str:
    author = root_project["authors"][0]
    lines = [
        "[build-system]",
        'requires = ["hatchling"]',
        'build-backend = "hatchling.build"',
        "",
        "[project]",
        f"name = {json.dumps(name)}",
        f"version = {json.dumps(version)}",
        f"description = {json.dumps(root_project['description'] + ' (' + name + ')')}",
        f"license = {json.dumps(root_project['license'])}",
        f"authors = [{{ name = {json.dumps(author['name'])}, email = {json.dumps(author['email'])} }}]",
        f"requires-python = {json.dumps(root_project['requires-python'])}",
        f"dependencies = {toml_list(dependencies)}",
        "",
        "[project.urls]",
        f"Homepage = {json.dumps(root_project['urls']['Homepage'])}",
        "",
        "[tool.hatch.build.targets.wheel]",
    ]
    return "\n".join(lines) + "\n"
# end def


def dependencies_of(module: Module, version: str) -> list[str]:
    internal = sorted(module.imported_modules | set(module.children))
    return [*module.external_dependencies, *(f"{name}=={version}" for name in internal)]
# end def


def generate(source_root: Path, modules: dict[str, Module], root_project: dict, out: Path) -> list[Path]:
    """Writes the buildable project of every distribution below `out`, returns their directories."""
    version = root_project["version"]
    if out.exists():
        shutil.rmtree(out)
    # end if
    projects: list[Path] = []
    for module in modules.values():
        project = out / module.name
        for file in module.files:
            target = project / "luckylucy" / "utils" / file.relative_to(source_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
        # end for
        text = render_pyproject(module.name, version, dependencies_of(module, version), root_project)
        (project / "pyproject.toml").write_text(text + 'packages = ["luckylucy"]\n', encoding="utf-8")
        projects.append(project)
    # end for
    top_level = sorted(name for name in modules if parent_name(name, modules) == ROOT_NAME)
    root_project_dir = out / ROOT_NAME
    root_project_dir.mkdir(parents=True, exist_ok=True)
    text = render_pyproject(ROOT_NAME, version, [f"{name}=={version}" for name in top_level], root_project)
    (root_project_dir / "pyproject.toml").write_text(text + "bypass-selection = true\n", encoding="utf-8")
    projects.append(root_project_dir)
    return projects
# end def


def print_tree(modules: dict[str, Module], version: str) -> None:
    def show(name: str, depth: int) -> None:
        module = modules.get(name)
        extra = "" if module is None else f"  deps={module.external_dependencies} uses={sorted(module.imported_modules)}"
        print("  " * depth + name + extra)
        for child in sorted(module.children if module else []):
            show(child, depth + 1)
        # end for
    # end def

    print(f"{ROOT_NAME} {version}")
    for name in sorted(name for name in modules if parent_name(name, modules) == ROOT_NAME):
        show(name, 1)
    # end for
# end def


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=Path("luckylucy/utils"))
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--out", type=Path, default=Path("build/modules"))
    parser.add_argument("--list", action="store_true", help="only print the module tree")
    parser.add_argument("--build", action="store_true", help="run `uv build` for every generated distribution")
    args = parser.parse_args()

    root_project = tomllib.loads(args.pyproject.read_text(encoding="utf-8"))["project"]
    modules = discover(args.source)
    resolve(args.source, modules)
    if args.list:
        print_tree(modules, root_project["version"])
        return
    # end if
    projects = generate(args.source, modules, root_project, args.out)
    print(f"Generated {len(projects)} distributions in {args.out}")
    if args.build:
        for project in projects:
            subprocess.run(["uv", "build", "--out-dir", str(args.out / "dist"), str(project)], check=True)
        # end for
    # end if
# end def


if __name__ == "__main__":
    main()
# end if
