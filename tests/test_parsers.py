from __future__ import annotations

import unittest

from questiongen.parsers import looks_fragmentary_sentence, normalize_text, prepare_source, split_sentences


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

    def test_split_sentences_keeps_u_s_and_u_k_in_one_sentence(self) -> None:
        source = (
            "Hardly did he know that he had created a classic combination. "
            "Even now, in the U.S. and U.K., no pizza menu seems complete without it. "
            "In Italy, however, most people find pineapple on pizza distasteful."
        )
        self.assertEqual(
            split_sentences(source),
            [
                "Hardly did he know that he had created a classic combination.",
                "Even now, in the U.S. and U.K., no pizza menu seems complete without it.",
                "In Italy, however, most people find pineapple on pizza distasteful.",
            ],
        )

    def test_fragment_detector_accepts_complete_sentence_with_terminal_to(self) -> None:
        sentence = "The old-timers said it was the loudest, most exciting game they’d ever been to."
        self.assertFalse(looks_fragmentary_sentence(sentence))

    def test_fragment_detector_still_rejects_real_terminal_fragment(self) -> None:
        sentence = "The book I was looking for."
        self.assertTrue(looks_fragmentary_sentence(sentence))

    def test_span_preparation_is_deterministic_and_source_preserving(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        prepared = prepare_source(source)
        rerun = prepare_source(source)

        self.assertEqual(prepared.source_text, source)
        self.assertEqual(
            [(span.id, span.text, span.char_start, span.char_end) for span in prepared.span_units],
            [(span.id, span.text, span.char_start, span.char_end) for span in rerun.span_units],
        )
        self.assertEqual([unit.id for unit in prepared.sentence_units], ["S0", "S1"])
        self.assertEqual([gap.id for gap in prepared.gap_units], ["G0", "G1", "G2"])

        target_span = next(span for span in prepared.span_units if span.text == "brought only discontent")
        self.assertEqual(source[target_span.char_start : target_span.char_end], target_span.text)
        self.assertEqual(target_span.normalized_text, "brought only discontent")
        self.assertEqual(target_span.sentence_unit_id, "S1")


if __name__ == "__main__":
    unittest.main()
