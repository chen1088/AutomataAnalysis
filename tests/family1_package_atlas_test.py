"""Packaging accepts fresh grouped builds and the earlier compiled layout."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from family1_package_atlas import individual_pdfs


class IndividualPdfTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)

    def picture(self, directory, name, content=b"picture"):
        path = self.repo / "output/pdf" / directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_fresh_individual_build_is_packaged(self):
        picture = self.picture("family1-atlas/grouped-individual", "m08-shape-01.pdf")
        self.assertEqual(individual_pdfs(self.repo), [picture])

    def test_old_layout_falls_back_and_fresh_build_wins_duplicate(self):
        old = self.picture("family1-grouped-atlas/standalone", "m01-shape-01.pdf")
        self.picture("family1-grouped-atlas/standalone", "m08-shape-01.pdf", b"old")
        fresh = self.picture("family1-atlas/grouped-individual", "m08-shape-01.pdf", b"new")
        self.assertEqual(individual_pdfs(self.repo), [old, fresh])
        self.assertEqual(individual_pdfs(self.repo)[1].read_bytes(), b"new")

    def test_legacy_build_does_not_include_grouped_pictures(self):
        legacy = self.picture("family1-atlas/individual", "m08-01.pdf")
        self.picture("family1-atlas/grouped-individual", "m08-shape-01.pdf")
        self.assertEqual(individual_pdfs(self.repo, legacy_rooted=True), [legacy])


if __name__ == "__main__":
    unittest.main()
