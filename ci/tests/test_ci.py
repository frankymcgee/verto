"""Cache correctness and workflow routing checks, without Docker or Frappe."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "ci" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


key = load("image_key")
plan = load("plan")


class TestImageInvalidation(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in key.INPUTS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("original dependency input")

    def digest(self, ref="a" * 40):
        return key.image_key(self.root, ref)

    def test_every_declared_dependency_or_runtime_change_invalidates_the_seed(self):
        original = self.digest()
        for name in key.INPUTS:
            with self.subTest(name=name):
                path = self.root / name
                path.write_text("changed dependency input")
                self.assertNotEqual(self.digest(), original)
                path.write_text("original dependency input")
                self.assertEqual(self.digest(), original)

    def test_vanilla_verto_source_and_version_edits_reuse_the_image(self):
        original = self.digest()
        source = self.root / "verto/api/mobile/documents.py"
        source.parent.mkdir(parents=True)
        source.write_text("changed application source")
        (self.root / "verto/__init__.py").write_text('__version__ = "16.3.999"')
        self.assertEqual(self.digest(), original)

    def test_submodule_updates_require_matching_installed_frontend_dependencies(self):
        self.assertNotEqual(self.digest("a" * 40), self.digest("b" * 40))

    def test_missing_dependency_inputs_fail_instead_of_selecting_a_stale_image(self):
        (self.root / "frontend/yarn.lock").unlink()
        with self.assertRaises(FileNotFoundError):
            self.digest()

    def test_invalid_submodule_revision_is_rejected(self):
        for value in ("", "main", "a" * 39, "x" * 40):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.digest(value)


class TestCheckSelection(unittest.TestCase):
    def test_app_only_pr_runs_integration_without_rebuilding_a_fresh_site(self):
        self.assertEqual(plan.select_checks("pull_request", {}, ["frontend/src/pages/Home.vue"]), (True, False))

    def test_schema_installer_migration_and_dependency_prs_also_test_fresh_installation(self):
        for path in ("verto/verto/doctype/daily_timesheet/daily_timesheet.json",
                     "verto/safety/custom/project.json", "verto/install.py", "verto/hooks.py",
                     "verto/patches/v16/new_field.py", "verto/patches.txt", "verto/fixtures/custom_field.json",
                     "pyproject.toml", "package.json", "frontend/yarn.lock", "frappe-ui", "ci/run.sh",
                     ".github/workflows/ci-image.yml"):
            with self.subTest(path=path):
                self.assertEqual(plan.select_checks("pull_request", {}, [path]), (True, True))

    def test_develop_pushes_do_not_duplicate_the_pr_integration_run(self):
        self.assertEqual(plan.select_checks("push", {}, ["ci/run.sh"], "refs/heads/develop"), (False, False))

    def test_version_16_schema_pushes_keep_a_post_merge_fresh_install_check(self):
        self.assertEqual(plan.select_checks("push", {}, ["verto/hooks.py"], "refs/heads/version-16"), (False, True))
        self.assertEqual(plan.select_checks("push", {}, ["frontend/src/pages/Home.vue"], "refs/heads/version-16"), (False, False))

    def test_manual_runs_allow_the_seed_only_mode_and_releases_test_both(self):
        self.assertEqual(plan.select_checks("workflow_dispatch", {"inputs": {"fresh_install": False}}, []), (True, False))
        self.assertEqual(plan.select_checks("workflow_dispatch", {"inputs": {"fresh_install": "true"}}, []), (True, True))
        self.assertEqual(plan.select_checks("workflow_dispatch", {}, []), (True, True))
        self.assertEqual(plan.select_checks("release", {}, []), (True, True))


if __name__ == "__main__":
    unittest.main()
