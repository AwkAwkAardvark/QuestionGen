from __future__ import annotations

import unittest

from questiongen.parsers import prepare_source
from questiongen.question_types import MOOD_ATMOSPHERE_SPEC, QUESTION_TYPES
from questiongen.renderers import (
    render_fill_in_the_blank,
    render_grammar,
    render_mood_atmosphere,
    render_paragraph_ordering,
    render_sentence_insertion,
    render_underlined_phrase_meaning,
    render_vocab,
)
from questiongen.schemas import (
    FillInTheBlankPlan,
    GrammarPlan,
    MoodAtmospherePlan,
    ParagraphOrderingPlan,
    SentenceInsertionPlan,
    UnderlinedPhraseMeaningPlan,
    VocabPlan,
)
from questiongen.targeting import allowed_verb_form_variants, grammar_target_inventory, phrase_span_inventory, vocab_target_inventory
from questiongen.validators import validate_sentence_insertion_output


class RendererTests(unittest.TestCase):
    def test_sentence_insertion_renderer_builds_expected_output(self) -> None:
        prepared = prepare_source("A. B. C. D. E. F.")
        plan = SentenceInsertionPlan(
            target_unit_ids=["S2"],
            selected_gap_ids=["G0", "G1", "G2", "G4", "G5"],
            correct_gap_id="G2",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        result = render_sentence_insertion(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["sentence_insertion"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.given_sentence, "C.")
        self.assertNotIn("C.", generated.student_paragraph)
        for sentence in ["A.", "B.", "D.", "E.", "F."]:
            self.assertEqual(generated.student_paragraph.count(sentence), 1)
        for marker in ["①", "②", "③", "④", "⑤"]:
            self.assertEqual(generated.student_paragraph.count(marker), 1)
        self.assertEqual(generated.answer, "③")
        self.assertEqual(generated.QuestionType, QUESTION_TYPES["sentence_insertion"].label_ko)
        self.assertEqual(generated.OriginalQuestionNumber, "8-Analysis")
        self.assertEqual(generated.BatchRowId, 0)
        self.assertEqual(generated.explanation, "문맥상 이 위치가 가장 자연스럽습니다.")
        self.assertEqual(generated.student_paragraph, "① A. ② B. ③ D. ④ E. ⑤ F.")

    def test_sentence_insertion_renderer_keeps_abbreviation_heavy_target_intact(self) -> None:
        source = (
            "Some people love this combination, whereas others can’t seem to stand it. "
            "It can even cause quite heated arguments. "
            "If you haven’t guessed already, it’s the tasty or nasty - depending on your taste - ham and pineapple pizza. "
            "The man who created this pizza was neither Italian nor Hawaiian. "
            "A Greek immigrant from Canada, Sam Panopoulos did not want to stick to the usual ingredients on pizzas, like pepperoni and mushrooms. "
            "He spread canned pineapple and sliced ham onto a pizza and called it “the Hawaiian” as that was what was written on the pineapple can. "
            "Hardly did he know that he had created a classic combination. "
            "Even now, in the U.S. and U.K., no pizza menu seems complete without it. "
            "In Italy, however, most people find pineapple on pizza distasteful. "
            "Why is the Hawaiian pizza so divisive? "
            "The combination is not that odd. "
            "Pineapple and ham is not the only fruit and meat pairing in kitchens around the world. "
            "In France, duck is paired with a sweet orange sauce, and an American Thanksgiving turkey dinner would not be complete without cranberry sauce. "
            "Many people enjoy salty and sweet flavor combinations, while some others prefer keeping those tastes as far from each other as possible."
        )
        prepared = prepare_source(source)
        plan = SentenceInsertionPlan(
            target_unit_ids=["S6"],
            selected_gap_ids=["G0", "G2", "G4", "G6", "G12"],
            correct_gap_id="G6",
            explanation="문맥상 이 위치가 가장 자연스럽습니다.",
        )
        result = render_sentence_insertion(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "10-03",
                "BatchRowId": 0,
                "QuestionTypeKey": "sentence_insertion",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["sentence_insertion"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(
            generated.given_sentence,
            "Even now, in the U.S. and U.K., no pizza menu seems complete without it.",
        )
        self.assertNotIn("and U.K., no pizza menu seems complete without it.", generated.student_paragraph)
        self.assertEqual(
            validate_sentence_insertion_output(
                prepared_source=prepared,
                plan=plan,
                generated=generated,
                type_spec=QUESTION_TYPES["sentence_insertion"],
            ),
            [],
        )

    def test_paragraph_ordering_renderer_builds_expected_output(self) -> None:
        prepared = prepare_source("A. B. C. D. E. F.")
        plan = ParagraphOrderingPlan(
            intro_unit_ids=["S0"],
            continuation_blocks=[["S1"], ["S2", "S3"], ["S4", "S5"]],
            explanation="도입부 다음에 세 덩어리로 배열하는 흐름이 가장 자연스럽습니다.",
        )
        result = render_paragraph_ordering(
            {
                "source_paragraph": "A. B. C. D. E. F.",
                "OriginalQuestionNumber": "8-Analysis",
                "BatchRowId": 1,
                "QuestionTypeKey": "paragraph_ordering",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["paragraph_ordering"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.QuestionType, QUESTION_TYPES["paragraph_ordering"].label_ko)
        self.assertEqual(generated.BatchRowId, 1)
        self.assertIn("[주어진 글] A.", generated.student_paragraph)
        self.assertIn("(A)", generated.student_paragraph)
        self.assertEqual(len(generated.choices), 5)
        self.assertIn(generated.answer, ["①", "②", "③", "④", "⑤"])

    def test_mood_atmosphere_renderer_builds_expected_output(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. In one experiment, two capuchin monkeys were initially perfectly content "
            "with a reward of cucumbers when they successfully performed a task. But when one monkey receiving "
            "plain old cucumbers became enraged, angrily throwing the previously satisfactory salad vegetable "
            "at its handler. The monkey's economy had grown, since grapes are better than cucumbers. "
            "But the resulting inequality brought only discontent."
        )
        plan = MoodAtmospherePlan(
            target_holder="the monkey",
            initial_emotion="content",
            final_emotion="angry",
            choice_pairs=[
                "content -> angry",
                "anxious -> relieved",
                "confident -> embarrassed",
                "curious -> disappointed",
                "proud -> grateful",
            ],
            correct_choice="content -> angry",
            initial_evidence="were initially perfectly content with a reward of cucumbers",
            final_evidence="became enraged",
            shift_trigger="when one monkey receiving plain old cucumbers",
            explanation="초반에는 만족하지만 이후 상황 변화로 분노하게 됩니다.",
        )
        result = render_mood_atmosphere(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "9-03",
                "BatchRowId": 0,
                "QuestionTypeKey": "mood_atmosphere",
                "prepared_source": prepare_source(source),
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            MOOD_ATMOSPHERE_SPEC,
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.QuestionType, MOOD_ATMOSPHERE_SPEC.label_ko)
        self.assertEqual(generated.given_sentence, None)
        self.assertEqual(generated.student_paragraph, source)
        self.assertEqual(generated.choices[0], "content -> angry")
        self.assertEqual(generated.answer, "①")

    def test_underlined_phrase_meaning_renderer_wraps_selected_span_once(self) -> None:
        source = (
            "People’s happiness depends not on their absolute wealth, but rather on their wealth relative "
            "to those around them. But the resulting inequality brought only discontent."
        )
        prepared = prepare_source(source)
        selected_span = next(span for span in prepared.span_units if span.text == "brought only discontent")
        plan = UnderlinedPhraseMeaningPlan(
            selected_span_id=selected_span.id,
            selected_span_text=selected_span.text,
            paraphrase_choices_ko=[
                "비교 속에서 상대적 박탈감만 커졌다는 뜻",
                "경제적 격차가 불만을 낳았다는 뜻",
                "보상이 충분해도 만족이 오래가지 않았다는 뜻",
                "경쟁이 심해져 분노가 겉으로 드러났다는 뜻",
                "차이가 커질수록 성취감도 함께 커졌다는 뜻",
            ],
            correct_choice="경제적 격차가 불만을 낳았다는 뜻",
            surface_meaning="오직 불만만을 가져왔다는 말",
            contextual_meaning="상대적 불평등 때문에 만족 대신 불만이 커졌다는 뜻",
            supporting_evidence="the resulting inequality brought only discontent",
            explanation="문맥상 상대적 불평등으로 인한 불만을 뜻합니다.",
        )
        result = render_underlined_phrase_meaning(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "10-03",
                "BatchRowId": 0,
                "QuestionTypeKey": "underlined_phrase_meaning",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["underlined_phrase_meaning"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.QuestionType, QUESTION_TYPES["underlined_phrase_meaning"].label_ko)
        self.assertEqual(generated.given_sentence, None)
        self.assertEqual(generated.student_paragraph.count("[밑줄]"), 1)
        self.assertEqual(generated.student_paragraph.count("[/밑줄]"), 1)
        self.assertIn("[밑줄]brought only discontent[/밑줄]", generated.student_paragraph)
        self.assertEqual(generated.answer, "②")

    def test_fill_in_the_blank_renderer_replaces_selected_span_once(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        prepared = prepare_source(source)
        selected_span = next(span for span in phrase_span_inventory(prepared) if "electricity" in span.text and "older" in span.text)
        plan = FillInTheBlankPlan(
            selected_span_id=selected_span.id,
            selected_span_text=selected_span.text,
            completion_choices=[
                selected_span.text,
                "more confusion among the residents",
                "a weaker plan for nearby roads",
                "fewer reasons to expand the system",
                "higher costs for the city budget",
            ],
            correct_choice=selected_span.text,
            contextual_meaning_ko="원문의 핵심 설명이 복원되어야 한다는 의미",
            supporting_evidence=selected_span.text,
            explanation="문맥상 원문의 핵심 설명이 복원되어야 합니다.",
        )
        result = render_fill_in_the_blank(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "MVP-01",
                "BatchRowId": 0,
                "QuestionTypeKey": "fill_in_the_blank",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["fill_in_the_blank"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.student_paragraph.count("_____"), 1)
        self.assertNotIn(selected_span.text, generated.student_paragraph)
        self.assertEqual(generated.answer, "①")

    def test_vocab_renderer_marks_five_targets_and_one_corruption(self) -> None:
        source = (
            "City planners recently tested brighter LED lights on several downtown blocks. "
            "The new lights make crosswalks easier to see after sunset. "
            "They also use less electricity than the older lights. "
            "Because the lights use less electricity, the city can improve safety without raising its energy budget. "
            "Residents say the brighter crosswalks feel safer at night. "
            "Officials now plan to expand the same lighting system to nearby neighborhoods."
        )
        prepared = prepare_source(source)
        targets = sorted(vocab_target_inventory(prepared)[:5], key=lambda span: span.char_start)
        plan = VocabPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_span_id=targets[1].id,
            corrupted_word="heavier",
            correction_basis_ko="이 문맥에서는 원래 단어가 글의 설명 흐름과 더 잘 맞습니다",
            supporting_evidence="Residents say the brighter crosswalks feel safer at night.",
            explanation="문맥상 해당 단어의 쓰임이 맞지 않습니다.",
        )
        result = render_vocab(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "MVP-02",
                "BatchRowId": 0,
                "QuestionTypeKey": "vocab",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["vocab"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.choices, ["①", "②", "③", "④", "⑤"])
        self.assertIn("[밑줄①]", generated.student_paragraph)
        self.assertIn("heavier", generated.student_paragraph)
        self.assertEqual(generated.answer, "②")

    def test_grammar_renderer_marks_five_targets_and_one_corruption(self) -> None:
        source = (
            "The city can reduce energy use without raising taxes. "
            "Officials plan to expand the lighting system next month. "
            "Residents say the brighter streets feel safer at night. "
            "Engineers are testing whether the new lamps last longer in winter. "
            "The mayor hopes to show that the project saves money over time. "
            "Teachers report that students now walk home with more confidence."
        )
        prepared = prepare_source(source)
        targets = sorted(grammar_target_inventory(prepared)[:5], key=lambda span: span.char_start)
        original_word = targets[1].text
        replacement = next(iter(sorted(allowed_verb_form_variants(original_word) - {original_word.lower()})))
        plan = GrammarPlan(
            target_span_ids=[span.id for span in targets],
            target_span_texts=[span.text for span in targets],
            corrupted_span_id=targets[1].id,
            corrupted_word=replacement,
            correction_basis_ko="이 자리에는 주변 구조에 맞는 원래 동사 형태가 필요합니다",
            supporting_evidence="Officials plan to expand the lighting system next month.",
            explanation="문맥상 이 자리의 동사 형태가 구조와 맞지 않습니다.",
        )
        result = render_grammar(
            {
                "source_paragraph": source,
                "OriginalQuestionNumber": "MVP-03",
                "BatchRowId": 0,
                "QuestionTypeKey": "grammar",
                "prepared_source": prepared,
                "plan": plan,
                "generated": None,
                "status": "planned",
                "errors": [],
            },
            QUESTION_TYPES["grammar"],
        )
        self.assertEqual(result["status"], "rendered")
        generated = result["generated"]
        self.assertEqual(generated.choices, ["①", "②", "③", "④", "⑤"])
        self.assertIn("[밑줄②]", generated.student_paragraph)
        self.assertIn(replacement, generated.student_paragraph)
        self.assertEqual(generated.answer, "②")


if __name__ == "__main__":
    unittest.main()
