"""
whisper_engine.py
Phase 9 — Audio transcription using OpenAI Whisper API.

Handles:
- Audio file transcription (WAV, MP3, M4A, WebM)
- Browser audio blob processing
- Fallback to browser Web Speech API (no server needed)
- Language detection
- Confidence scoring
- Integration with Grok-compatible API
"""

import os
import io
import base64
import tempfile
from typing import Optional, Tuple
from datetime import datetime


# ─── Whisper Transcription ───────────────────────────────────────────────────────
def transcribe_audio_file(audio_path: str, language: str = "en") -> Tuple[str, float]:
    """
    Transcribe an audio file using OpenAI Whisper API.

    Args:
        audio_path: Path to audio file (WAV, MP3, M4A, WebM, OGG)
        language: Language hint (en, hi for Hindi)

    Returns:
        Tuple of (transcript_text, confidence_score)
    """
    try:
        from openai import OpenAI
        from dotenv import load_dotenv
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROK_API_KEY")
        if not api_key:
            return "", 0.0

        client = OpenAI(api_key=api_key)

        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=language,
                response_format="verbose_json"
            )

        transcript = response.text.strip()
        # Whisper doesn't return per-segment confidence directly
        # Use avg_logprob from segments if available
        confidence = 0.85  # Default high confidence for Whisper
        if hasattr(response, 'segments') and response.segments:
            avg_logprob = sum(s.avg_logprob for s in response.segments) / len(response.segments)
            # Convert log prob to 0-1 confidence (logprob of -0.5 ≈ 0.85)
            confidence = min(1.0, max(0.0, 1.0 + avg_logprob))

        return transcript, confidence

    except Exception as e:
        print(f"Whisper transcription error: {e}")
        return "", 0.0


