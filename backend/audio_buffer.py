"""Bounded PCM buffering using the Silero VAD already shipped with Whisper."""
import numpy as np

SAMPLE_RATE = 16000
PAUSE_SAMPLES = 8000       # 500 ms without detected speech
PAD_SAMPLES = 1600         # retain 100 ms after speech
MAX_SAMPLES = 80000        # at most 5 seconds per recognition call


def speech_timestamps(audio):
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    return get_speech_timestamps(
        audio, VadOptions(min_speech_duration_ms=120,
                          min_silence_duration_ms=500, speech_pad_ms=0),
        sampling_rate=SAMPLE_RATE,
    )


class SpeechBuffer:
    def __init__(self, detector=speech_timestamps):
        self.detector = detector
        self.reset()

    def reset(self):
        self.pcm = np.empty(0, dtype=np.int16)

    def feed(self, raw_bytes):
        """Return (PCM bytes, boundary reason) pairs. No output for non-speech.

        Retain a half-second lead-in while idle so speech onsets are not lost.
        Each call belongs to one session and must run serially.
        """
        self.pcm = np.concatenate((self.pcm, np.frombuffer(raw_bytes, dtype=np.int16)))
        result = []
        while self.pcm.size >= PAUSE_SAMPLES:
            window = self.pcm[:MAX_SAMPLES]
            spans = self.detector(window.astype(np.float32) / 32768.0)
            if not spans:
                if self.pcm.size > MAX_SAMPLES:
                    self.pcm = self.pcm[MAX_SAMPLES - PAUSE_SAMPLES:]
                    continue
                self.pcm = self.pcm[-PAUSE_SAMPLES:].copy()
                break
            first_end = spans[0]['end']
            if first_end <= window.size - PAUSE_SAMPLES:
                cut = min(first_end + PAD_SAMPLES, window.size)
                reason = 'pause'
            elif window.size >= MAX_SAMPLES:
                cut = MAX_SAMPLES
                reason = 'limit'
            else:
                break
            result.append((self.pcm[:cut].tobytes(), reason))
            self.pcm = self.pcm[cut:].copy()
        return result
