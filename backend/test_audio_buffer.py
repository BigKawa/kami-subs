import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import numpy as np
import server
from audio_buffer import SpeechBuffer, MAX_SAMPLES, PAUSE_SAMPLES, speech_timestamps


def pcm(seconds, value=2000):
    return np.full(int(seconds * 16000), value, dtype=np.int16).tobytes()


def activity(audio):
    # Deterministic speech/no-speech boundaries for buffer tests, not a VAD substitute.
    indices = np.flatnonzero(audio)
    if not len(indices):
        return []
    breaks = np.flatnonzero(np.diff(indices) > PAUSE_SAMPLES)
    starts = [indices[0]] + [indices[b + 1] for b in breaks]
    ends = [indices[b] + 1 for b in breaks] + [indices[-1] + 1]
    return [dict(start=int(a), end=int(b)) for a, b in zip(starts, ends)]


class SpeechBufferTests(unittest.TestCase):
    def test_pause_flushes_short_utterance(self):
        b = SpeechBuffer(activity)
        self.assertEqual(b.feed(pcm(1)), [])
        sections = b.feed(pcm(.5, 0))
        self.assertEqual(sections, [(pcm(1) + pcm(.1, 0), 'pause')])

    def test_short_hesitation_does_not_split(self):
        b = SpeechBuffer(activity)
        self.assertEqual(b.feed(pcm(1) + pcm(.2, 0) + pcm(1)), [])
        self.assertEqual(b.feed(pcm(.5, 0))[0][1], 'pause')

    def test_continuous_speech_has_five_second_limit(self):
        b = SpeechBuffer(activity)
        for _ in range(9):
            self.assertEqual(b.feed(pcm(.5)), [])
        self.assertEqual(b.feed(pcm(.5)), [(pcm(5), 'limit')])
        self.assertEqual(b.pcm.size, 0)

    def test_silence_is_bounded_and_retains_onset_padding(self):
        b = SpeechBuffer(activity)
        for _ in range(40):
            self.assertEqual(b.feed(pcm(.5, 0)), [])
        self.assertEqual(b.pcm.size, PAUSE_SAMPLES)
        self.assertEqual(b.feed(pcm(1)), [])
        output = b.feed(pcm(.5, 0))[0][0]
        self.assertEqual(output, pcm(.5, 0) + pcm(1) + pcm(.1, 0))

    def test_boundary_preserves_next_utterance(self):
        b = SpeechBuffer(activity)
        output = b.feed(pcm(1) + pcm(.6, 0) + pcm(.5, 3000))
        self.assertEqual(output[0][0], pcm(1) + pcm(.1, 0))
        output = b.feed(pcm(.5, 0))
        self.assertEqual(output[0][0], pcm(.5, 0) + pcm(.5, 3000) + pcm(.1, 0))

    def test_reset_discards_old_audio(self):
        b = SpeechBuffer(activity)
        b.feed(pcm(1))
        b.reset()
        self.assertEqual(b.feed(pcm(.5, 0)), [])

    def test_real_silero_silence_smoke(self):
        self.assertEqual(speech_timestamps(np.zeros(16000, dtype=np.float32)), [])


class SpeechModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_sections_are_final_not_concatenated(self):
        b = SpeechBuffer(activity)
        s = server.Session(source_lang='ja', target_lang='en', pause_aware=True)
        ws = SimpleNamespace(send_text=AsyncMock())
        with patch.object(server, 'transcribe_chunk', return_value=('こんにちは', 'ja')), patch.object(server, 'translate', return_value='Hello'):
            for _ in range(2):
                await server._process_audio_packet(ws, s, asyncio.get_running_loop(), pcm(1) + pcm(.5, 0), server.time.monotonic(), b)
        lines = [json.loads(c.args[0]) for c in ws.send_text.call_args_list]
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(l['isFinal'] for l in lines))
        self.assertTrue(all(l['raw'] == 'こんにちは' for l in lines))
        self.assertEqual(s.pending, '')

    async def test_stale_transport_resets_audio(self):
        b = SpeechBuffer(activity)
        b.feed(pcm(1))
        s = server.Session(pause_aware=True)
        await server._process_audio_packet(None, s, asyncio.get_running_loop(), pcm(.5), server.time.monotonic() - 10, b)
        self.assertEqual(b.pcm.size, 0)

if __name__ == '__main__':
    unittest.main()
