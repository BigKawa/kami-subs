import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import server


class VocalizationTests(unittest.IsolatedAsyncioTestCase):
    def test_only_japanese_ah_sounds(self):
        for text in ('あ!あ!あ!あ!あ!', 'あ、あ、あ', ' あぁー！ ', 'アアッ！',
                     '「あ～……」', 'あ', 'ぁぁ'):
            with self.subTest(text=text):
                self.assertTrue(server.is_pure_ah_vocalization(text, 'ja'))

    def test_words_and_other_languages_remain(self):
        for text in ('あ、助けて！', 'ああ、そうです', 'ありがとうございます',
                     'おやすみなさい。', 'うん', 'はい', 'いや', 'あれ',
                     'あいうえお', 'Ah! Help!', '', '…', 'っ', 'ー'):
            with self.subTest(text=text):
                self.assertFalse(server.is_pure_ah_vocalization(text, 'ja'))
        self.assertFalse(server.is_pure_ah_vocalization('あ！', 'en'))

    async def test_filter_in_translation_pipeline(self):
        audio = np.full(16000, 2000, dtype=np.int16).tobytes()
        for backend in ('nllb', 'google'):
            for raw, skipped in (('あ!あ!あ!', True), ('あ、助けて！', False),
                                 ('おやすみなさい。', True),
                                 ('おやすみなさい。また明日。', False)):
                with self.subTest(backend=backend, raw=raw):
                    session = server.Session(source_lang='ja', target_lang='en',
                                             task='translate', pause_aware=True)
                    ws = SimpleNamespace(send_text=AsyncMock())
                    with patch.object(server, 'TRANSLATOR', backend), patch.object(
                            server, 'transcribe_chunk', return_value=(raw, 'ja')), patch.object(
                            server, 'translate', return_value='translated') as translate:
                        await server._handle_chunk(ws, session, asyncio.get_running_loop(),
                                                   audio, server.time.monotonic())
                    if skipped:
                        translate.assert_not_called()
                        ws.send_text.assert_not_called()
                    else:
                        translate.assert_called_once_with(raw, 'ja', 'en')
                        ws.send_text.assert_awaited_once()
                    self.assertEqual(session.pending, '')

    async def test_transcription_still_displays_ah(self):
        session = server.Session(source_lang='ja', target_lang='ja',
                                 task='transcribe', pause_aware=True)
        ws = SimpleNamespace(send_text=AsyncMock())
        with patch.object(server, 'TRANSLATOR', 'nllb'), patch.object(
                server, 'transcribe_chunk', return_value=('あ！', 'ja')):
            await server._handle_chunk(ws, session, asyncio.get_running_loop(),
                                       np.full(16000, 2000, dtype=np.int16).tobytes(),
                                       server.time.monotonic())
        ws.send_text.assert_awaited_once()
        self.assertIn('あ', ws.send_text.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
