import pyaudio
import wave
import threading
from datetime import datetime
from faster_whisper import WhisperModel
import os
import yaml
import time

class AudioMonitor:
    def __init__(self, config, room_name=None, session_timestamp: str | None = None):
        self.config = config['detection']['audio_monitoring']
        self.sample_rate = self.config['sample_rate']
        self.chunk_size = self.config['chunk_size']
        self.input_device_index = self.config['input_device_index']
        self.duration_minutes = self.config.get('duration_minutes', 60)
        self.recording_dir = "./session_data/recordings"
        os.makedirs(self.recording_dir, exist_ok=True)
        
        # Create transcripts_doc directory if it doesn't exist
        self.transcripts_dir = "./session_data/transcripts_doc"
        os.makedirs(self.transcripts_dir, exist_ok=True)
        
        # Store room name for transcript filename
        self.room_name = room_name or "unknown_room"
        
        # Generate session timestamp for unique file naming
        self.session_timestamp = session_timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Unique file for every meeting session
        self.audio_file = os.path.join(self.recording_dir, f"audio_{self.room_name}_{self.session_timestamp}.wav")

        self.running = False
        self.thread = None
        self.transcript_log = ""
        self.alert_logger = None

    def set_alert_logger(self, logger):
        """Set the alert logger for this audio monitor."""
        self.alert_logger = logger

    # def start(self):
    #     """Start audio recording in a background thread."""
    #     self.running = True
    #     self.thread = threading.Thread(target=self._record, daemon=True)
    #     self.thread.start()

    # def stop(self):
    #     """Signal to stop and wait for background recording thread to finish."""
    #     self.running = False
    #     if self.thread:
    #         self.thread.join()

    # def _record(self):
    #     """Record audio continuously until manually stopped."""
    #     print("🎙️ Audio recording started...")
    #     p = pyaudio.PyAudio()

    #     try:
    #         stream = p.open(
    #             format=pyaudio.paInt16,
    #             channels=1,
    #             rate=self.sample_rate,
    #             input=True,
    #             input_device_index=self.input_device_index,
    #             frames_per_buffer=self.chunk_size
    #         )

    #         frames = []

    #         while self.running:
    #             data = stream.read(self.chunk_size, exception_on_overflow=False)
    #             frames.append(data)

    #         stream.stop_stream()
    #         stream.close()

    #         with wave.open(self.audio_file, 'wb') as wf:
    #             wf.setnchannels(1)
    #             wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    #             wf.setframerate(self.sample_rate)
    #             wf.writeframes(b''.join(frames))

    #         print(f"✅ Audio saved to: {self.audio_file}")

    #     finally:
    #         p.terminate()

    def get_transcript_text(self):
        """Transcribe entire recorded audio after the meeting ends."""
        if not self.config['whisper_enabled']:
            return "Transcription disabled."

        print("📝 Transcribing audio with faster-whisper...")
        try:
            model = WhisperModel(
                self.config['whisper_model'],  # e.g., "base", "tiny"
                device="cpu",
                compute_type="int8"
            )

            segments, _ = model.transcribe(self.audio_file,language='en')
            self.transcript_log = "\n".join([seg.text.strip() for seg in segments])
            
            # Save transcript to transcripts_doc folder with room name
            transcript_filename = f"transcript_{self.room_name}_{self.session_timestamp}.txt"
            transcript_path = os.path.join(self.transcripts_dir, transcript_filename)
            
            try:
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(f"Room: {self.room_name}\n")
                    f.write(f"Session: {self.session_timestamp}\n")
                    f.write(f"Audio File: {self.audio_file}\n")
                    f.write("-" * 50 + "\n\n")
                    f.write(self.transcript_log)
                
                print(f"📄 Transcript saved to: {transcript_path}")
            except Exception as save_error:
                print(f"⚠️ Failed to save transcript file: {save_error}")
            
            return self.transcript_log

        except Exception as e:
            print(f"❌ Transcription failed: {e}")
            return "Transcription failed."

#     # with open('config.yaml') as f:
#     #     config = yaml.safe_load(f)
#     #     audio_monitor = AudioMonitor(config)
#     #     audio_monitor.start()
# if __name__ == "__main__":
#     config = yaml.safe_load(open("config.yaml"))
    
#     # Create monitor object
#     monitor = AudioMonitor(config)

#     # 👉 Set an existing audio file instead of recording
#     monitor.audio_file = "./recordings/audio_20250801154628.wav"  # Set your WAV file here

#     # 👇 Skip monitor.start() and stop(), since you're not recording
#     # monitor.start()
#     # time.sleep(10)
#     # monitor.stop()

#     # 🧾 Generate transcription
#     print("\n🧾 Transcript:\n", monitor.get_transcript_text())