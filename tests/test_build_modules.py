import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.build_modules import (
    ROOT_NAME, discover, generate, imported_names, merge_requires_python, owner_of, parent_name, read_metadata, render_requirements, resolve,
    write_requirements,
)

REPOSITORY = Path(__file__).parent.parent
ROOT_PROJECT = {
    "version": "1.2", "description": "Test", "license": "MIT", "requires-python": ">=3.8",
    "authors": [{"name": "someone", "email": "someone@example.com"}], "urls": {"Homepage": "https://example.com"},
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
# end def


def block(dependencies: list[str], module: bool, requires_python: str | None = None) -> str:
    lines = ["# /// script"]
    if requires_python:
        lines.append(f'# requires-python = "{requires_python}"')
    # end if
    lines.append(f"# dependencies = {json.dumps(dependencies)}")
    if module:
        lines += ["#", "# [tool.luckylucy]", "# module = true"]
    # end if
    return "\n".join([*lines, "# ///", ""])
# end def


class BuildModulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "luckylucy" / "utils"
        write(self.source / "logger" / "__init__.py", block([], True) + "x = 1\n")
        write(self.source / "web" / "__init__.py", block(["flask"], True) + "from ..logger import x\n")
        write(self.source / "web" / "helper.py", block(["requests"], False) + "y = 1\n")
        write(self.source / "web" / "unmarked.py", "z = 1\n")
        write(self.source / "web" / "extra.py", block(["pytz"], True) + "from . import helper\n")
        write(self.source / "plain.py", block([], True) + "from luckylucy.utils.logger import x\n")
        write(self.source / "old" / "__init__.py", "")
        write(self.source / "old" / "pyproject.toml", '[project]\ndependencies = ["attrs"]\n[tool.luckylucy]\nmodule = true\n')
    # end def

    def test_discover(self) -> None:
        modules = discover(self.source)
        self.assertEqual(
            sorted(modules),
            [
                "luckylucy.utils.logger", "luckylucy.utils.old", "luckylucy.utils.plain", "luckylucy.utils.web",
                "luckylucy.utils.web.extra",
            ],
        )
        self.assertEqual(modules["luckylucy.utils.web.extra"].external_dependencies, ["pytz"])
        self.assertEqual(modules["luckylucy.utils.old"].external_dependencies, ["attrs"], "a `pyproject.toml` marker still works")
        self.assertEqual(
            sorted(file.name for file in modules["luckylucy.utils.web"].files), ["__init__.py", "helper.py", "unmarked.py"],
            "the file module and the markers must not be part of the folder module",
        )
    # end def

    def test_dependencies_of_files_are_merged_into_the_folder(self) -> None:
        modules = discover(self.source)
        self.assertEqual(modules["luckylucy.utils.web"].external_dependencies, ["flask", "requests"])
    # end def

    def test_requires_python_is_merged_into_the_folder(self) -> None:
        write(self.source / "web" / "new.py", block([], False, ">=3.10"))
        write(self.source / "web" / "old.py", block([], False, ">=3.9"))
        modules = discover(self.source)
        self.assertEqual(modules["luckylucy.utils.web"].requires_python, ">=3.10")
        self.assertIsNone(modules["luckylucy.utils.logger"].requires_python)
        resolve(self.source, modules)
        generate(self.source, modules, ROOT_PROJECT, Path(self.temp.name) / "out")
        for name, expected in (("web", ">=3.10"), ("logger", ">=3.8")):
            project = tomllib.loads((Path(self.temp.name) / "out" / f"luckylucy.utils.{name}" / "pyproject.toml").read_text())["project"]
            self.assertEqual(project["requires-python"], expected)
        # end for
    # end def

    def test_requires_python_keeps_excluded_versions(self) -> None:
        self.assertEqual(
            merge_requires_python(">=2.7, !=3.0.*", ">=2.7, !=3.0.*, !=3.1.*"), ">=2.7, !=3.0.*, !=3.1.*", "the gaps add up",
        )
        self.assertEqual(merge_requires_python(">=2.7, !=3.0.*", ">=3.5"), ">=3.5", "a gap below the minimum is irrelevant")
        self.assertEqual(merge_requires_python(">=2.7", None), ">=2.7")
        with self.assertRaises(SystemExit):
            merge_requires_python(">=2.7", "<4")
        # end with
    # end def

    def test_internal_dependencies_in_a_block(self) -> None:
        write(self.source / "web" / "uses.py", block(["luckylucy.utils.plain"], False))
        modules = discover(self.source)
        self.assertEqual(modules["luckylucy.utils.web"].external_dependencies, ["flask", "requests"], "not an external dependency")
        resolve(self.source, modules)
        self.assertEqual(modules["luckylucy.utils.web"].imported_modules, {"luckylucy.utils.logger", "luckylucy.utils.plain"})
        write(self.source / "web" / "typo.py", block(["luckylucy.utils.nope"], False))
        with self.assertRaises(SystemExit):
            resolve(self.source, discover(self.source))
        # end with
    # end def

    def test_file_outside_of_a_module_is_an_error(self) -> None:
        write(self.source / "orphan.py", "z = 1\n")
        with self.assertRaises(SystemExit):
            discover(self.source)
        # end with
    # end def

    def test_block_of_another_type_is_ignored(self) -> None:
        write(self.source / "web" / "other.py", "# /// something-else\n# dependencies = [\"nope\"]\n# ///\n")
        self.assertEqual(discover(self.source)["luckylucy.utils.web"].external_dependencies, ["flask", "requests"])
    # end def

    def test_resolve(self) -> None:
        modules = discover(self.source)
        resolve(self.source, modules)
        self.assertEqual(modules["luckylucy.utils.web"].imported_modules, {"luckylucy.utils.logger"})
        self.assertEqual(modules["luckylucy.utils.web.extra"].imported_modules, {"luckylucy.utils.web"})
        self.assertEqual(modules["luckylucy.utils.plain"].imported_modules, {"luckylucy.utils.logger"})
        self.assertEqual(modules["luckylucy.utils.web"].children, ["luckylucy.utils.web.extra"])
        self.assertEqual(parent_name("luckylucy.utils.web.extra", modules), "luckylucy.utils.web")
        self.assertEqual(parent_name("luckylucy.utils.plain", modules), ROOT_NAME)
    # end def

    def test_generate(self) -> None:
        modules = discover(self.source)
        resolve(self.source, modules)
        out = Path(self.temp.name) / "out"
        generate(self.source, modules, ROOT_PROJECT, out)

        web = tomllib.loads((out / "luckylucy.utils.web" / "pyproject.toml").read_text())["project"]
        self.assertEqual(web["version"], "1.2")
        self.assertEqual(
            web["dependencies"], ["flask", "requests", "luckylucy.utils.logger==1.2", "luckylucy.utils.web.extra==1.2"],
            "imports and inner modules are depended on, with the shared version",
        )
        self.assertTrue((out / "luckylucy.utils.web" / "luckylucy" / "utils" / "web" / "helper.py").is_file())
        self.assertFalse((out / "luckylucy.utils.web" / "luckylucy" / "utils" / "web" / "extra.py").exists())

        root = tomllib.loads((out / ROOT_NAME / "pyproject.toml").read_text())
        self.assertEqual(
            root["project"]["dependencies"],
            ["luckylucy.utils.logger==1.2", "luckylucy.utils.old==1.2", "luckylucy.utils.plain==1.2", "luckylucy.utils.web==1.2"],
            "the root depends on all top level modules, but not the nested ones",
        )
    # end def

    def test_requirements_are_sorted_with_their_sources(self) -> None:
        write(self.source / "web" / "also.py", block(["Flask >= 1.0"], False))
        write(self.source / "plain2.py", block(["flask", "attrs"], True))
        modules = discover(self.source)
        self.assertEqual(
            render_requirements(modules),
            "# luckylucy.utils.old\n# luckylucy.utils.plain2\nattrs\n\n"
            "# luckylucy.utils.plain2\n# luckylucy.utils.web\nflask\n\n"
            "# luckylucy.utils.web\nFlask >= 1.0\n\n"
            "# luckylucy.utils.web.extra\npytz\n\n"
            "# luckylucy.utils.web\nrequests\n",
        )
        path = Path(self.temp.name) / "requirements.txt"
        write_requirements(modules, path)
        write_requirements(modules, path)
        self.assertEqual((path.parent / ".gitignore").read_text().count("/requirements.txt"), 1, "added once")
    # end def

    def test_repository_blocks_list_the_imported_modules(self) -> None:
        source = REPOSITORY / "luckylucy" / "utils"
        modules = discover(source)
        owners = {file: module.name for module in modules.values() for file in module.files}
        for file, own in owners.items():
            metadata = read_metadata(file)
            if file.suffix != ".py" or file.name == "__init__.py" and metadata is not None and metadata.module:
                continue  # the folder marker is filled in by the script
            # end if
            self.assertIsNotNone(metadata, f"{file} has no `# /// script` block")
            declared = {dependency for dependency in metadata.dependencies if dependency.startswith(ROOT_NAME + ".")}
            imported = {o for name in imported_names(source, file) if (o := owner_of(name, modules)) and o != own}
            self.assertEqual(declared, imported, f"{file}: the block must list the `{ROOT_NAME}` modules it imports")
            self.assertTrue(metadata.requires_python, f"{file} has no `requires-python`")
        # end for
    # end def

    def test_repository_modules_are_consistent(self) -> None:
        source = REPOSITORY / "luckylucy" / "utils"
        modules = discover(source)
        resolve(source, modules)
        self.assertIn("luckylucy.utils.uvicorns.log_config", modules)
        self.assertEqual(parent_name("luckylucy.utils.uvicorns.log_config", modules), "luckylucy.utils.uvicorns")
        self.assertTrue(
            {"luckylucy.utils.logger", "luckylucy.utils.fully_qualified_name"}
            <= modules["luckylucy.utils.uvicorns.log_config"].imported_modules
        )
    # end def
# end class


if __name__ == "__main__":
    unittest.main()
# end if
