import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.build_modules import ROOT_NAME, discover, generate, parent_name, resolve

REPOSITORY = Path(__file__).parent.parent
ROOT_PROJECT = {
    "version": "1.2", "description": "Test", "license": "MIT", "requires-python": ">=3.8",
    "authors": [{"name": "someone", "email": "someone@example.com"}], "urls": {"Homepage": "https://example.com"},
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
# end def


class BuildModulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "luckylucy" / "utils"
        write(self.source / "logger" / "__init__.py", "x = 1\n")
        write(self.source / "logger" / "pyproject.toml", "[tool.luckylucy]\nmodule = true\n")
        write(self.source / "web" / "__init__.py", "from ..logger import x\n")
        write(self.source / "web" / "pyproject.toml", '[project]\ndependencies = ["flask"]\n[tool.luckylucy]\nmodule = true\n')
        write(self.source / "web" / "helper.py", "y = 1\n")
        write(self.source / "web" / "extra.py", "# /// luckylucy-module\n# dependencies = [\"pytz\"]\n# ///\nfrom . import helper\n")
        write(self.source / "plain.py", "# /// luckylucy-module\n# ///\nfrom luckylucy.utils.logger import x\n")
    # end def

    def test_discover(self) -> None:
        modules = discover(self.source)
        self.assertEqual(
            sorted(modules),
            ["luckylucy.utils.logger", "luckylucy.utils.plain", "luckylucy.utils.web", "luckylucy.utils.web.extra"],
        )
        self.assertEqual(modules["luckylucy.utils.web"].external_dependencies, ["flask"])
        self.assertEqual(modules["luckylucy.utils.web.extra"].external_dependencies, ["pytz"])
        self.assertEqual(
            sorted(file.name for file in modules["luckylucy.utils.web"].files), ["__init__.py", "helper.py"],
            "the file module and the marker must not be part of the directory module",
        )
    # end def

    def test_unmarked_file_is_an_error(self) -> None:
        write(self.source / "orphan.py", "z = 1\n")
        with self.assertRaises(SystemExit):
            discover(self.source)
        # end with
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
            web["dependencies"], ["flask", "luckylucy.utils.logger==1.2", "luckylucy.utils.web.extra==1.2"],
            "imports and inner modules are depended on, with the shared version",
        )
        self.assertTrue((out / "luckylucy.utils.web" / "luckylucy" / "utils" / "web" / "helper.py").is_file())
        self.assertFalse((out / "luckylucy.utils.web" / "luckylucy" / "utils" / "web" / "extra.py").exists())

        root = tomllib.loads((out / ROOT_NAME / "pyproject.toml").read_text())
        self.assertEqual(
            root["project"]["dependencies"],
            ["luckylucy.utils.logger==1.2", "luckylucy.utils.plain==1.2", "luckylucy.utils.web==1.2"],
            "the root depends on all top level modules, but not the nested ones",
        )
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
