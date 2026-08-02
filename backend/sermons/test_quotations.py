from django.test import SimpleTestCase

from .quotations import (
    accepted_quotations,
    normalize_quotation_display,
    quotation_matches_transcript,
)


class QuotationNormalizationTests(SimpleTestCase):
    def test_matches_transcript_ignoring_case_and_punctuation(self):
        transcript = "there was a father who welcomed his son home"
        self.assertTrue(
            quotation_matches_transcript(
                "There was a father who welcomed his son home.",
                transcript,
            )
        )
        self.assertFalse(
            quotation_matches_transcript(
                "The father ran down the road.",
                transcript,
            )
        )

    def test_normalizes_capitalization_and_terminal_punctuation(self):
        self.assertEqual(
            normalize_quotation_display("grace meets us here"),
            "Grace meets us here.",
        )
        self.assertEqual(
            normalize_quotation_display('"Already finished!"'),
            "Already finished!",
        )

    def test_accepted_quotations_keep_word_order_and_dedupe(self):
        transcript = "Grace meets us here. Grace meets us here again."
        self.assertEqual(
            accepted_quotations(
                [
                    "grace meets us here",
                    "Grace meets us here!",
                    "made up words",
                ],
                transcript,
            ),
            ("Grace meets us here.",),
        )
