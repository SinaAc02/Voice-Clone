import unittest

import numpy as np

from audio_recorder import MicrophoneRecorder


class AudioCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.recorder = MicrophoneRecorder(sample_rate=1_000)

    def test_quiet_recording_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "silent or too quiet"):
            self.recorder._clean_audio(np.zeros(2_000, dtype=np.float32))

    def test_audio_is_trimmed_and_normalized(self) -> None:
        audio = np.zeros(2_000, dtype=np.float32)
        audio[500:1_500] = 0.25

        cleaned = self.recorder._clean_audio(audio)

        self.assertEqual(len(cleaned), 1_100)
        self.assertAlmostEqual(float(np.max(np.abs(cleaned))), 0.92, places=5)

    def test_recording_is_limited_to_thirty_seconds(self) -> None:
        audio = np.full(35_000, 0.25, dtype=np.float32)
        cleaned = self.recorder._clean_audio(audio)
        self.assertEqual(len(cleaned), 30_000)


if __name__ == "__main__":
    unittest.main()
