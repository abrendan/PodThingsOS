from pathlib import Path
import re
import runpy
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class LogoTests(unittest.TestCase):
    def test_reference_gradient_and_all_gradient_references_resolve(self):
        text = (ROOT / "assets/branding/podthings.svg").read_text()
        document = ET.fromstring(text)
        ids = {e.attrib["id"] for e in document.iter() if "id" in e.attrib}
        self.assertTrue(set(re.findall(r"url\(#([^)]+)\)", text)) <= ids)
        ns = {"s": "http://www.w3.org/2000/svg"}
        body = document.find("s:defs/s:linearGradient[@id='body']", ns)
        self.assertIsNotNone(body)
        self.assertEqual([stop.attrib["stop-color"] for stop in body],
                         ["#FBF6EE", "#D9CCF2"])
        wheel = document.find("s:g/s:circle[@r='76']", ns)
        self.assertEqual(wheel.attrib["fill"], "#FFFAF1")
        self.assertEqual(document.attrib["viewBox"], "0 0 256 400")

    def test_tall_logo_fits_square_asset_without_stretching(self):
        renderer = runpy.run_path(str(ROOT/"scripts/generate-podthings-logo.py"))["svg"]
        pixels = [[(0, 0, 0)] * 64 for _ in range(64)]
        renderer(pixels, "podthings.svg", 0, 0, 64, 64)
        visible = [(x, y) for y, row in enumerate(pixels)
                   for x, pixel in enumerate(row) if max(pixel) > 20]
        width = max(x for x, y in visible) - min(x for x, y in visible) + 1
        height = max(y for x, y in visible) - min(y for x, y in visible) + 1
        self.assertGreater(height, width * 1.4)
