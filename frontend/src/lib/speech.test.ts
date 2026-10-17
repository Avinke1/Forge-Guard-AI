import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  isVoiceSupported,
  matchSpokenMachine,
  startVoiceInput,
} from './speech.ts';

const fleet = ['HP-01', 'HP-02', 'FP-02'] as const;

// Runs without Chrome and without calling any network or AMD endpoint.
test('unsupported environment is detected', () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'window');
  Reflect.deleteProperty(globalThis, 'window');
  try {
    assert.equal(isVoiceSupported(), false);
    let message = '';
    const stop = startVoiceInput(() => {}, (error) => { message = error; }, () => {});
    assert.equal(message, 'Voice works in Chrome/Edge');
    stop();
  } finally {
    if (descriptor) Object.defineProperty(globalThis, 'window', descriptor);
  }
});

test('recognizes HP 01 only in the active fleet', () => {
  assert.equal(matchSpokenMachine('inspect HP 01', fleet), 'HP-01');
  assert.equal(matchSpokenMachine('inspect HP 01', ['APU-01']), null);
});

test('recognizes individual spoken letters and number words', () => {
  assert.equal(matchSpokenMachine('H P zero one', fleet), 'HP-01');
});

test('recognizes the compact machine ID', () => {
  assert.equal(matchSpokenMachine('Show HP01', fleet), 'HP-01');
});

test('recognizes case-insensitive machine IDs', () => {
  assert.equal(matchSpokenMachine('please inspect hp-02', fleet), 'HP-02');
});

test('recognizes FP 02', () => {
  assert.equal(matchSpokenMachine('FP 02', fleet), 'FP-02');
});

test('recognizes the existing MetroPT-3 machine', () => {
  assert.equal(matchSpokenMachine('Open A P U zero one', ['APU-01']), 'APU-01');
});

test('does not select an unrelated machine', () => {
  assert.equal(matchSpokenMachine('please show APU-01', fleet), null);
});

test('does not select a partial numeric machine ID', () => {
  assert.equal(matchSpokenMachine('HP-011', ['HP-01']), null);
});

test('does not select a machine for general speech', () => {
  assert.equal(matchSpokenMachine('show vibration anomalies', fleet), null);
});

test('empty active-run machine list never resolves an ID', () => {
  assert.equal(matchSpokenMachine('HP 01', []), null);
});

class FakeRecognition {
  static latest: FakeRecognition | null = null;
  lang = '';
  continuous = true;
  interimResults = true;
  onresult: ((event: { results: ArrayLike<{ isFinal: boolean; [index: number]: { transcript: string } }> }) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = 0;
  aborted = 0;
  constructor() { FakeRecognition.latest = this; }
  start() { this.started++; }
  abort() { this.aborted++; }
}

function withFakeBrowser(run: () => void): void {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'window');
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { webkitSpeechRecognition: FakeRecognition },
  });
  try { run(); }
  finally {
    FakeRecognition.latest = null;
    if (descriptor) Object.defineProperty(globalThis, 'window', descriptor);
    else Reflect.deleteProperty(globalThis, 'window');
  }
}

test('detects Chrome/Edge Web Speech support', () => {
  withFakeBrowser(() => assert.equal(isVoiceSupported(), true));
});

test('starts recognition in Indian English and returns a final transcript', () => {
  withFakeBrowser(() => {
    let heard = '';
    let ended = 0;
    const stop = startVoiceInput((text) => { heard = text; }, () => {}, () => { ended++; });
    const mic = FakeRecognition.latest!;
    assert.equal(mic.lang, 'en-IN');
    assert.equal(mic.continuous, false);
    assert.equal(mic.interimResults, false);
    assert.equal(mic.started, 1);
    mic.onresult?.({ results: [{ isFinal: true, 0: { transcript: ' HP 01 ' } }] });
    assert.equal(heard, 'HP 01');
    mic.onend?.();
    assert.equal(ended, 1);
    stop();
    assert.equal(mic.aborted, 1);
  });
});

test('ignores interim transcription results', () => {
  withFakeBrowser(() => {
    let heard = '';
    startVoiceInput((text) => { heard = text; }, () => {}, () => {});
    FakeRecognition.latest!.onresult?.({
      results: [{ isFinal: false, 0: { transcript: 'half-completed' } }],
    });
    assert.equal(heard, '');
  });
});

test('handles microphone permission denial without leaking details', () => {
  withFakeBrowser(() => {
    let error = '';
    startVoiceInput(() => {}, (message) => { error = message; }, () => {});
    FakeRecognition.latest!.onerror?.({ error: 'not-allowed' });
    assert.equal(error, 'Microphone permission denied');
  });
});

test('reports recognition failures', () => {
  withFakeBrowser(() => {
    let error = '';
    startVoiceInput(() => {}, (message) => { error = message; }, () => {});
    FakeRecognition.latest!.onerror?.({ error: 'no-speech' });
    assert.match(error, /no-speech/);
  });
});
