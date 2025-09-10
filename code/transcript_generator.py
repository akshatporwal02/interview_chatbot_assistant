import pyaudio
import wave
from datetime import datetime
from faster_whisper import WhisperModel
import os
import yaml
import time

class AudioMonitor:
    def __init__(self, config, room_name=None, session_timestamp: str | None = None):
        self.config = config['detection']['audio_monitoring']
        # self.sample_rate = self.config['sample_rate']
        # self.chunk_size = self.config['chunk_size']
        self.recording_dir = "./session_data/recordings"
        os.makedirs(self.recording_dir, exist_ok=True)
        
        # Create transcripts_doc directory if it doesn't exist
        self.transcripts_dir = "./session_data/transcripts_doc"
        os.makedirs(self.transcripts_dir, exist_ok=True)
        
        # Store room name for transcript filename
        self.room_name = room_name or "unknown_room"
        
        # Generate session timestamp for unique file naming
        self.session_timestamp = session_timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        
        self.transcript_log = ""
        


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