def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "audio.wav",
                            language: str = "en") -> Tuple[str, float]:
    """
    Transcribe audio from bytes (e.g., browser recording).

    Args:
        audio_bytes: Raw audio bytes
        filename: Filename hint for format detection
        language: Language hint

    Returns:
        Tuple of (transcript_text, confidence)
    """
    with tempfile.NamedTemporaryFile(suffix=f"_{filename}", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        return transcribe_audio_file(tmp_path, language)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def transcribe_base64_audio(b64_data: str, mime_type: str = "audio/wav",
                              language: str = "en") -> Tuple[str, float]:
    """
    Transcribe base64-encoded audio from browser.

    Args:
        b64_data: Base64 encoded audio
        mime_type: Audio MIME type (audio/wav, audio/webm, audio/mp4)
        language: Language

    Returns:
        Tuple of (transcript, confidence)
    """
    # Clean base64 header if present
    if "," in b64_data:
        b64_data = b64_data.split(",")[1]

    audio_bytes = base64.b64decode(b64_data)
    ext = mime_type.split("/")[-1].replace("mpeg", "mp3").replace("webm", "webm")
    return transcribe_audio_bytes(audio_bytes, f"recording.{ext}", language)


# ─── Check Whisper Availability ──────────────────────────────────────────────────
def is_whisper_available() -> bool:
    """Check if Whisper API is available (needs OpenAI key)."""
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROK_API_KEY")
    if not api_key:
        return False
    try:
        from openai import OpenAI
        return True
    except ImportError:
        return False


def get_transcription_mode() -> str:
    """
    Determine best transcription mode for current setup.
    Returns: 'whisper_api' | 'browser_speech' | 'manual'
    """
    if is_whisper_available():
        return "whisper_api"
    return "browser_speech"


# ─── Browser Speech API JavaScript ───────────────────────────────────────────────
def get_browser_speech_js() -> str:
    """
    Returns JavaScript code for browser-based Web Speech API.
    Injected into Streamlit via st.components.v1.html().
    Sends transcript back to Python via Streamlit's component messaging.
    """
    return """
<script>
// NeuroResume Voice Interface — Browser Speech API
(function() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        document.getElementById('voice-status').textContent = 'Speech recognition not supported. Use Chrome or Edge.';
        return;
    }

    let recognition = null;
    let isListening = false;
    let finalTranscript = '';

    function initRecognition() {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-IN';
        recognition.maxAlternatives = 1;

        recognition.onstart = function() {
            isListening = true;
            document.getElementById('voice-status').textContent = '🎙 Listening...';
            document.getElementById('mic-btn').style.background = '#ef4444';
            document.getElementById('mic-btn').textContent = '⏹ Stop';
            document.getElementById('interim-text').textContent = '';
        };

        recognition.onresult = function(event) {
            let interimTranscript = '';
            finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }
            document.getElementById('interim-text').textContent = interimTranscript || finalTranscript;
        };

        recognition.onend = function() {
            isListening = false;
            document.getElementById('mic-btn').style.background = '#7c3aed';
            document.getElementById('mic-btn').textContent = '🎙 Speak';

            if (finalTranscript) {
                document.getElementById('voice-status').textContent = '✓ Processing: "' + finalTranscript + '"';
                document.getElementById('interim-text').textContent = finalTranscript;
                // Send to Streamlit via query param approach
                sendTranscriptToStreamlit(finalTranscript);
            } else {
                document.getElementById('voice-status').textContent = '◌ Ready — Click mic to speak';
            }
        };

        recognition.onerror = function(event) {
            isListening = false;
            let msg = 'Error: ' + event.error;
            if (event.error === 'no-speech') msg = 'No speech detected. Try again.';
            if (event.error === 'not-allowed') msg = 'Microphone access denied. Allow in browser settings.';
            document.getElementById('voice-status').textContent = msg;
            document.getElementById('mic-btn').style.background = '#7c3aed';
            document.getElementById('mic-btn').textContent = '🎙 Speak';
        };
    }

    function sendTranscriptToStreamlit(text) {
        // Store in window for Streamlit to poll
        window.neurorVoiceTranscript = text;
        window.neurorVoiceTimestamp = Date.now();

        // Also update hidden input for form-based approach
        const hiddenInput = document.getElementById('transcript-hidden');
        if (hiddenInput) {
            hiddenInput.value = text;
            hiddenInput.dispatchEvent(new Event('change'));
        }

        // Try postMessage approach for Streamlit components
        window.parent.postMessage({
            type: 'neuroresume_voice',
            transcript: text,
            timestamp: Date.now()
        }, '*');
    }

    // Text-to-Speech
    window.speakText = function(text) {
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'en-IN';
        utterance.rate = 0.95;
        utterance.pitch = 1.0;
        utterance.volume = 0.9;

        // Try to use a good voice
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v =>
            v.lang.includes('en') && (v.name.includes('Google') || v.name.includes('Natural'))
        ) || voices.find(v => v.lang.includes('en-IN')) || voices[0];
        if (preferredVoice) utterance.voice = preferredVoice;

        window.speechSynthesis.speak(utterance);
        document.getElementById('voice-status').textContent = '🔊 Speaking...';
        utterance.onend = () => {
            document.getElementById('voice-status').textContent = '◌ Ready — Click mic to speak';
        };
    };

    // Mic button handler
    document.getElementById('mic-btn').addEventListener('click', function() {
        if (!recognition) initRecognition();
        if (isListening) {
            recognition.stop();
        } else {
            finalTranscript = '';
            try {
                recognition.start();
            } catch(e) {
                initRecognition();
                recognition.start();
            }
        }
    });

    // Speak button
    const speakBtn = document.getElementById('speak-btn');
    if (speakBtn) {
        speakBtn.addEventListener('click', function() {
            const text = document.getElementById('tts-text').textContent;
            if (text) window.speakText(text);
        });
    }

    // Poll for transcript (for Streamlit integration)
    setInterval(function() {
        if (window.neurorVoiceTranscript && window.neurorVoiceTimestamp) {
            const age = Date.now() - window.neurorVoiceTimestamp;
            if (age < 5000) {  // Only recent transcripts
                const el = document.getElementById('transcript-output');
                if (el) el.textContent = window.neurorVoiceTranscript;
            }
        }
    }, 500);

    initRecognition();
    document.getElementById('voice-status').textContent = '◌ Ready — Click mic to speak';
})();
</script>
"""


def get_voice_ui_html(tts_text: str = "", status: str = "◌ Ready") -> str:
    """Generate the voice interface HTML widget."""
    return f"""
<div id="voice-widget" style="
    background: #16161f;
    border: 1px solid #1e1e2e;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    font-family: 'Space Mono', monospace;
">
    <!-- Status -->
    <div id="voice-status" style="
        font-size: 0.72rem;
        color: #7c3aed;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        margin-bottom: 1rem;
        min-height: 1.2rem;
    ">{status}</div>

    <!-- Mic Button -->
    <button id="mic-btn" style="
        background: #7c3aed;
        border: none;
        border-radius: 50%;
        width: 72px;
        height: 72px;
        font-size: 1.8rem;
        cursor: pointer;
        transition: all 0.2s;
        box-shadow: 0 0 0 0 rgba(124,58,237,0.4);
        animation: pulse-ring 2s infinite;
        display: block;
        margin: 0 auto 1rem;
    ">🎙</button>

    <!-- Interim/Final Transcript -->
    <div id="interim-text" style="
        font-size: 0.85rem;
        color: #94a3b8;
        min-height: 2rem;
        padding: 0.5rem 0;
        font-family: 'DM Sans', sans-serif;
        font-style: italic;
    "></div>

    <!-- TTS Output -->
    <div id="tts-text" style="display:none;">{tts_text}</div>

    <!-- Hidden transcript output for Streamlit polling -->
    <div id="transcript-output" style="display:none;"></div>

    <style>
    @keyframes pulse-ring {{
        0% {{ box-shadow: 0 0 0 0 rgba(124,58,237,0.4); }}
        70% {{ box-shadow: 0 0 0 12px rgba(124,58,237,0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(124,58,237,0); }}
    }}
    #mic-btn:hover {{ transform: scale(1.08); }}
    </style>
</div>
"""
