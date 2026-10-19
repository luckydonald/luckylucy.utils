#!/usr/bin/env python3
"""
Generates one distribution per marked `luckylucy.utils` module, so each one is installable on its own.

The markers are standard PEP 723 inline blocks at the top of a file, which can also list the `dependencies` of that file:
```py
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "uvicorn",
#     "luckylucy.utils.logger",
# ]
#
# [tool.luckylucy]
# module = true
# ///
```

- `module = true` in a file makes that file a distribution of its own.
- `module = true` in the block of an `__init__.py` (or in a `pyproject.toml` with `[tool.luckylucy]`) makes that folder a distribution.
- Every other file is part of its closest folder module, and its `dependencies` are merged into the ones of that folder.
- A dependency starting with `luckylucy.utils.` is an internal one, it gets the shared version pinned.
- `requires-python` of the files is merged into the folder as well, the highest minimum wins.
- A folder marker in `__init__.py` needs just `module = true`, everything else is filled in from the files and the modules inside.

Everything else is derived:

- The distribution name is the import path, e.g. `luckylucy.utils.uvicorns.log_config`.
- The version is shared, taken from the root `pyproject.toml`.
- Dependencies on other modules are found by scanning the imports.
- An outer module depends on all marked modules directly inside of it.
- The root `luckylucy.utils` contains no code and depends on all top-level modules.

Usage:
    scripts/build_modules.py --list
    scripts/build_modules.py --out build/modules [--build]
    scripts/build_modules.py --publish [--repository-url https://test.pypi.org/legacy/]

Besides the distributions, a git-ignored `requirements.txt` with all third-party dependencies is written next to the root `pyproject.toml`.
It lists the modules needing each requirement above it, so an IDE can install them and they are quick to verify.
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
    requires_python: str | None = None
# end class


@dataclass
class Module:
    name: str
    path: Path
    is_file: bool
    external_dependencies: list[str]
    requires_python: str | None = None
    declared_modules: set[str] = field(default_factory=set)
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
            data.get("project", {}).get("requires-python"),
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
            data.get("requires-python"),
        )
    # end for
    return None
# end def


def merge(existing: list[str], new: list[str]) -> list[str]:
    return [*existing, *(dependency for dependency in new if dependency not in existing)]
# end def


def parse_requires_python(requires_python: str) -> tuple[tuple[int, ...], set[tuple[int, int]]]:
    """Only `>=X.Y` plus any `!=X.Y.*` are supported; returns the minimum and the excluded minor versions."""
    minimum: tuple[int, ...] | None = None
    excluded: set[tuple[int, int]] = set()
    for part in requires_python.split(","):
        part = part.strip()
        if (match := re.fullmatch(r">=\s*(\d+(?:\.\d+)*)", part)) is not None:
            minimum = tuple(int(number) for number in match.group(1).split("."))
        elif (match := re.fullmatch(r"!=\s*(\d+)\.(\d+)\.\*", part)) is not None:
            excluded.add((int(match.group(1)), int(match.group(2))))
        else:
            raise SystemExit(f"Only `>=X.Y` and `!=X.Y.*` are supported as `requires-python`, got {requires_python!r}.")
        # end if
    # end for
    if minimum is None:
        raise SystemExit(f"`requires-python` needs a `>=X.Y`, got {requires_python!r}.")
    # end if
    return minimum, excluded
# end def


def minimum_version(requires_python: str) -> tuple[int, ...]:
    return parse_requires_python(requires_python)[0]
# end def


def merge_requires_python(existing: str | None, new: str | None) -> str | None:
    """The stricter of both, so a folder needs at least what its most demanding file needs."""
    if existing is None or new is None:
        return existing or new
    # end if
    (low_a, gaps_a), (low_b, gaps_b) = parse_requires_python(existing), parse_requires_python(new)
    low = max(low_a, low_b)
    gaps = sorted(gap for gap in gaps_a | gaps_b if gap >= low[:2])
    return ", ".join([">=" + ".".join(map(str, low)), *(f"!={major}.{minor}.*" for major, minor in gaps)])
# end def


def absorb(module: "Module", found: Metadata) -> None:
    """Merges the metadata of a file or marker into the module."""
    external = [dependency for dependency in found.dependencies if not is_internal(dependency)]
    module.external_dependencies = merge(module.external_dependencies, external)
    module.declared_modules.update(dependency for dependency in found.dependencies if is_internal(dependency))
    module.requires_python = merge_requires_python(module.requires_python, found.requires_python)
# end def


def is_internal(dependency: str) -> bool:
    return dependency.startswith(ROOT_NAME + ".")
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
                modules[dotted(source_root, path)] = Module(dotted(source_root, path), path, False, [])
                absorb(modules[dotted(source_root, path)], found)
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
                modules[dotted(source_root, path)] = Module(dotted(source_root, path), path, True, [])
                absorb(modules[dotted(source_root, path)], found)
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
            absorb(owner, metadata[path])
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
        for name in module.declared_modules:
            owner = owner_of(name, modules)
            if owner is None:
                raise SystemExit(f"{module.name} depends on {name}, which is not part of any module.")
            # end if
            if owner != module.name:
                module.imported_modules.add(owner)
            # end if
        # end for
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


def render_pyproject(name: str, version: str, dependencies: list[str], root_project: dict, requires_python: str | None = None) -> str:
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
        f"requires-python = {json.dumps(requires_python or root_project['requires-python'])}",
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
        text = render_pyproject(module.name, version, dependencies_of(module, version), root_project, module.requires_python)
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


def render_requirements(modules: dict[str, Module]) -> str:
    sources: dict[str, list[str]] = {}
    for module in modules.values():
        for dependency in module.external_dependencies:
            sources.setdefault(dependency, []).append(module.name)
        # end for
    # end for
    blocks = [
        "".join(f"# {name}\n" for name in sorted(sources[dependency])) + f"{dependency}\n"
        for dependency in sorted(sources, key=lambda dependency: (dependency.lower(), dependency))
    ]
    return "\n".join(blocks)
# end def


def write_requirements(modules: dict[str, Module], path: Path) -> None:
    """Writes the `requirements.txt` and makes sure it is git-ignored, as it is generated."""
    path.write_text(render_requirements(modules), encoding="utf-8")
    gitignore = path.parent / ".gitignore"
    entry = "/" + path.name
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if entry not in lines and path.name not in lines:
        gitignore.write_text("\n".join([*lines, "", "# generated by scripts/build_modules.py", entry, ""]), encoding="utf-8")
    # end if
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
    parser.add_argument("--requirements", type=Path, default=Path("requirements.txt"), help="where to write the dependencies of all modules")
    parser.add_argument("--list", action="store_true", help="only print the module tree")
    parser.add_argument("--build", action="store_true", help="run `uv build` for every generated distribution")
    parser.add_argument("--publish", action="store_true", help="build, then upload every distribution with `twine`, skipping the ones already there")
    parser.add_argument("--repository-url", help="upload here instead of PyPI, e.g. https://test.pypi.org/legacy/")
    parser.add_argument("--username", default="luckydonald", help="user for the upload")
    args = parser.parse_args()

    root_project = tomllib.loads(args.pyproject.read_text(encoding="utf-8"))["project"]
    modules = discover(args.source)
    resolve(args.source, modules)
    if args.list:
        print_tree(modules, root_project["version"])
        return
    # end if
    write_requirements(modules, args.requirements)
    projects = generate(args.source, modules, root_project, args.out)
    print(f"Generated {len(projects)} distributions in {args.out}")
    if args.build or args.publish:
        dist = args.out / "dist"
        shutil.rmtree(dist, ignore_errors=True)  # only upload what was just built
        for project in projects:
            subprocess.run(["uv", "build", "--out-dir", str(dist), str(project)], check=True)
        # end for
        if args.publish:
            command = ["uv", "run", "twine", "upload", "--username", args.username, "--skip-existing"]
            if args.repository_url:
                command += ["--repository-url", args.repository_url]
            # end if
            uploads = sorted(path for path in dist.iterdir() if path.suffix == ".whl" or path.name.endswith(".tar.gz"))  # `uv build` adds a `.gitignore`
            subprocess.run([*command, *map(str, uploads)], check=True)
        # end if
    # end if
# end def


if __name__ == "__main__":
    main()
# end if
