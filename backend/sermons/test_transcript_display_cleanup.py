from django.test import SimpleTestCase

from sermons.processing import TranscriptSegment
from sermons.transcript_display_cleanup import polish_display_segments


class TranscriptDisplayCleanupTests(SimpleTestCase):
    def test_returns_polished_segments_when_count_matches(self):
        segments = (
            TranscriptSegment(0, 2, "um grace meets us"),
            TranscriptSegment(2, 4, "in the ordinary"),
        )

        def runner(*args, **kwargs):
            return type(
                "Result",
                (),
                {"segments": ["Grace meets us.", "In the ordinary."]},
            )()

        text, polished = polish_display_segments(segments, runner=runner)

        self.assertEqual(text, "Grace meets us. In the ordinary.")
        self.assertEqual(
            polished,
            (
                TranscriptSegment(0, 2, "Grace meets us."),
                TranscriptSegment(2, 4, "In the ordinary."),
            ),
        )

    def test_fails_open_when_segment_count_mismatches(self):
        segments = (TranscriptSegment(0, 2, "um grace meets us"),)

        def runner(*args, **kwargs):
            return type("Result", (), {"segments": ["Grace.", "Extra."]})()

        text, polished = polish_display_segments(segments, runner=runner)

        self.assertEqual(text, "um grace meets us")
        self.assertEqual(polished, segments)

    def test_fails_open_when_runner_raises(self):
        from simpleai import SimpleAIException

        segments = (TranscriptSegment(0, 2, "grace"),)

        def runner(*args, **kwargs):
            raise SimpleAIException("model unavailable")

        text, polished = polish_display_segments(segments, runner=runner)

        self.assertEqual(text, "grace")
        self.assertEqual(polished, segments)
