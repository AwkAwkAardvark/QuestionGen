from __future__ import annotations

import unittest

from questiongen.parsers import normalize_text, prepare_source, split_sentences


class ParserTests(unittest.TestCase):
    def test_split_sentences_and_ids(self) -> None:
        prepared = prepare_source("One. Two! Three? Four.")
        self.assertEqual([unit.id for unit in prepared.sentence_units], ["S0", "S1", "S2", "S3"])
        self.assertEqual([gap.id for gap in prepared.gap_units], ["G0", "G1", "G2", "G3", "G4"])

    def test_gap_adjacency(self) -> None:
        prepared = prepare_source("One. Two. Three.")
        self.assertEqual(prepared.gap_units[0].before_unit_id, None)
        self.assertEqual(prepared.gap_units[0].after_unit_id, "S0")
        self.assertEqual(prepared.gap_units[1].before_unit_id, "S0")
        self.assertEqual(prepared.gap_units[1].after_unit_id, "S1")
        self.assertEqual(prepared.gap_units[3].before_unit_id, "S2")
        self.assertEqual(prepared.gap_units[3].after_unit_id, None)

    def test_normalization_is_stable(self) -> None:
        self.assertEqual(normalize_text(" A \n B\t C "), "A B C")
        self.assertEqual(split_sentences("One.\n\nTwo."), ["One.", "Two."])


if __name__ == "__main__":
    unittest.main()
