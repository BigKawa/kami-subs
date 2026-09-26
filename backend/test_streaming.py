import asyncio, json, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import server

class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_buffer_is_bounded_and_cjk_is_joined(self):
        s = server.Session(source_lang='ja', target_lang='en')
        ws = SimpleNamespace(send_text=AsyncMock())
        pcm = np.full(16000, 2000, dtype=np.int16).tobytes()
        with patch.object(server, 'SENTENCE_MAX_CHUNKS', 2), patch.object(server, 'transcribe_chunk', return_value=('こんにちは', 'ja')), patch.object(server, 'translate', return_value='Hello'):
            for _ in range(3):
                await server._handle_chunk(ws, s, asyncio.get_running_loop(), pcm, server.time.monotonic())
        lines = [json.loads(c.args[0]) for c in ws.send_text.call_args_list]
        self.assertEqual([l['raw'] for l in lines], ['こんにちは', 'こんにちはこんにちは', 'こんにちは'])
        self.assertEqual([l['isFinal'] for l in lines], [False, True, False])

    async def test_vad_empty_finalizes(self):
        s = server.Session(pending='Hello', pending_chunks=1)
        ws = SimpleNamespace(send_text=AsyncMock())
        with patch.object(server, 'transcribe_chunk', return_value=('', 'en')), patch.object(server, 'translate', return_value='Hello'):
            await server._handle_chunk(ws, s, asyncio.get_running_loop(), np.full(16000, 2000, dtype=np.int16).tobytes(), server.time.monotonic())
        self.assertEqual(s.pending, '')
        self.assertEqual(s.pending_chunks, 0)
        self.assertTrue(json.loads(ws.send_text.call_args.args[0])['isFinal'])

    async def test_stale_audio_is_not_transcribed(self):
        s = server.Session(pending='old', pending_chunks=1)
        with patch.object(server, 'transcribe_chunk') as asr:
            await server._handle_chunk(None, s, asyncio.get_running_loop(), b'aa', server.time.monotonic()-10)
            asr.assert_not_called()
        self.assertEqual(s.pending, '')

    async def test_receiver_drops_old_audio_preserves_config_and_stops(self):
        input_queue = asyncio.Queue()
        ws = SimpleNamespace(receive=input_queue.get)
        messages = server._incoming_messages(ws)
        await input_queue.put({'bytes': b'first'})
        first = await anext(messages)
        self.assertEqual(first[0]['bytes'], b'first')
        await input_queue.put({'text': 'config'})
        for i in range(10):
            await input_queue.put({'bytes': bytes([i+1])})
        await asyncio.sleep(0)
        config = await anext(messages)
        self.assertEqual(config[0]['text'], 'config')
        self.assertTrue(config[2])
        received = [(await anext(messages))[0]['bytes'] for _ in range(3)]
        self.assertEqual(received, [b'\x08', b'\x09', b'\x0a'])
        await input_queue.put({'type': 'websocket.disconnect'})
        self.assertEqual((await anext(messages))[0]['type'], 'websocket.disconnect')
        with self.assertRaises(StopAsyncIteration):
            await anext(messages)

    async def test_socket_disconnect_ends_processing(self):
        incoming = asyncio.Queue()
        await incoming.put({'text': json.dumps({'type': 'config', 'sourceLang': 'ja'})})
        await incoming.put({'bytes': b'aa'})
        ws = SimpleNamespace(accept=AsyncMock(), receive=incoming.get, send_text=AsyncMock())
        with patch.object(server, '_handle_chunk', new=AsyncMock(side_effect=server.WebSocketDisconnect())) as handle:
            await asyncio.wait_for(server.handle_socket(ws), timeout=1)
            handle.assert_awaited_once()
        ws.send_text.assert_not_called()

    async def test_reader_cancelled_when_consumer_closes(self):
        queue = asyncio.Queue()
        cancelled = asyncio.Event()
        async def receive():
            try:
                return await queue.get()
            except asyncio.CancelledError:
                cancelled.set()
                raise
        messages = server._incoming_messages(SimpleNamespace(receive=receive))
        await queue.put({'bytes': b'aa'})
        await anext(messages)
        await messages.aclose()
        self.assertTrue(cancelled.is_set())

if __name__ == '__main__':
    unittest.main()
