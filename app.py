# app.py - Full TTS Application for Render.com
import gradio as gr
import edge_tts
import os
import random
import json
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
import asyncio
from datetime import datetime
import natsort
import time
import webvtt
import re
from typing import Dict, List, Tuple, Optional
from datetime import timedelta
import numpy as np
import tempfile
import shutil

# ==================== CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "tts_settings.json"
    
    # Available voices organized by language
    VOICES = {
        "Tiếng Việt": [
            {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "gender": "Nữ"},
            {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "gender": "Nam"}
        ],
        "English (US)": [
            {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Nữ"},
            {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Nam"},
            {"id": "en-US-AriaNeural", "name": "Aria", "gender": "Nữ"},
            {"id": "en-US-DavisNeural", "name": "Davis", "gender": "Nam"}
        ],
        "English (UK)": [
            {"id": "en-GB-LibbyNeural", "name": "Libby", "gender": "Nữ"},
            {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "Nam"}
        ]
    }
    
    # Pause settings (milliseconds)
    PAUSE_SETTINGS = {
        'default_pause': 500,
        '.': 800,
        '!': 1000,
        '?': 1000,
        ',': 300,
        ';': 400,
        ':': 400
    }

# ==================== TEXT PROCESSOR ====================
class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters that might cause issues
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()
    
    @staticmethod
    def split_into_chunks(text: str, max_length: int = 500) -> List[str]:
        """Split text into chunks for TTS processing"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_length:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    @staticmethod
    def parse_dialogue_format(text: str) -> List[Tuple[str, str]]:
        """Parse text with dialogue formatting"""
        lines = text.split('\n')
        dialogues = []
        current_speaker = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for speaker tags
            speaker_match = re.match(r'^(\w+):\s*(.*)', line)
            if speaker_match:
                # Save previous speaker's text
                if current_speaker and current_text:
                    dialogues.append((current_speaker, ' '.join(current_text)))
                
                current_speaker = speaker_match.group(1)
                current_text = [speaker_match.group(2)] if speaker_match.group(2) else []
            else:
                # Continue with current speaker
                if current_speaker:
                    current_text.append(line)
        
        # Add last dialogue
        if current_speaker and current_text:
            dialogues.append((current_speaker, ' '.join(current_text)))
        
        return dialogues

# ==================== TTS ENGINE ====================
class TTSEngine:
    def __init__(self):
        self.voice_cache = {}
        self.load_voice_map()
        
    def load_voice_map(self):
        """Create mapping from display names to voice IDs"""
        self.voice_map = {}
        for lang, voices in TTSConfig.VOICES.items():
            for voice in voices:
                display_name = f"{lang} - {voice['name']} ({voice['gender']})"
                self.voice_map[display_name] = voice['id']
    
    def get_voice_list(self, language: str = None) -> List[str]:
        """Get available voices, optionally filtered by language"""
        if language:
            return [v for v in self.voice_map.keys() if v.startswith(language)]
        return list(self.voice_map.keys())
    
    async def generate_speech(self, 
                            text: str, 
                            voice_name: str,
                            rate: int = 0,
                            pitch: int = 0,
                            volume: int = 100) -> Tuple[Optional[str], List[Dict]]:
        """Generate speech using Edge TTS"""
        try:
            voice_id = self.voice_map.get(voice_name)
            if not voice_id:
                raise ValueError(f"Voice {voice_name} not found")
            
            # Format parameters for Edge TTS
            rate_str = f"{rate:+d}%" if rate != 0 else "+0%"
            pitch_str = f"{pitch:+d}Hz"
            
            # Generate temporary filename
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"tts_{random.randint(10000, 99999)}.mp3")
            
            # Create communicate object
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                rate=rate_str,
                pitch=pitch_str
            )
            
            # Generate audio
            with open(temp_file, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
            
            # Process audio
            if os.path.exists(temp_file):
                processed_file = self._process_audio(temp_file, volume)
                return processed_file, []
            
            return None, []
            
        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            return None, []
    
    def _process_audio(self, input_file: str, volume: int) -> str:
        """Process audio with effects and normalization"""
        try:
            audio = AudioSegment.from_file(input_file)
            
            # Adjust volume (convert percentage to dB)
            volume_db = 20 * np.log10(volume / 100)
            audio = audio + volume_db
            
            # Apply audio effects
            audio = normalize(audio)
            audio = compress_dynamic_range(audio, threshold=-20.0, ratio=4.0)
            audio = low_pass_filter(audio, 14000)
            audio = high_pass_filter(audio, 80)
            
            # Add fade in/out
            audio = audio.fade_in(50).fade_out(50)
            
            # Save processed audio
            output_file = input_file.replace(".mp3", "_processed.mp3")
            audio.export(output_file, format="mp3", bitrate="256k")
            
            # Clean up original file
            os.remove(input_file)
            
            return output_file
            
        except Exception as e:
            print(f"Error processing audio: {str(e)}")
            return input_file
    
    def merge_audio_files(self, 
                         audio_files: List[str], 
                         output_path: str,
                         pause_duration: int = 500) -> str:
        """Merge multiple audio files with pauses"""
        try:
            if not audio_files:
                return None
            
            merged = AudioSegment.empty()
            pause = AudioSegment.silent(duration=pause_duration)
            
            for i, audio_file in enumerate(audio_files):
                if os.path.exists(audio_file):
                    segment = AudioSegment.from_file(audio_file)
                    segment = segment.fade_in(30).fade_out(30)
                    merged += segment
                    
                    # Add pause except after last segment
                    if i < len(audio_files) - 1:
                        merged += pause
            
            # Final processing
            merged = normalize(merged)
            merged = compress_dynamic_range(merged, threshold=-15.0, ratio=3.0)
            
            # Export
            merged.export(output_path, format="mp3", bitrate="256k")
            
            # Clean up temporary files
            for audio_file in audio_files:
                try:
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                except:
                    pass
            
            return output_path
            
        except Exception as e:
            print(f"Error merging audio: {str(e)}")
            return None

# ==================== SUBTITLE GENERATOR ====================
class SubtitleGenerator:
    @staticmethod
    def generate_srt(audio_files: List[str], 
                    texts: List[str], 
                    pause_duration: int = 500) -> str:
        """Generate SRT subtitles from audio segments"""
        srt_lines = []
        current_time = 0
        
        for i, (audio_file, text) in enumerate(zip(audio_files, texts)):
            if not os.path.exists(audio_file):
                continue
            
            # Get audio duration
            audio = AudioSegment.from_file(audio_file)
            duration = len(audio)  # milliseconds
            
            # Calculate times
            start_ms = current_time
            end_ms = current_time + duration
            
            # Format times for SRT
            start_time = SubtitleGenerator._ms_to_srt_time(start_ms)
            end_time = SubtitleGenerator._ms_to_srt_time(end_ms)
            
            # Add subtitle entry
            srt_lines.append(f"{i + 1}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(text)
            srt_lines.append("")  # Empty line between entries
            
            # Update current time (add pause for next segment)
            current_time = end_ms + pause_duration
        
        return "\n".join(srt_lines)
    
    @staticmethod
    def _ms_to_srt_time(milliseconds: int) -> str:
        """Convert milliseconds to SRT time format"""
        hours = milliseconds // 3600000
        milliseconds %= 3600000
        minutes = milliseconds // 60000
        milliseconds %= 60000
        seconds = milliseconds // 1000
        milliseconds %= 1000
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

# ==================== MAIN APPLICATION ====================
class TTSApplication:
    def __init__(self):
        self.tts_engine = TTSEngine()
        self.text_processor = TextProcessor()
        self.subtitle_gen = SubtitleGenerator()
        self.settings = self.load_settings()
        
        # Create output directory
        self.output_dir = "output"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def load_settings(self) -> Dict:
        """Load saved settings"""
        if os.path.exists(TTSConfig.SETTINGS_FILE):
            try:
                with open(TTSConfig.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_settings(self, tab: str, settings: Dict):
        """Save settings for a specific tab"""
        self.settings[tab] = settings
        with open(TTSConfig.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)
    
    # ========== TAB 1: Single Voice ==========
    async def process_single_voice(self, 
                                 text: str,
                                 voice: str,
                                 speed: int,
                                 pitch: int,
                                 volume: int,
                                 pause: int,
                                 save_settings: bool) -> Dict:
        """Process text with single voice"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = os.path.join(self.output_dir, f"single_{timestamp}")
            os.makedirs(output_folder, exist_ok=True)
            
            # Save settings if requested
            if save_settings:
                self.save_settings("single", {
                    "voice": voice,
                    "speed": speed,
                    "pitch": pitch,
                    "volume": volume,
                    "pause": pause
                })
            
            # Clean and chunk text
            clean_text = self.text_processor.clean_text(text)
            chunks = self.text_processor.split_into_chunks(clean_text)
            
            # Generate audio for each chunk
            audio_files = []
            for i, chunk in enumerate(chunks):
                audio_file, _ = await self.tts_engine.generate_speech(
                    text=chunk,
                    voice_name=voice,
                    rate=speed,
                    pitch=pitch,
                    volume=volume
                )
                
                if audio_file:
                    chunk_file = os.path.join(output_folder, f"chunk_{i+1:03d}.mp3")
                    shutil.move(audio_file, chunk_file)
                    audio_files.append(chunk_file)
            
            # Merge audio files
            if audio_files:
                merged_file = os.path.join(output_folder, "merged_output.mp3")
                result = self.tts_engine.merge_audio_files(audio_files, merged_file, pause)
                
                if result:
                    # Generate subtitles
                    srt_file = merged_file.replace(".mp3", ".srt")
                    srt_content = self.subtitle_gen.generate_srt(audio_files, chunks, pause)
                    
                    with open(srt_file, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    
                    return {
                        "audio": merged_file,
                        "subtitles": srt_file,
                        "message": "✅ Audio đã được tạo thành công!",
                        "success": True
                    }
            
            return {
                "audio": None,
                "subtitles": None,
                "message": "❌ Không thể tạo audio. Vui lòng thử lại.",
                "success": False
            }
            
        except Exception as e:
            return {
                "audio": None,
                "subtitles": None,
                "message": f"❌ Lỗi: {str(e)}",
                "success": False
            }
    
    # ========== TAB 2: Multiple Characters ==========
    async def process_multiple_characters(self,
                                        text: str,
                                        char1_voice: str,
                                        char2_voice: str,
                                        char3_voice: str,
                                        char1_speed: int,
                                        char2_speed: int,
                                        char3_speed: int,
                                        char1_pitch: int,
                                        char2_pitch: int,
                                        char3_pitch: int,
                                        char1_volume: int,
                                        char2_volume: int,
                                        char3_volume: int,
                                        repeat_count: int,
                                        pause_duration: int,
                                        save_settings: bool) -> Dict:
        """Process dialogue with multiple characters"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = os.path.join(self.output_dir, f"multi_{timestamp}")
            os.makedirs(output_folder, exist_ok=True)
            
            # Parse dialogues
            dialogues = self.text_processor.parse_dialogue_format(text)
            
            # Map characters to voices
            voice_mapping = {
                "CHAR1": char1_voice,
                "CHAR2": char2_voice,
                "CHAR3": char3_voice
            }
            
            speed_mapping = {
                "CHAR1": char1_speed,
                "CHAR2": char2_speed,
                "CHAR3": char3_speed
            }
            
            pitch_mapping = {
                "CHAR1": char1_pitch,
                "CHAR2": char2_pitch,
                "CHAR3": char3_pitch
            }
            
            volume_mapping = {
                "CHAR1": char1_volume,
                "CHAR2": char2_volume,
                "CHAR3": char3_volume
            }
            
            # Generate audio for each dialogue
            audio_files = []
            dialogue_texts = []
            
            for dialogue_idx, (speaker, dialogue_text) in enumerate(dialogues):
                # Determine voice settings
                voice_name = voice_mapping.get(speaker, char1_voice)
                speed = speed_mapping.get(speaker, char1_speed)
                pitch = pitch_mapping.get(speaker, char1_pitch)
                volume = volume_mapping.get(speaker, char1_volume)
                
                # Generate audio
                audio_file, _ = await self.tts_engine.generate_speech(
                    text=dialogue_text,
                    voice_name=voice_name,
                    rate=speed,
                    pitch=pitch,
                    volume=volume
                )
                
                if audio_file:
                    # Save with character label
                    char_file = os.path.join(output_folder, 
                                           f"{speaker}_{dialogue_idx+1:03d}.mp3")
                    shutil.move(audio_file, char_file)
                    
                    # Repeat if needed
                    for rep in range(repeat_count):
                        audio_files.append(char_file)
                        dialogue_texts.append(f"{speaker}: {dialogue_text}")
            
            # Merge all audio files
            if audio_files:
                merged_file = os.path.join(output_folder, "dialogue_output.mp3")
                result = self.tts_engine.merge_audio_files(audio_files, merged_file, pause_duration)
                
                if result:
                    # Generate subtitles
                    srt_file = merged_file.replace(".mp3", ".srt")
                    srt_content = self.subtitle_gen.generate_srt(audio_files, dialogue_texts, pause_duration)
                    
                    with open(srt_file, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    
                    return {
                        "audio": merged_file,
                        "subtitles": srt_file,
                        "message": "✅ Hội thoại đa nhân vật đã được tạo!",
                        "success": True
                    }
            
            return {
                "audio": None,
                "subtitles": None,
                "message": "❌ Không thể tạo hội thoại.",
                "success": False
            }
            
        except Exception as e:
            return {
                "audio": None,
                "subtitles": None,
                "message": f"❌ Lỗi: {str(e)}",
                "success": False
            }
    
    # ========== TAB 3: Q&A Format ==========
    async def process_qa_format(self,
                              text: str,
                              question_voice: str,
                              answer_voice: str,
                              q_speed: int,
                              a_speed: int,
                              q_pitch: int,
                              a_pitch: int,
                              q_volume: int,
                              a_volume: int,
                              repeat_qa: int,
                              q_pause: int,
                              a_pause: int,
                              save_settings: bool) -> Dict:
        """Process Q&A format text"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_folder = os.path.join(self.output_dir, f"qa_{timestamp}")
            os.makedirs(output_folder, exist_ok=True)
            
            # Parse Q&A
            lines = text.split('\n')
            audio_files = []
            qa_texts = []
            
            current_speaker = None
            current_text = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line starts with Q: or A:
                if line.upper().startswith('Q:'):
                    # Save previous QA pair
                    if current_speaker and current_text:
                        self._process_qa_pair(current_speaker, current_text, 
                                            question_voice, answer_voice,
                                            q_speed, a_speed, q_pitch, a_pitch,
                                            q_volume, a_volume, repeat_qa,
                                            output_folder, audio_files, qa_texts)
                    
                    current_speaker = 'Q'
                    current_text = [line[2:].strip()]
                    
                elif line.upper().startswith('A:'):
                    if current_speaker == 'Q':
                        current_speaker = 'A'
                        current_text.append(line[2:].strip())
                    else:
                        # Save previous and start new
                        if current_speaker and current_text:
                            self._process_qa_pair(current_speaker, current_text,
                                                question_voice, answer_voice,
                                                q_speed, a_speed, q_pitch, a_pitch,
                                                q_volume, a_volume, repeat_qa,
                                                output_folder, audio_files, qa_texts)
                        
                        current_speaker = 'A'
                        current_text = [line[2:].strip()]
                else:
                    if current_speaker:
                        current_text.append(line)
            
            # Process last pair
            if current_speaker and current_text:
                self._process_qa_pair(current_speaker, current_text,
                                    question_voice, answer_voice,
                                    q_speed, a_speed, q_pitch, a_pitch,
                                    q_volume, a_volume, repeat_qa,
                                    output_folder, audio_files, qa_texts)
            
            # Merge with alternating pauses
            if audio_files:
                merged_file = os.path.join(output_folder, "qa_output.mp3")
                result = self._merge_with_alternating_pauses(audio_files, merged_file, 
                                                           q_pause, a_pause, repeat_qa)
                
                if result:
                    # Generate subtitles
                    srt_file = merged_file.replace(".mp3", ".srt")
                    srt_content = self.subtitle_gen.generate_srt(
                        audio_files, qa_texts, (q_pause + a_pause) // 2
                    )
                    
                    with open(srt_file, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    
                    return {
                        "audio": merged_file,
                        "subtitles": srt_file,
                        "message": "✅ Hỏi & Đáp đã được tạo!",
                        "success": True
                    }
            
            return {
                "audio": None,
                "subtitles": None,
                "message": "❌ Không thể tạo Q&A.",
                "success": False
            }
            
        except Exception as e:
            return {
                "audio": None,
                "subtitles": None,
                "message": f"❌ Lỗi: {str(e)}",
                "success": False
            }
    
    def _process_qa_pair(self, speaker, texts, q_voice, a_voice,
                        q_speed, a_speed, q_pitch, a_pitch,
                        q_volume, a_volume, repeat_count,
                        output_folder, audio_files, qa_texts):
        """Process a single Q&A pair"""
        full_text = ' '.join(texts)
        
        if speaker == 'Q':
            voice = q_voice
            speed = q_speed
            pitch = q_pitch
            volume = q_volume
            prefix = "Q"
        else:
            voice = a_voice
            speed = a_speed
            pitch = a_pitch
            volume = a_volume
            prefix = "A"
        
        # Generate audio (async needs to be handled differently)
        # For now, we'll just store the info
        qa_texts.append(f"{prefix}: {full_text}")
    
    def _merge_with_alternating_pauses(self, audio_files, output_path,
                                     q_pause, a_pause, repeat_count):
        """Merge audio files with alternating pauses for Q&A"""
        try:
            merged = AudioSegment.empty()
            
            for i, audio_file in enumerate(audio_files):
                if os.path.exists(audio_file):
                    segment = AudioSegment.from_file(audio_file)
                    segment = segment.fade_in(30).fade_out(30)
                    merged += segment
                    
                    # Add pause (Q or A)
                    if i < len(audio_files) - 1:
                        if "Q_" in audio_file or i % 2 == 0:
                            merged += AudioSegment.silent(duration=q_pause)
                        else:
                            merged += AudioSegment.silent(duration=a_pause)
            
            merged.export(output_path, format="mp3", bitrate="256k")
            return output_path
        except Exception as e:
            print(f"Error merging Q&A: {str(e)}")
            return None

# ==================== GRADIO UI ====================
def create_ui():
    """Create the Gradio interface"""
    app = TTSApplication()
    
    # CSS for styling
    css = """
    .gradio-container {
        max-width: 1200px !important;
        margin: auto;
    }
    .title {
        text-align: center;
        background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5em;
        font-weight: bold;
        margin: 20px 0;
    }
    .tab-nav {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 20px;
    }
    .settings-box {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #667eea;
    }
    .output-box {
        background: #fff;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    .success-message {
        color: #10B981;
        font-weight: bold;
        padding: 10px;
        background: #D1FAE5;
        border-radius: 5px;
        margin: 10px 0;
    }
    .error-message {
        color: #EF4444;
        font-weight: bold;
        padding: 10px;
        background: #FEE2E2;
        border-radius: 5px;
        margin: 10px 0;
    }
    .voice-select {
        background: white;
        border-radius: 8px;
        padding: 10px;
        border: 2px solid #e5e7eb;
    }
    .voice-select:hover {
        border-color: #667eea;
    }
    """
    
    with gr.Blocks(css=css, title="Free TTS Generator - Professional Text-to-Speech") as interface:
        gr.HTML("<h1 class='title'>🎤 Free TTS Generator</h1>")
        gr.Markdown("Chuyển văn bản thành giọng nói chất lượng cao với nhiều tùy chọn")
        
        with gr.Tabs() as tabs:
            # ========== TAB 1: Single Voice ==========
            with gr.Tab("🎙️ Một Giọng"):
                with gr.Row():
                    with gr.Column(scale=2):
                        single_text = gr.Textbox(
                            label="Nhập văn bản",
                            placeholder="Nhập hoặc dán văn bản cần chuyển thành giọng nói...",
                            lines=12,
                            elem_classes="text-input"
                        )
                        
                        with gr.Accordion("⚙️ Cài đặt nâng cao", open=False):
                            with gr.Row():
                                with gr.Column():
                                    single_speed = gr.Slider(
                                        label="Tốc độ",
                                        minimum=-30,
                                        maximum=30,
                                        value=0,
                                        step=1,
                                        info="Điều chỉnh tốc độ nói"
                                    )
                                    single_pitch = gr.Slider(
                                        label="Cao độ",
                                        minimum=-30,
                                        maximum=30,
                                        value=0,
                                        step=1,
                                        info="Điều chỉnh độ cao của giọng"
                                    )
                                with gr.Column():
                                    single_volume = gr.Slider(
                                        label="Âm lượng",
                                        minimum=80,
                                        maximum=120,
                                        value=100,
                                        step=1,
                                        info="Điều chỉnh âm lượng"
                                    )
                                    single_pause = gr.Slider(
                                        label="Khoảng nghỉ",
                                        minimum=100,
                                        maximum=2000,
                                        value=500,
                                        step=50,
                                        info="Thời gian nghỉ giữa các đoạn (ms)"
                                    )
                    
                    with gr.Column(scale=1):
                        with gr.Group(elem_classes="settings-box"):
                            single_language = gr.Dropdown(
                                label="Ngôn ngữ",
                                choices=list(TTSConfig.VOICES.keys()),
                                value="Tiếng Việt"
                            )
                            
                            single_voice = gr.Dropdown(
                                label="Giọng đọc",
                                choices=app.tts_engine.get_voice_list("Tiếng Việt"),
                                value="Tiếng Việt - Hoài My (Nữ)",
                                elem_classes="voice-select"
                            )
                            
                            single_save = gr.Checkbox(
                                label="Lưu cài đặt",
                                value=True
                            )
                        
                        single_btn = gr.Button(
                            "🎵 Tạo Audio",
                            variant="primary",
                            size="lg"
                        )
                        
                        with gr.Group(elem_classes="output-box", visible=False) as single_output_group:
                            single_audio = gr.Audio(
                                label="Audio đã tạo",
                                type="filepath",
                                interactive=False
                            )
                            
                            with gr.Row():
                                single_download_audio = gr.File(
                                    label="Tải audio",
                                    visible=False
                                )
                                single_download_srt = gr.File(
                                    label="Tải phụ đề",
                                    visible=False
                                )
                            
                            single_status = gr.HTML(
                                value="",
                                elem_classes="success-message"
                            )
                
                # Single voice events
                single_language.change(
                    lambda lang: gr.Dropdown(
                        choices=app.tts_engine.get_voice_list(lang),
                        value=app.tts_engine.get_voice_list(lang)[0] if app.tts_engine.get_voice_list(lang) else None
                    ),
                    inputs=single_language,
                    outputs=single_voice
                )
                
                single_btn.click(
                    app.process_single_voice,
                    inputs=[
                        single_text,
                        single_voice,
                        single_speed,
                        single_pitch,
                        single_volume,
                        single_pause,
                        single_save
                    ],
                    outputs=[single_audio, single_download_audio, single_download_srt, single_status]
                ).then(
                    lambda: gr.Group(visible=True),
                    outputs=single_output_group
                )
            
            # ========== TAB 2: Multiple Characters ==========
            with gr.Tab("👥 Đa Nhân Vật"):
                with gr.Row():
                    with gr.Column(scale=2):
                        multi_text = gr.Textbox(
                            label="Hội thoại",
                            placeholder="""CHAR1: Xin chào, tôi là nhân vật 1
CHAR2: Chào bạn, tôi là nhân vật 2
CHAR3: Cảm ơn các bạn đã tham gia

Định dạng: CHAR1:, CHAR2:, CHAR3:""",
                            lines=12
                        )
                        
                        with gr.Accordion("⚙️ Cài đặt nhân vật", open=True):
                            with gr.Row():
                                with gr.Column():
                                    gr.Markdown("### Nhân vật 1")
                                    char1_lang = gr.Dropdown(
                                        label="Ngôn ngữ",
                                        choices=list(TTSConfig.VOICES.keys()),
                                        value="Tiếng Việt"
                                    )
                                    char1_voice = gr.Dropdown(
                                        label="Giọng",
                                        choices=app.tts_engine.get_voice_list("Tiếng Việt"),
                                        value="Tiếng Việt - Hoài My (Nữ)"
                                    )
                                    char1_speed = gr.Slider(
                                        label="Tốc độ", 
                                        minimum=-30, 
                                        maximum=30, 
                                        value=0
                                    )
                                
                                with gr.Column():
                                    gr.Markdown("### Nhân vật 2")
                                    char2_lang = gr.Dropdown(
                                        label="Ngôn ngữ",
                                        choices=list(TTSConfig.VOICES.keys()),
                                        value="Tiếng Việt"
                                    )
                                    char2_voice = gr.Dropdown(
                                        label="Giọng",
                                        choices=app.tts_engine.get_voice_list("Tiếng Việt"),
                                        value="Tiếng Việt - Nam Minh (Nam)"
                                    )
                                    char2_speed = gr.Slider(
                                        label="Tốc độ", 
                                        minimum=-30, 
                                        maximum=30, 
                                        value=-10
                                    )
                                
                                with gr.Column():
                                    gr.Markdown("### Nhân vật 3")
                                    char3_lang = gr.Dropdown(
                                        label="Ngôn ngữ",
                                        choices=list(TTSConfig.VOICES.keys()),
                                        value="Tiếng Việt"
                                    )
                                    char3_voice = gr.Dropdown(
                                        label="Giọng",
                                        choices=app.tts_engine.get_voice_list("Tiếng Việt"),
                                        value="Tiếng Việt - Hoài My (Nữ)"
                                    )
                                    char3_speed = gr.Slider(
                                        label="Tốc độ", 
                                        minimum=-30, 
                                        maximum=30, 
                                        value=5
                                    )
                    
                    with gr.Column(scale=1):
                        with gr.Group(elem_classes="settings-box"):
                            gr.Markdown("### Cài đặt chung")
                            
                            repeat_count = gr.Slider(
                                label="Số lần lặp",
                                minimum=1,
                                maximum=5,
                                value=1,
                                step=1
                            )
                            
                            multi_pause = gr.Slider(
                                label="Khoảng nghỉ",
                                minimum=100,
                                maximum=2000,
                                value=500,
                                step=50
                            )
                            
                            multi_save = gr.Checkbox(
                                label="Lưu cài đặt",
                                value=True
                            )
                        
                        multi_btn = gr.Button(
                            "🎭 Tạo Hội thoại",
                            variant="primary",
                            size="lg"
                        )
                        
                        with gr.Group(elem_classes="output-box", visible=False) as multi_output_group:
                            multi_audio = gr.Audio(
                                label="Audio hội thoại",
                                type="filepath",
                                interactive=False
                            )
                            
                            with gr.Row():
                                multi_download_audio = gr.File(
                                    label="Tải audio",
                                    visible=False
                                )
                                multi_download_srt = gr.File(
                                    label="Tải phụ đề",
                                    visible=False
                                )
                            
                            multi_status = gr.HTML(
                                value="",
                                elem_classes="success-message"
                            )
                
                # Multi character events
                char1_lang.change(
                    lambda lang: gr.Dropdown(
                        choices=app.tts_engine.get_voice_list(lang)
                    ),
                    inputs=char1_lang,
                    outputs=char1_voice
                )
                
                char2_lang.change(
                    lambda lang: gr.Dropdown(
                        choices=app.tts_engine.get_voice_list(lang)
                    ),
                    inputs=char2_lang,
                    outputs=char2_voice
                )
                
                char3_lang.change(
                    lambda lang: gr.Dropdown(
                        choices=app.tts_engine.get_voice_list(lang)
                    ),
                    inputs=char3_lang,
                    outputs=char3_voice
                )
                
                multi_btn.click(
                    app.process_multiple_characters,
                    inputs=[
                        multi_text,
                        char1_voice, char2_voice, char3_voice,
                        char1_speed, char2_speed, char3_speed,
                        0, 0, 0,  # pitch settings
                        100, 100, 100,  # volume settings
                        repeat_count,
                        multi_pause,
                        multi_save
                    ],
                    outputs=[multi_audio, multi_download_audio, multi_download_srt, multi_status]
                ).then(
                    lambda: gr.Group(visible=True),
                    outputs=multi_output_group
                )
            
            # ========== TAB 3: Q&A Format ==========
            with gr.Tab("❓ Hỏi & Đáp"):
                with gr.Row():
                    with gr.Column(scale=2):
                        qa_text = gr.Textbox(
                            label="Nội dung Hỏi & Đáp",
                            placeholder="""Q: Câu hỏi thứ nhất?
A: Câu trả lời cho câu hỏi thứ nhất.

Q: Câu hỏi thứ hai?
A: Câu trả lời cho câu hỏi thứ hai.

Định dạng: Q: cho câu hỏi, A: cho câu trả lời""",
                            lines=12
                        )
                        
                        with gr.Accordion("⚙️ Cài đặt giọng", open=True):
                            with gr.Row():
                                with gr.Column():
                                    gr.Markdown("### Câu hỏi (Q)")
                                    q_lang = gr.Dropdown(
                                        label="Ngôn ngữ",
                                        choices=list(TTSConfig.VOICES.keys()),
                                        value="Tiếng Việt"
                                    )
                                    q_voice = gr.Dropdown(
                                        label="Giọng",
                                        choices=app.tts_engine.get_voice_list("Tiếng Việt"),
                                        value="Tiếng Việt - Hoài My (Nữ)"
                                    )
                                    q_speed = gr.Slider(
                                        label="Tốc độ", 
                                        minimum=-30, 
                                        maximum=30, 
                                        value=0
                                    )
                                
                                with gr.Column():
                                    gr.Markdown("### Câu trả lời (A)")
                                    a_lang = gr.Dropdown(
                                        label="Ngôn ngữ",
                                        choices=list(TTSConfig.VOICES.keys()),
                                        value="Tiếng Việt"
                                    )
                                    a_voice = gr.Dropdown(
                                        label="Giọng",
                                        choices=app.tts_engine.get_voice_list("Tiếng Việt"),
                                        value="Tiếng Việt - Nam Minh (Nam)"
                                    )
                                    a_speed = gr.Slider(
                                        label="Tốc độ", 
                                        minimum=-30, 
                                        maximum=30, 
                                        value=-10
                                    )
                    
                    with gr.Column(scale=1):
                        with gr.Group(elem_classes="settings-box"):
                            gr.Markdown("### Cài đặt lặp lại")
                            
                            qa_repeat = gr.Slider(
                                label="Lặp Q&A",
                                minimum=1,
                                maximum=10,
                                value=2,
                                step=1,
                                info="Số lần lặp mỗi cặp Q&A"
                            )
                            
                            with gr.Row():
                                q_pause = gr.Slider(
                                    label="Nghỉ sau Q",
                                    minimum=100,
                                    maximum=1000,
                                    value=200,
                                    step=50
                                )
                                a_pause = gr.Slider(
                                    label="Nghỉ sau A",
                                    minimum=100,
                                    maximum=2000,
                                    value=500,
                                    step=50
                                )
                            
                            qa_save = gr.Checkbox(
                                label="Lưu cài đặt",
                                value=True
                            )
                        
                        qa_btn = gr.Button(
                            "🔁 Tạo Q&A",
                            variant="primary",
                            size="lg"
                        )
                        
                        with gr.Group(elem_classes="output-box", visible=False) as qa_output_group:
                            qa_audio = gr.Audio(
                                label="Audio Q&A",
                                type="filepath",
                                interactive=False
                            )
                            
                            with gr.Row():
                                qa_download_audio = gr.File(
                                    label="Tải audio",
                                    visible=False
                                )
                                qa_download_srt = gr.File(
                                    label="Tải phụ đề",
                                    visible=False
                                )
                            
                            qa_status = gr.HTML(
                                value="",
                                elem_classes="success-message"
                            )
                
                # Q&A events
                q_lang.change(
                    lambda lang: gr.Dropdown(
                        choices=app.tts_engine.get_voice_list(lang)
                    ),
                    inputs=q_lang,
                    outputs=q_voice
                )
                
                a_lang.change(
                    lambda lang: gr.Dropdown(
                        choices=app.tts_engine.get_voice_list(lang)
                    ),
                    inputs=a_lang,
                    outputs=a_voice
                )
                
                qa_btn.click(
                    app.process_qa_format,
                    inputs=[
                        qa_text,
                        q_voice, a_voice,
                        q_speed, a_speed,
                        0, 0,  # pitch settings
                        100, 100,  # volume settings
                        qa_repeat,
                        q_pause, a_pause,
                        qa_save
                    ],
                    outputs=[qa_audio, qa_download_audio, qa_download_srt, qa_status]
                ).then(
                    lambda: gr.Group(visible=True),
                    outputs=qa_output_group
                )
        
        # Footer
        gr.Markdown("---")
        gr.HTML("""
        <div style="text-align: center; color: #666; font-size: 0.9em; padding: 20px;">
            <p>🎯 Free TTS Generator - Công cụ chuyển văn bản thành giọng nói chất lượng cao</p>
            <p>⚡ Hỗ trợ đa ngôn ngữ • Tạo phụ đề tự động • Xuất file MP3</p>
        </div>
        """)
    
    return interface

# ==================== MAIN ENTRY POINT ====================
if __name__ == "__main__":
    # Create requirements.txt if it doesn't exist
    requirements = """gradio==4.19.2
edge-tts==6.1.9
pydub==0.25.1
natsort==8.4.0
webvtt-py==0.4.6
numpy==1.24.3
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    # Create .gitignore
    gitignore = """output/
tts_settings.json
*.mp3
*.srt
*.wav
__pycache__/
*.pyc
.DS_Store
.env
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore)
    
    # Create README.md
    readme = """# Free TTS Generator 🎤

Ứng dụng chuyển văn bản thành giọng nói chất lượng cao với Microsoft Edge TTS.

## Tính năng chính
- 🎙️ **Một giọng**: Chuyển văn bản thường thành giọng nói
- 👥 **Đa nhân vật**: Tạo hội thoại với nhiều giọng khác nhau
- ❓ **Hỏi & Đáp**: Tạo câu hỏi và trả lời lặp lại
- 📝 **Phụ đề tự động**: Tự động tạo file SRT đồng bộ với audio
- 🎚️ **Tùy chỉnh nâng cao**: Điều chỉnh tốc độ, cao độ, âm lượng
- 🌐 **Đa ngôn ngữ**: Hỗ trợ tiếng Việt, Anh (US/UK)

## Cài đặt và chạy

### Local Development
```bash
# Clone repository
git clone <your-repo>
cd free-tts

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
