from django.test import SimpleTestCase

from .models import Sermon
from .processing_messages import owner_facing_processing_message


class OwnerFacingProcessingMessageTests(SimpleTestCase):
    def test_missing_openai_key_explains_configuration(self):
        self.assertEqual(
            owner_facing_processing_message(
                Sermon.ProcessingStatus.FAILED,
                "OPENAI_API_KEY is required for Sermon transcription.",
            ),
            "Transcription isn't configured yet. Add an OpenAI API key on the server, "
            "then try again.",
        )

    def test_unknown_failures_stay_generic_and_safe(self):
        message = owner_facing_processing_message(
            Sermon.ProcessingStatus.FAILED,
            "provider-secret: internal stack detail",
        )
        self.assertNotIn("provider-secret", message)
        self.assertEqual(
            message,
            "Processing couldn't finish. Your recording is still safe — "
            "try again when you're ready.",
        )

    def test_no_speech_points_at_the_recording(self):
        self.assertIn(
            "clear sermon speech",
            owner_facing_processing_message(
                Sermon.ProcessingStatus.FAILED,
                "No predominant-speaker speech was found in the Sermon audio.",
            ),
        )
