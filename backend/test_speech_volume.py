import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import server


class SpeechVolumeTests(unittest.IsolatedAsyncioTestCase):
    async def handle(self, amplitude, speech_mode):
        session = server.Session(source_lang='ja', target_lang='en',
                                 task='translate', pause_aware=speech_mode)
        ws = SimpleNamespace(send_text=AsyncMock())
        audio = np.full(16000, amplitude, dtype=np.int16).tobytes()
        with patch.object(server, 'TRANSLATOR', 'nllb'), patch.object(
                server, 'transcribe_chunk', return_value=('今助けてやる', 'ja')) as asr, patch.object(
                server, 'translate', return_value="I'll help you now") as translate:
            await server._handle_chunk(ws, session, asyncio.get_running_loop(),
                                       audio, server.time.monotonic())
        return ws, asr, translate

    async def test_quiet_vad_sections_reach_recognition_and_display(self):
        # Approximate the previously skipped RMS levels in the user's log.
        # Recognition is mocked: this tests routing, not real audio accuracy.
        for amplitude in (46, 85, 95, 98, 131):
            with self.subTest(amplitude=amplitude):
                ws, asr, translate = await self.handle(amplitude, True)
                asr.assert_called_once()
                translate.assert_called_once_with('今助けてやる', 'ja', 'en')
                ws.send_text.assert_awaited_once()
                self.assertEqual(json.loads(ws.send_text.call_args.args[0])['text'],
                                 "I'll help you now")

    async def test_silence_and_near_silence_still_skip_recognition(self):
        for mode in (True, False):
            for amplitude in (0, 16):
                with self.subTest(mode=mode, amplitude=amplitude):
                    ws, asr, translate = await self.handle(amplitude, mode)
                    asr.assert_not_called()
                    translate.assert_not_called()
                    ws.send_text.assert_not_awaited()

    async def test_fixed_chunk_gate_is_unchanged(self):
        ws, asr, translate = await self.handle(98, False)
        asr.assert_not_called()
        translate.assert_not_called()
        ws.send_text.assert_not_awaited()
        ws, asr, translate = await self.handle(2000, False)
        asr.assert_called_once()
        translate.assert_called_once()
        ws.send_text.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
