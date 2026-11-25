#!/usr/bin/env python3
"""The Linux launch profile, staged the way each format ships it; no cargo build, no GUI, no network.

What is checked, all synthetic:
  * `nightly-launch.sh` (the AppImage and tar launcher) passes the flavor's own tokens and nothing else;
  * `package.sh` stages the deb/rpm, AppImage and tar launchers and a nightly desktop entry, and
    leaves a stable tree exactly as it was. `nfpm`, `appimagetool` and `strip` are stubs on PATH.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "packaging/linux/nightly-launch.sh"
PACKAGE = ROOT / "packaging/linux/package.sh"
NIGHTLY_VERSION = "0.19.1-nightly.20261124.7.1.gabcdef012345"
PROFILE = "gridz-nightly/profile"

RECORDER = """#!/bin/sh
printf '<%s>\\n' "$@"
"""


def run(argv, cwd, env, check=True):
    return subprocess.run(argv, cwd=cwd, env=env, check=check, capture_output=True, text=True)


class MovedTreeLauncher(unittest.TestCase):
    """nightly-launch.sh as AppRun and as an unpacked tar's launcher."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.data = self.root / "data"
        self.env = {"PATH": os.environ["PATH"], "XDG_DATA_HOME": str(self.data)}

    def install(self, layout):
        """Each placement puts the GUI and this launcher where its format does.

        appdir: AppRun at the root, GUI in usr/bin (also usr/bin/gridz-nightly).
        tar: the kit's flat tar, `gridz` launcher beside the `gridz-bin` GUI.
        tree: a plain tree tarball, bin/gridz-nightly beside bin/gridz.
        """
        tree = self.root / layout
        binary, launcher_name = {
            "appdir": (tree / "usr/bin/gridz", tree / "AppRun"),
            "tar": (tree / "gridz-bin", tree / "gridz"),
            "tree": (tree / "bin/gridz", tree / "bin/gridz-nightly"),
        }[layout]
        binary.parent.mkdir(parents=True)
        binary.write_text(RECORDER)
        binary.chmod(0o755)
        shutil.copy2(LAUNCHER, launcher_name)
        launcher_name.chmod(0o755)
        return launcher_name

    def query(self, launcher, *args):
        return run([str(launcher), *args], cwd=self.root, env=self.env)

    def tokens(self):
        return ["<--launch-profile>", "<nightly-v1>", "<--profile-root>", f"<{self.data / PROFILE}>", "<-->"]

    def test_every_layout_starts_the_gui_through_the_launch_profile(self):
        for layout in ("appdir", "tar", "tree"):
            with self.subTest(layout=layout):
                launcher = self.install(layout)
                self.assertEqual(self.query(launcher).stdout.splitlines(), self.tokens())
                self.assertEqual(
                    self.query(launcher, "workbook with spaces.xlsx", "--other-name.xlsx").stdout.splitlines(),
                    self.tokens() + ["<workbook with spaces.xlsx>", "<--other-name.xlsx>"],
                )

    def test_a_bare_version_query_and_the_launcher_protocol_pass_through(self):
        launcher = self.install("appdir")
        for args in (["--version"], ["-V"], ["--launch-profile", "nightly-v1", "--profile-root", "/launcher", "--", "book.xlsx"]):
            with self.subTest(args=args):
                self.assertEqual(self.query(launcher, *args).stdout.splitlines(), [f"<{arg}>" for arg in args])

    def test_a_missing_data_folder_or_binary_refuses_before_running_anything(self):
        launcher = self.install("appdir")
        refused = run([str(launcher), "book.xlsx"], cwd=self.root, env={"PATH": os.environ["PATH"]}, check=False)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("XDG_DATA_HOME and HOME are both unset", refused.stderr)
        (self.root / "appdir/usr/bin/gridz").unlink()
        missing = run([str(launcher)], cwd=self.root, env=self.env, check=False)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("no GridZ binary", missing.stderr)
        self.assertFalse(self.data.exists(), "a refused launch creates no data folder")

    def test_a_flat_tar_launcher_never_starts_itself(self):
        launcher = self.install("tar")
        (self.root / "tar/gridz-bin").unlink()
        refused = run([str(launcher)], cwd=self.root, env=self.env, check=False)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("no GridZ binary", refused.stderr)

    def test_the_launcher_is_portable_shell(self):
        run(["sh", "-n", str(LAUNCHER)], cwd=self.root, env=self.env)
        self.assertTrue(LAUNCHER.read_text().startswith("#!/bin/sh\n"))


