# import pyaudio
import wave
from datetime import datetime
from faster_whisper import WhisperModel
import os
import yaml
import time
import threading
from pathlib import Path
import os
import wave
from datetime import datetime

class AudioMonitor:
    def __init__(self, config, room_name=None, session_timestamp: str | None = None):
        self.config = config['detection']['audio_monitoring']
        # Standardize session data location under project root: /app/session_data
        # __file__ is /app/code/transcript_generator.py → parents[1] is /app
        # This matches entrypoint.sh and report/LLM readers that use ./session_data
        project_root = Path(__file__).resolve().parents[1]  # /app
        base_session_dir = project_root / "session_data"
        self.recording_dir = str(base_session_dir / "recordings")
        os.makedirs(self.recording_dir, exist_ok=True)
        
        # Create transcripts_doc directory if it doesn't exist
        self.transcripts_dir = str(base_session_dir / "transcripts_doc")
        os.makedirs(self.transcripts_dir, exist_ok=True)
        
        self.room_name = room_name or "unknown_room"
        self.session_timestamp = session_timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.transcript_log = ""

    def _get_audio_duration_seconds(self, audio_path: str) -> float | None:
        """Compute audio duration (seconds) for .wav files."""
        try:
            if audio_path.lower().endswith(".wav"):
                with wave.open(audio_path, 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    if rate > 0:
                        return frames / float(rate)
        except Exception:
            pass
        return None

    def _format_time(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h:
            return f"{h:d}h {m:02d}m {s:02d}s"
        if m:
            return f"{m:d}m {s:02d}s"
        return f"{s:d}s"

    def _print_progress(self, progress: float | None, elapsed: float):
        """Render progress bar with elapsed time only (no ETA)."""
        bar_len = 40  # wider bar
        if progress is None:
            filled_len = 0
            pct_text = "--%"
        else:
            progress = max(0.0, min(1.0, progress))
            filled_len = int(bar_len * progress)
            pct_text = f"{int(progress * 100):3d}%"
        bar = "█" * filled_len + "-" * (bar_len - filled_len)
        elapsed_txt = self._format_time(elapsed)
        print(f"\r📝 Transcribing... [{bar}] {pct_text} | Elapsed: {elapsed_txt}", end="", flush=True)

    def get_transcript_text(self):
        """Transcribe entire recorded audio after the meeting ends."""
        if not self.config['whisper_enabled']:
            return "Transcription disabled."

        try:
            model = WhisperModel(
                self.config['whisper_model'],
                device="cpu",
                compute_type="int8"
            )

            total_duration = self._get_audio_duration_seconds(getattr(self, 'audio_file', ''))
            start_time = time.time()
            collected_texts = []
            progress_state = {"progress": 0.0}

            self._print_progress(0.0, 0.0)

            def _worker():
                try:
                    segments, _info = model.transcribe(self.audio_file, language='en')
                    if getattr(_info, 'duration', None):
                        progress_state['total'] = float(_info.duration)
                    for seg in segments:
                        collected_texts.append(seg.text.strip())
                        local_total = progress_state.get('total') or total_duration
                        if local_total and local_total > 0:
                            progress_state["progress"] = min(1.0, (seg.end or 0.0) / local_total)
                        else:
                            progress_state["progress"] = None
                except Exception:
                    pass

            t = threading.Thread(target=_worker, daemon=True)
            t.start()

            while t.is_alive():
                elapsed = time.time() - start_time
                progress = progress_state.get("progress")
                self._print_progress(progress, elapsed)
                time.sleep(60)

            elapsed_final = time.time() - start_time
            self._print_progress(1.0, elapsed_final)
            print()

            self.transcript_log = "\n".join(collected_texts)

            transcript_filename = f"transcript_{self.room_name}_{self.session_timestamp}.txt"
            transcript_path = os.path.join(self.transcripts_dir, transcript_filename)

            try:
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(f"Room: {self.room_name}\n")
                    f.write(f"Session: {self.session_timestamp}\n")
                    f.write(f"Audio File: {self.audio_file}\n")
                    f.write("-" * 50 + "\n\n")
                    f.write(self.transcript_log)
                print(f" Transcript saved to: {transcript_path}")
            except Exception as save_error:
                print(f" Failed to save transcript file: {save_error}")
            
            return self.transcript_log

        except Exception as e:
            print(f" Transcription failed: {e}")
            return "Transcription failed."
