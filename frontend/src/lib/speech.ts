type SpeechEvent = {
  results: ArrayLike<{
    isFinal: boolean;
    [index: number]: { transcript: string };
  }>;
};

type SpeechError = { error: string };

interface BrowserRecognizer {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onerror: ((event: SpeechError) => void) | null;
  onend: (() => void) | null;
  start(): void;
  abort(): void;
}

type RecognizerConstructor = new () => BrowserRecognizer;

function getRecognizer(): RecognizerConstructor | undefined {
  if (typeof window === 'undefined') return undefined;

  const browser = window as Window & {
    SpeechRecognition?: RecognizerConstructor;
    webkitSpeechRecognition?: RecognizerConstructor;
  };

  return browser.SpeechRecognition || browser.webkitSpeechRecognition;
}

export function isVoiceSupported(): boolean {
  return Boolean(getRecognizer());
}

export function matchSpokenMachine(
  transcript: string,
  machineIds: readonly string[]
): string | null {
  const numbers: Record<string, string> = {
    zero: '0', oh: '0', one: '1', two: '2',
    three: '3', four: '4', five: '5',
    six: '6', seven: '7', eight: '8', nine: '9',
  };

  const spoken = transcript
    .toLowerCase()
    .replace(/\b(zero|oh|one|two|three|four|five|six|seven|eight|nine)\b/g,
      (word) => numbers[word])
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

  for (const id of machineIds) {
    const characters = id.toLowerCase()
      .replace(/[^a-z0-9]/g, '')
      .split('');

    if (!characters.length) continue;

    const pattern = new RegExp(
      `(?:^|[^a-z0-9])${characters.join('[\\s-]*')}(?:$|[^a-z0-9])`
    );

    if (pattern.test(spoken)) return id;
  }

  return null;
}

export function startVoiceInput(
  onTranscript: (text: string) => void,
  onError: (message: string) => void,
  onEnd: () => void
): () => void {
  const Recognizer = getRecognizer();

  if (!Recognizer) {
    onError('Voice works in Chrome/Edge');
    return () => {};
  }

  const recognition = new Recognizer();
  recognition.lang = 'en-IN';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    const parts: string[] = [];

    for (let i = 0; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        parts.push(event.results[i][0].transcript);
      }
    }

    const text = parts.join(' ').trim();
    if (text) onTranscript(text);
  };

  recognition.onerror = (event) => {
    onError(
      event.error === 'not-allowed'
        ? 'Microphone permission denied'
        : `Voice recognition error: ${event.error}`
    );
  };

  recognition.onend = onEnd;
  recognition.start();

  return () => recognition.abort();
}
