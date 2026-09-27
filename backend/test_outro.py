import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import numpy as np
import server


class OutroTests(unittest.IsolatedAsyncioTestCase):
    def test_standalone_japanese_outros(self):
        for text in ('ご視聴ありがとうございました', 'ご視聴ありがとうございました。',
                     ' ご視聴ありがとうございます！ ',
                     'ご視聴ありがとうございました ご視聴ありがとうございました',
                     'ご視聴ありがとうございました。ご視聴ありがとうございます！'):
            with self.subTest(text=text):
                self.assertTrue(server.looks_like_hallucination(text))

    def test_normal_thanks_and_longer_sentences_remain(self):
        for text in ('ありがとうございました', 'ありがとうございます。', 'ご視聴ありがとうございましたと彼は言った。',
                     'それでは、ご視聴ありがとうございました。', '今助けてやる', ''):
            with self.subTest(text=text):
                self.assertFalse(server.looks_like_hallucination(text))

    async def test_outro_is_dropped_before_translation_and_display(self):
        session = server.Session(source_lang='ja', target_lang='en', pause_aware=True)
        ws = SimpleNamespace(send_text=AsyncMock())
        with patch.object(server, 'transcribe_chunk', return_value=('ご視聴ありがとうございました。', 'ja')), patch.object(server, 'translate') as translate:
            await server._handle_chunk(ws, session, asyncio.get_running_loop(), np.full(16000, 2000, dtype=np.int16).tobytes(), server.time.monotonic())
            translate.assert_not_called()
            ws.send_text.assert_not_called()
        self.assertEqual(session.pending, '')

if __name__ == '__main__':
    unittest.main()