class FlatNightlyTar(unittest.TestCase):
    """nightly.sh needs a release build, so its staging and the archive policy are source-guarded."""

    def test_the_flat_tar_stages_the_kit_layout(self):
        source = (ROOT / "packaging/linux/nightly.sh").read_text()
        self.assertIn('cp "$NIGHTLY_GUI" "$STAGE/gridz-bin"', source, "the GUI is <app>-bin")
        self.assertIn('"$ROOT/packaging/linux/nightly-launch.sh" "$STAGE/gridz"', source, "the launcher is <app>")
        self.assertNotIn('"$STAGE/gridz-nightly"', source, "the flat tar's launcher is gridz")
        policy = (ROOT / "packaging/nightly-archive.py").read_text()
        self.assertIn('{"gridz", "gridz-bin", "gridz-nightly.png"}', policy)
        self.assertIn('required = {"gridz", "gridz-bin", "gridz-nightly.png"', policy)
        launcher = LAUNCHER.read_text()
        self.assertIn('"$here/gridz-bin"', launcher, "the launcher starts the GUI the tar ships")


class StagedFormats(unittest.TestCase):
    """package.sh with stub binaries, a stub nfpm and a stub strip."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.target = self.root / "target"
        self.dist = self.root / "dist"
        self.stubs = self.root / "stubs"
        for directory in (self.target / "release", self.dist, self.stubs):
            directory.mkdir(parents=True, exist_ok=True)
        for name in ("gridz", "gridz-cli"):
            binary = self.target / "release" / name
            binary.write_text(RECORDER)
            binary.chmod(0o755)
        # `strip` would refuse the recorder scripts; the real one is a no-op for a non-ELF file too.
        (self.stubs / "strip").write_text("#!/bin/sh\nexit 0\n")
        (self.stubs / "strip").chmod(0o755)
        (self.stubs / "nfpm").write_text(
            '#!/bin/sh\n'
            'while [ "$#" -gt 0 ]; do [ "$1" = "-f" ] && cp "$2" "$STUB_NFPM_DIR/rendered.yaml"; shift; done\n'
            'exit 0\n'
        )
        (self.stubs / "nfpm").chmod(0o755)
        self.env = {
            "PATH": f"{self.stubs}:{os.environ['PATH']}",
            "HOME": os.environ.get("HOME", str(self.root)),
            "CARGO_TARGET_DIR": str(self.target),
            "DIST": str(self.dist),
            "STUB_NFPM_DIR": str(self.root),
            "GRIDZ_BUILD_DATE": "2026-11-24",
            "GRIDZ_BUILD_SHA": "a" * 40,
        }

    def stage(self, formats="deb tar", **extra):
        env = dict(self.env, **extra)
        run(["bash", str(PACKAGE), "--skip-build", "--formats", formats], cwd=ROOT, env=env)
        return self.target / "linux-package"

    def nightly(self):
        return self.stage(GRIDZ_BUILD_CHANNEL="nightly-v1", GRIDZ_VERSION=NIGHTLY_VERSION)

    def test_nightly_deb_installs_a_launcher_and_the_gui_beside_it(self):
        work = self.nightly()
        stage = work / "nfpm-root"
        launcher = stage / "usr/bin/gridz-nightly"
        gui = stage / "usr/lib/gridz-nightly/gridz"
        self.assertTrue(self.executable(launcher))
        self.assertTrue(self.executable(gui))
        self.assertFalse((stage / "usr/bin/gridz").exists(), "the GUI moved out of usr/bin")
        self.assertTrue(self.executable(stage / "usr/bin/gridz-nightly-cli"))
        text = launcher.read_text()
        self.assertIn('exec "/usr/lib/gridz-nightly/gridz" --launch-profile nightly-v1', text)
        self.assertIn(f"/{PROFILE}", text)
        self.assertEqual(gui.read_text(), RECORDER, "the packaged GUI is the built binary, unchanged")
        rendered = (self.root / "rendered.yaml").read_text()
        self.assertIn(f"src: {stage}/usr/lib/gridz-nightly/gridz", rendered)
        self.assertIn("dst: /usr/lib/gridz-nightly/gridz", rendered)
        self.assertIn("file_info: { mode: 0755 }", rendered)

    def test_nightly_desktop_and_metainfo_are_the_nightly_identity(self):
        work = self.nightly()
        applications = work / "nfpm-root/usr/share/applications"
        desktop = applications / "com.pintaz.gridz.nightly-v1.desktop"
        self.assertEqual(sorted(p.name for p in applications.iterdir()), [desktop.name])
        text = desktop.read_text()
        self.assertIn("Exec=gridz-nightly %F\n", text)
        self.assertIn("TryExec=gridz-nightly\n", text)
        self.assertIn("StartupWMClass=com.pintaz.gridz.nightly-v1\n", text)
        self.assertIn("Name=GridZ Nightly\n", text)
        self.assertNotIn("MimeType=", text)
        metainfo = (work / "nfpm-root/usr/share/metainfo/com.pintaz.gridz.nightly-v1.metainfo.xml").read_text()
        self.assertNotIn("<mediatype>", metainfo)
        self.assertIn("<binary>gridz-nightly</binary>", metainfo)

    def test_nightly_tar_ships_the_launcher_beside_the_binary(self):
        self.nightly()
        archive = self.dist / f"gridz-{NIGHTLY_VERSION}-linux-x86_64.tar.gz"
        with tarfile.open(archive) as tar:
            names = {member.name.split("/", 1)[-1] for member in tar.getmembers()}
            launcher = tar.extractfile("gridz-%s-linux-x86_64/bin/gridz-nightly" % NIGHTLY_VERSION).read().decode()
            binary = tar.extractfile("gridz-%s-linux-x86_64/bin/gridz" % NIGHTLY_VERSION).read().decode()
            desktop = tar.extractfile("gridz-%s-linux-x86_64/share/applications/com.pintaz.gridz.desktop" % NIGHTLY_VERSION).read().decode()
        self.assertIn("bin/gridz", names)
        self.assertEqual(binary, RECORDER)
        self.assertEqual(launcher, LAUNCHER.read_text())
        self.assertIn("Exec=gridz-nightly %F\n", desktop)
        self.assertIn("Name=GridZ Nightly\n", desktop)
        self.assertNotIn("MimeType=", desktop)

    def test_a_stable_tree_is_unchanged(self):
        work = self.stage()
        stage = work / "root"
        self.assertEqual(stage, work / "root", "a stable build packages its one stage")
        self.assertTrue(self.executable(stage / "usr/bin/gridz"))
        self.assertTrue(self.executable(stage / "usr/bin/gridz-cli"))
        self.assertFalse((stage / "usr/bin/gridz-nightly").exists())
        self.assertFalse((stage / "usr/lib").exists())
        rendered = (self.root / "rendered.yaml").read_text()
        self.assertNotIn("gridz-nightly", rendered)
        self.assertIn(f"src: {stage}/usr/bin/gridz\n", rendered)
        desktop = (stage / "usr/share/applications/com.pintaz.gridz.desktop").read_text()
        self.assertIn("Exec=gridz %F\n", desktop)
        self.assertIn("MimeType=", desktop)
        with tarfile.open(self.dist / "gridz-0.19.1-linux-x86_64.tar.gz") as tar:
            names = {member.name.split("/", 1)[-1] for member in tar.getmembers()}
        self.assertIn("bin/gridz", names)
        self.assertNotIn("bin/gridz-nightly", names)

    def test_nightly_appimage_runs_its_launcher_as_apprun(self):
        tool = self.stubs / "appimagetool"
        tool.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" >\"$STUB_NFPM_DIR/appimagetool.argv\"\n")
        tool.chmod(0o755)
        (self.stubs / "runtime").write_text("runtime fixture")
        work = self.stage(
            "appimage",
            GRIDZ_BUILD_CHANNEL="nightly-v1",
            GRIDZ_VERSION=NIGHTLY_VERSION,
            APPIMAGETOOL=str(tool),
            APPIMAGE_RUNTIME=str(self.stubs / "runtime"),
        )
        appdir = work / "GridZ.AppDir"
        self.assertTrue(self.executable(appdir / "AppRun"))
        self.assertEqual((appdir / "AppRun").read_text(), LAUNCHER.read_text(), "AppRun is the launcher, not a symlink")
        self.assertFalse((appdir / "AppRun").is_symlink())
        self.assertEqual((appdir / "usr/bin/gridz-nightly").read_text(), LAUNCHER.read_text())
        self.assertEqual((appdir / "usr/bin/gridz").read_text(), RECORDER, "the binary stays in usr/bin")
        desktop = (appdir / "usr/share/applications/com.pintaz.gridz.nightly-v1.desktop").read_text()
        self.assertIn("Exec=gridz-nightly %F\n", desktop)
        self.assertIn("TryExec=gridz-nightly\n", desktop)
        self.assertIn("StartupWMClass=com.pintaz.gridz.nightly-v1\n", desktop)
        self.assertNotIn("MimeType=", desktop)

    def executable(self, path):
        self.assertTrue(path.is_file(), f"{path} is not a file")
        self.assertTrue(os.access(path, os.X_OK), f"{path} is not executable")
        return True


if __name__ == "__main__":
    unittest.main()
