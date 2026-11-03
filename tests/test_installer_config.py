import hashlib
import importlib.util
import io
import json
import runpy
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer_config", ROOT/"scripts/installer_config.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstallerConfigTests(unittest.TestCase):
    def test_release_payload_excludes_docs_but_preserves_installation_and_licenses(self):
        keep = {
            "installer.config": b"metadata",
            "firmware/podthingsos-firmware.zip": b"firmware",
            "bootloader/bootloader-ipodcolor.ipod": b"bootloader",
            "COPYING": b"GPL",
            "themes/font-LICENSE.txt": b"font license",
            ".podthingsloader/podthings-info.txt": b"runtime metadata",
        }
        remove = {
            "README.md": b"guide", "NAVIGATION.MD": b"guide",
            "developer.markdown": b"guide", "notes.rst": b"guide",
            "docs/internal.txt": b"developer notes",
            "source/source.tar.gz": b"source",
            "bootloader-build-info.txt": b"report",
            "diagnostic/build-info.txt": b"report",
            ".podthingsloader/debug/podthings.map": b"linker report",
        }
        self.assertEqual(module.release_payload({**keep, **remove}), keep)

    def test_all_firmware_targets_omit_nested_docs_and_refresh_checksums(self):
        for target in module.TARGETS:
            with self.subTest(target=target):
                raw = io.BytesIO()
                with zipfile.ZipFile(raw, "w") as archive:
                    archive.writestr(".podthingsloader/podthingsos.ipod", b"native image")
                    archive.writestr(".podthingsloader/README.md", b"guide")
                    archive.writestr(".podthingsloader/docs/developer.txt", b"notes")
                    archive.writestr(".podthingsloader/fonts/LICENSE.txt", b"license")
                    archive.writestr(".podthingsloader/debug/podthings.map", b"report")
                result = module.firmware_archive(raw.getvalue(), "0.9.6", target)
                with zipfile.ZipFile(io.BytesIO(result)) as archive:
                    self.assertEqual(archive.read(".podthingsloader/podthingsos.ipod"), b"native image")
                    self.assertNotIn(".podthingsloader/README.md", archive.namelist())
                    self.assertNotIn(".podthingsloader/docs/developer.txt", archive.namelist())
                    self.assertNotIn(".podthingsloader/debug/podthings.map", archive.namelist())
                    self.assertEqual(archive.read("COPYING"),
                                     (ROOT/"rockbox-firmware/docs/COPYING").read_bytes())
                    self.assertEqual(archive.read(".podthingsloader/fonts/LICENSE.txt"), b"license")
                    for line in archive.read("SHA256SUMS").decode().splitlines():
                        digest, name = line.split("  ", 1)
                        self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)

    def test_other_release_paths_apply_the_same_document_policy(self):
        root = ROOT / "scripts"
        nano = (root / "package-podthings-nano.py").read_text()
        self.assertEqual(nano.count("write_archive("), 4)  # definition and three outputs
        self.assertEqual(nano.count("release_payload(files)"), 3)
        themes = (root / "rockbox-theme-package.sh").read_text()
        self.assertNotIn("PODTHINGS-README.md", themes)
        self.assertNotIn('cp "$root/assets/fonts/FONT-SOURCES.md"', themes)
        combined = (root / "package-podthings-release.py").read_text()
        self.assertIn("entries = release_payload(entries)", combined)

    def test_both_packagers_import_the_shared_contract(self):
        for name in ("package-podthings-release.py", "package-podthings-nano.py"):
            namespace = runpy.run_path(str(ROOT/"scripts"/name))
            self.assertTrue(callable(namespace["installer_metadata"]))
            self.assertTrue(callable(namespace["firmware_archive"]))

    def test_models_have_explicit_independent_minimum(self):
        for target in module.TARGETS:
            for kind in ("firmware-update", "device-kit"):
                value = json.loads(module.config(kind, "0.9", target))
                self.assertEqual(value["minimum_bootloader_version"],
                                 json.loads(module.POLICY.read_text())[target])
                self.assertEqual(value["release_version"], "0.9")
                self.assertEqual(value["target"], target)
                self.assertTrue(value["installable"])
                self.assertEqual(value.get("bundled_bootloader_version"),
                                 "0.9" if kind == "device-kit" else None)

    def test_bundle_dispatches_to_all_child_manifests(self):
        value = json.loads(module.config("bundle", "0.8.1"))
        self.assertFalse(value["installable"])
        self.assertEqual({p["target"] for p in value["packages"]}, set(module.TARGETS))
        for child in value["packages"]:
            self.assertEqual(child["config"], child["target"]+"/installer.config")
            self.assertEqual(child["minimum_bootloader_version"],
                             json.loads(module.POLICY.read_text())[child["target"]])

    def test_non_firmware_packages_are_not_bootloader_permissions(self):
        for kind in ("themes", "source", "diagnostic"):
            value = json.loads(module.config(kind, "0.8",
                "ipodnano3g" if kind == "diagnostic" else None))
            self.assertIsNone(value["minimum_bootloader_version"])
            self.assertEqual(value["installable"], kind == "themes")

    def test_invalid_inputs_are_rejected(self):
        for args in (("firmware-update", "0.8", None),
                     ("device-kit", "0.8", "wrong-model"),
                     ("unknown-type", "0.8", None),
                     ("source", "../0.8", None),
                     ("source", "0.8", "ipod6g")):
            with self.assertRaises(ValueError):
                module.config(*args)

    def test_wrapped_firmware_bytes_and_hashes_are_preserved(self):
        raw = io.BytesIO()
        payload = {".podthingsloader/podthingsos.ipod": b"native firmware",
                   ".podthingsloader/config.cfg": b"user fixture"}
        with zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in payload.items():
                z.writestr(name, data)
        wrapped = module.firmware_archive(raw.getvalue(), "0.8", "ipod6g")
        # Repackaging must replace rather than duplicate metadata.
        wrapped = module.firmware_archive(wrapped, "0.8", "ipod6g")
        with zipfile.ZipFile(io.BytesIO(wrapped)) as z:
            self.assertEqual(z.namelist().count("installer.config"), 1)
            for name, data in payload.items():
                self.assertEqual(z.read(name), data)
            self.assertEqual(json.loads(z.read("installer.config"))["target"], "ipod6g")
            for line in z.read("SHA256SUMS").decode().splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
