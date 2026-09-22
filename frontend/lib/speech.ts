interface SpeechRecognitionEvent {
  results: {
    [index: number]: {
      [index: number]: {
        transcript: string;
      };
    };
  };
}

interface ISpeechRecognition {
  lang: string;
  interimResults: boolean;
  onresult: (event: SpeechRecognitionEvent) => void;
  onerror: (error: unknown) => void;
  start: () => void;
}

export function listenOnce(): Promise<string> {
  const Recognition = (
    window as unknown as {
      webkitSpeechRecognition?: new () => ISpeechRecognition;
      SpeechRecognition?: new () => ISpeechRecognition;
    }
  ).webkitSpeechRecognition || (
    window as unknown as {
      SpeechRecognition?: new () => ISpeechRecognition;
    }
  ).SpeechRecognition;

  if (!Recognition) {
    return Promise.reject(
      new Error("This browser has no speech recognition. Type the answer instead.")
    );
  }
  const recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  return new Promise((resolve, reject) => {
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const text = event.results[0][0].transcript;
      resolve(text);
    };
    recognition.onerror = () => reject(new Error("The microphone did not capture speech."));
    recognition.start();
  });
}
