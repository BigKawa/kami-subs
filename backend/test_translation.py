import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import server

class TranslationTests(unittest.IsolatedAsyncioTestCase):
    async def test_external_translation_pipeline(self):
        for backend in ('google', 'nllb'):
            for source, target in (('ja', 'en'), ('auto', 'en'), ('ja', 'de')):
                with self.subTest(backend=backend, source=source, target=target):
                    session = server.Session(source_lang=source, target_lang=target, task='translate')
                    model = Mock()
                    model.transcribe.return_value = ([SimpleNamespace(text='今助けてやる')], SimpleNamespace(language='ja'))
                    with patch.object(server, 'TRANSLATOR', backend), patch.object(server, 'get_model', return_value=model), patch.object(server, '_translate_' + backend, return_value="I'll help you now") as translator:
                        session.pending, session.last_detected = server.transcribe_chunk(session, np.ones(16000, dtype=np.int16))
                        result = await server._render(session, asyncio.get_running_loop())
                        self.assertEqual(result, "I'll help you now")
                        translator.assert_called_once_with('今助けてやる', 'ja', target)
                        self.assertEqual(model.transcribe.call_args.kwargs['task'], 'transcribe')

    async def test_none_preserves_whisper_translation(self):
        session = server.Session(source_lang='ja', target_lang='en', task='translate')
        model = Mock()
        model.transcribe.return_value = ([SimpleNamespace(text='Hello')], SimpleNamespace(language='ja'))
        with patch.object(server, 'TRANSLATOR', 'none'), patch.object(server, 'get_model', return_value=model):
            session.pending, session.last_detected = server.transcribe_chunk(session, np.ones(16000, dtype=np.int16))
            self.assertEqual(model.transcribe.call_args.kwargs['task'], 'translate')
            self.assertEqual(await server._render(session, asyncio.get_running_loop()), 'Hello')

    async def test_same_language_and_empty_skip_translation(self):
        with patch.object(server, 'TRANSLATOR', 'google'), patch.object(server, '_translate_google') as translator:
            self.assertEqual(server.translate('hello', 'en', 'en'), 'hello')
            self.assertEqual(await server._render(server.Session(), asyncio.get_running_loop()), '')
            translator.assert_not_called()

    async def test_chunk_emits_translated_text(self):
        session = server.Session(source_lang='ja', target_lang='en', task='translate')
        from unittest.mock import AsyncMock
        ws = SimpleNamespace(send_text=AsyncMock())
        with patch.object(server, 'TRANSLATOR', 'google'), patch.object(server, 'transcribe_chunk', return_value=('今助けてやる', 'ja')), patch.object(server, '_translate_google', return_value="I'll help you now"):
            await server._handle_chunk(ws, session, asyncio.get_running_loop(), np.full(16000, 2000, dtype=np.int16).tobytes(), server.time.monotonic())
        import json
        payload = json.loads(ws.send_text.call_args.args[0])
        self.assertEqual(payload['raw'], '今助けてやる')
        self.assertEqual(payload['text'], "I'll help you now")

if __name__ == '__main__':
    unittest.main()
