const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const context = vm.createContext({
  console, setTimeout, clearTimeout,
  chrome: { runtime: { sendMessage() {}, onMessage: { addListener() {} } } },
  WebSocket: class {
    static OPEN = 1;
    constructor() { this.readyState = 1; this.sent = []; this.events = {}; }
    addEventListener(name, fn) { this.events[name] = fn; }
    send(value) { this.sent.push(value); }
  }
});
vm.runInContext(fs.readFileSync(path.join(__dirname, 'offscreen.js'), 'utf8'), context);
const result = vm.runInContext(`
  openSocket();
  chunkBuffer = new Float32Array(3000);
  ws.events.open();
  const cleared = chunkBuffer.length === 0;
  chunkBuffer = new Float32Array(20000);
  sendChunkIfReady();
  JSON.stringify({cleared, config: JSON.parse(ws.sent[0]),
    packets: ws.sent.slice(1).map(x => x.byteLength), remaining: chunkBuffer.length});
`, context);
const data = JSON.parse(result);
assert.equal(data.cleared, true);
assert.equal(data.config.chunkMode, 'speech');
assert.equal(data.config.sampleRate, 16000);
assert.deepEqual(data.packets, [16000, 16000]);
assert.equal(data.remaining, 4000);
console.log('PASS: speech mode, 0.5s PCM packets, residual samples, reconnect reset');
