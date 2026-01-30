
import os
import sys
import json
import re
import asyncio
import random
import time
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import io
import base64
import tempfile
import shutil

# Core dependencies
try:
    import gradio as gr
    GRADIO_AVAILABLE = True
except ImportError as e:
    print(f"Error: gradio not available: {e}")
    GRADIO_AVAILABLE = False
    sys.exit(1)

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    print("Warning: edge-tts not available")
    EDGE_TTS_AVAILABLE = False
    sys.exit(1)

# Optional dependencies
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    print("Warning: numpy not available")
    NUMPY_AVAILABLE = False

try:
    import webvtt
    WEBVTT_AVAILABLE = True
except ImportError:
    print("Warning: webvtt-py not available")
    WEBVTT_AVAILABLE = False

# ==================== CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "edge_tts_settings.json"
    
    # Voice configurations
    VOICES = {
        "vi-VN-HoaiMyNeural": {"language": "Tiếng Việt", "gender": "Nữ", "display": "HoaiMy (Nữ)"},
        "vi-VN-NamMinhNeural": {"language": "Tiếng Việt", "gender": "Nam", "display": "NamMinh (Nam)"},
        "en-US-GuyNeural": {"language": "English (US)", "gender": "Nam", "display": "Guy (Nam)"},
        "en-US-JennyNeural": {"language": "English (US)", "gender": "Nữ", "display": "Jenny (Nữ)"},
        "en-US-AvaNeural": {"language": "English (US)", "gender": "Nữ", "display": "Ava (Nữ)"},
        "en-US-AndrewNeural": {"language": "English (US)", "gender": "Nam", "display": "Andrew (Nam)"},
        "en-GB-LibbyNeural": {"language": "English (UK)", "gender": "Nữ", "display": "Libby (Nữ)"},
        "en-GB-RyanNeural": {"language": "English (UK)", "gender": "Nam", "display": "Ryan (Nam)"},
    }
    
    # Group by language for UI
    LANGUAGES = {
        "Tiếng Việt": [
            "vi-VN-HoaiMyNeural",
            "vi-VN-NamMinhNeural"
        ],
        "English (US)": [
            "en-US-GuyNeural",
            "en-US-JennyNeural",
            "en-US-AvaNeural",
            "en-US-AndrewNeural"
        ],
        "English (UK)": [
            "en-GB-LibbyNeural",
            "en-GB-RyanNeural"
        ]
    }
    
    @staticmethod
    def get_voice_display_name(voice_id: str) -> str:
        """Get display name for voice"""
        voice_info = TTSConfig.VOICES.get(voice_id, {})
        language = voice_info.get("language", "Unknown")
        display = voice_info.get("display", voice_id)
        return f"{language} - {display}"
    
    @staticmethod
    def get_default_settings():
        return {
            "single_char": {
                "language": "Tiếng Việt",
                "voice": "vi-VN-HoaiMyNeural",
                "rate": 0,
                "volume": 100,
                "pause": 500
            },
            "multi_char": {
                "language_char1": "Tiếng Việt",
                "voice_char1": "vi-VN-HoaiMyNeural",
                "language_char2": "Tiếng Việt",
                "voice_char2": "vi-VN-NamMinhNeural",
                "rate_char1": -10,
                "rate_char2": -15,
                "volume_char1": 100,
                "volume_char2": 100,
                "repeat_times": 1,
                "pause_between": 500
            },
            "dialogue": {
                "language_q": "Tiếng Việt",
                "voice_q": "vi-VN-HoaiMyNeural",
                "language_a": "Tiếng Việt",
                "voice_a": "vi-VN-NamMinhNeural",
                "rate_q": -10,
                "rate_a": -15,
                "volume_q": 100,
                "volume_a": 100,
                "repeat_times": 1,
                "pause_q": 300,
                "pause_a": 500
            }
        }

# ==================== TEXT PROCESSOR ====================
class TextProcessor:
    """Process and clean text for TTS"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Basic text cleaning"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common punctuation issues
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        return text.strip()
    
    @staticmethod
    def split_into_chunks(text: str, max_chars: int = 500) -> List[str]:
        """Split text into manageable chunks for TTS"""
        if not text:
            return []
        
        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_chars:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    @staticmethod
    def parse_dialogue(text: str) -> List[Tuple[str, str]]:
        """Parse dialogue text with Q:/A: or CHAR: format"""
        lines = text.strip().split('\n')
        dialogues = []
        current_speaker = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for speaker tags
            speaker_match = re.match(r'^(Q|A|CHAR\d+|NARRATOR):\s*(.*)$', line, re.IGNORECASE)
            if speaker_match:
                if current_speaker is not None:
                    dialogues.append((current_speaker, ' '.join(current_text)))
                
                current_speaker = speaker_match.group(1).upper()
                current_text = [speaker_match.group(2)]
            elif current_speaker is not None:
                current_text.append(line)
        
        if current_speaker is not None:
            dialogues.append((current_speaker, ' '.join(current_text)))
        
        return dialogues

# ==================== AUDIO PROCESSOR ====================
class AudioProcessor:
    """Simple audio processor without pydub"""
    
    @staticmethod
    def save_audio(audio_data: bytes, filepath: str) -> bool:
        """Save audio bytes to file"""
        try:
            with open(filepath, 'wb') as f:
                f.write(audio_data)
            return True
        except Exception as e:
            print(f"Error saving audio: {e}")
            return False
    
    @staticmethod
    def concatenate_audio_files(filepaths: List[str], output_path: str, pause_ms: int = 500) -> bool:
        """
        Concatenate multiple audio files by simply writing them sequentially
        This is a simplified version without audio processing
        """
        try:
            if not filepaths:
                return False
            
            # For MP3 files, we can concatenate them by simple byte concatenation
            # This works for edge-tts generated MP3 files
            with open(output_path, 'wb') as outfile:
                for i, filepath in enumerate(filepaths):
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as infile:
                            outfile.write(infile.read())
            
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error concatenating audio: {e}")
            return False
    
    @staticmethod
    def create_output_directory() -> str:
        """Create a timestamped output directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"output_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    @staticmethod
    def cleanup_temp_files(files: List[str]):
        """Clean up temporary files"""
        for filepath in files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                print(f"Error removing file {filepath}: {e}")

# ==================== TTS ENGINE ====================
class TTSEngine:
    """Main TTS engine using edge-tts"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.audio_processor = AudioProcessor()
    
    async def text_to_speech(self, text: str, voice: str, rate: int = 0, 
                           volume: int = 100) -> Tuple[Optional[str], List[Dict]]:
        """Convert text to speech using edge-tts"""
        if not EDGE_TTS_AVAILABLE:
            return None, []
        
        try:
            # Clean text
            text = self.text_processor.clean_text(text)
            if not text:
                return None, []
            
            # Prepare rate parameter
            rate_str = f"{rate:+d}%" if rate != 0 else "+0%"
            
            # Create communicate object
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate_str,
                pitch=0  # Fixed pitch for simplicity
            )
            
            # Generate temporary file
            temp_dir = "temp_audio"
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f"tts_{random.randint(10000, 99999)}.mp3")
            
            # Generate audio and collect subtitles
            subtitles = []
            with open(temp_file, 'wb') as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        subtitles.append({
                            "text": chunk["text"],
                            "start": chunk["offset"],
                            "end": chunk["offset"] + chunk["duration"]
                        })
            
            return temp_file, subtitles
            
        except Exception as e:
            print(f"Error in text_to_speech: {e}")
            return None, []
    
    async def generate_story_audio(self, content: str, voice: str, rate: int, 
                                 volume: int, pause_ms: int) -> Tuple[Optional[str], Optional[str], str]:
        """Generate audio for a story"""
        try:
            # Split content into sentences/chunks
            chunks = self.text_processor.split_into_chunks(content)
            if not chunks:
                return None, None, "❌ No content to process"
            
            # Generate audio for each chunk
            audio_files = []
            all_subtitles = []
            
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)}...")
                audio_file, subtitles = await self.text_to_speech(chunk, voice, rate, volume)
                
                if audio_file and os.path.exists(audio_file):
                    audio_files.append(audio_file)
                    all_subtitles.extend(subtitles)
            
            if not audio_files:
                return None, None, "❌ Failed to generate audio"
            
            # Create output directory
            output_dir = self.audio_processor.create_output_directory()
            output_audio = os.path.join(output_dir, "story.mp3")
            
            # Concatenate audio files
            success = self.audio_processor.concatenate_audio_files(audio_files, output_audio, pause_ms)
            
            if not success:
                self.audio_processor.cleanup_temp_files(audio_files)
                return None, None, "❌ Failed to merge audio"
            
            # Generate SRT file if subtitles available
            srt_file = None
            if all_subtitles and WEBVTT_AVAILABLE:
                srt_file = os.path.join(output_dir, "story.srt")
                self._generate_srt_file(all_subtitles, srt_file)
            
            # Cleanup temp files
            self.audio_processor.cleanup_temp_files(audio_files)
            
            return output_audio, srt_file, "✅ Story generated successfully!"
            
        except Exception as e:
            print(f"Error in generate_story_audio: {e}")
            return None, None, f"❌ Error: {str(e)}"
    
    async def generate_dialogue_audio(self, content: str, voice_q: str, voice_a: str,
                                    rate_q: int, rate_a: int, volume_q: int, volume_a: int,
                                    repeat_times: int) -> Tuple[Optional[str], Optional[str], str]:
        """Generate audio for Q&A dialogue"""
        try:
            # Parse dialogue
            dialogues = self.text_processor.parse_dialogue(content)
            if not dialogues:
                return None, None, "❌ No dialogue found"
            
            # Generate audio for each dialogue line
            audio_files = []
            
            for speaker, text in dialogues:
                if not text:
                    continue
                
                # Select voice based on speaker
                if speaker.upper() == "Q":
                    voice = voice_q
                    rate = rate_q
                    volume = volume_q
                elif speaker.upper() == "A":
                    voice = voice_a
                    rate = rate_a
                    volume = volume_a
                else:
                    # Default to question voice for other speakers
                    voice = voice_q
                    rate = rate_q
                    volume = volume_q
                
                audio_file, _ = await self.text_to_speech(text, voice, rate, volume)
                if audio_file and os.path.exists(audio_file):
                    audio_files.append(audio_file)
            
            if not audio_files:
                return None, None, "❌ Failed to generate audio"
            
            # Repeat if needed
            if repeat_times > 1:
                original_files = audio_files.copy()
                for _ in range(repeat_times - 1):
                    audio_files.extend(original_files)
            
            # Create output
            output_dir = self.audio_processor.create_output_directory()
            output_audio = os.path.join(output_dir, "dialogue.mp3")
            
            # Concatenate with default pause
            success = self.audio_processor.concatenate_audio_files(audio_files, output_audio, 300)
            
            if not success:
                self.audio_processor.cleanup_temp_files(audio_files)
                return None, None, "❌ Failed to merge audio"
            
            # Cleanup
            self.audio_processor.cleanup_temp_files(audio_files)
            
            return output_audio, None, "✅ Dialogue generated successfully!"
            
        except Exception as e:
            print(f"Error in generate_dialogue_audio: {e}")
            return None, None, f"❌ Error: {str(e)}"
    
    async def generate_multi_character_audio(self, content: str, 
                                           voice_char1: str, voice_char2: str, voice_char3: str,
                                           rate_char1: int, rate_char2: int, rate_char3: int,
                                           volume_char1: int, volume_char2: int, volume_char3: int,
                                           repeat_times: int) -> Tuple[Optional[str], Optional[str], str]:
        """Generate audio for multi-character story"""
        try:
            # Parse story with characters
            dialogues = self.text_processor.parse_dialogue(content)
            if not dialogues:
                return None, None, "❌ No character dialogue found"
            
            # Generate audio for each line
            audio_files = []
            
            for speaker, text in dialogues:
                if not text:
                    continue
                
                # Select voice based on character
                speaker_upper = speaker.upper()
                if speaker_upper.startswith("CHAR1"):
                    voice = voice_char1
                    rate = rate_char1
                    volume = volume_char1
                elif speaker_upper.startswith("CHAR2"):
                    voice = voice_char2
                    rate = rate_char2
                    volume = volume_char2
                elif speaker_upper.startswith("CHAR3"):
                    voice = voice_char3
                    rate = rate_char3
                    volume = volume_char3
                else:  # NARRATOR or others
                    voice = voice_char1
                    rate = rate_char1
                    volume = volume_char1
                
                audio_file, _ = await self.text_to_speech(text, voice, rate, volume)
                if audio_file and os.path.exists(audio_file):
                    audio_files.append(audio_file)
            
            if not audio_files:
                return None, None, "❌ Failed to generate audio"
            
            # Repeat if needed
            if repeat_times > 1:
                original_files = audio_files.copy()
                for _ in range(repeat_times - 1):
                    audio_files.extend(original_files)
            
            # Create output
            output_dir = self.audio_processor.create_output_directory()
            output_audio = os.path.join(output_dir, "multi_character.mp3")
            
            # Concatenate
            success = self.audio_processor.concatenate_audio_files(audio_files, output_audio, 400)
            
            if not success:
                self.audio_processor.cleanup_temp_files(audio_files)
                return None, None, "❌ Failed to merge audio"
            
            # Cleanup
            self.audio_processor.cleanup_temp_files(audio_files)
            
            return output_audio, None, "✅ Multi-character story generated!"
            
        except Exception as e:
            print(f"Error in generate_multi_character_audio: {e}")
            return None, None, f"❌ Error: {str(e)}"
    
    def _generate_srt_file(self, subtitles: List[Dict], output_path: str):
        """Generate SRT subtitle file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, 1):
                    start_ms = sub["start"]
                    end_ms = sub["end"]
                    
                    # Convert to SRT time format
                    start_time = self._ms_to_srt_time(start_ms)
                    end_time = self._ms_to_srt_time(end_ms)
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{sub['text']}\n\n")
        except Exception as e:
            print(f"Error generating SRT: {e}")
    
    def _ms_to_srt_time(self, milliseconds: int) -> str:
        """Convert milliseconds to SRT time format (HH:MM:SS,mmm)"""
        seconds, ms = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

# ==================== SETTINGS MANAGER ====================
class SettingsManager:
    """Manage application settings"""
    
    def __init__(self):
        self.settings_file = TTSConfig.SETTINGS_FILE
        self.settings = self.load_settings()
    
    def load_settings(self) -> Dict:
        """Load settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        return TTSConfig.get_default_settings()
    
    def save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def update_setting(self, tab: str, key: str, value: Any):
        """Update a specific setting"""
        if tab in self.settings and key in self.settings[tab]:
            self.settings[tab][key] = value
            self.save_settings()

# ==================== GRADIO INTERFACE ====================
class TTSInterface:
    """Gradio interface for TTS application"""
    
    def __init__(self):
        self.tts_engine = TTSEngine()
        self.settings_manager = SettingsManager()
        
        # Get default settings
        self.default_settings = TTSConfig.get_default_settings()
    
    def create_interface(self):
        """Create the Gradio interface"""
        with gr.Blocks(title="TTS Story Generator", theme=gr.themes.Soft()) as app:
            # Header
            gr.Markdown("# 🎵 TTS Story Generator")
            gr.Markdown("Generate audio stories with text-to-speech (No pydub dependency)")
            
            with gr.Tabs():
                # ========== TAB 1: SINGLE STORY ==========
                with gr.Tab("📖 Single Story"):
                    single_settings = self.default_settings["single_char"]
                    
                    with gr.Row():
                        with gr.Column(scale=2):
                            # Content input
                            story_content = gr.Textbox(
                                label="Story Content",
                                lines=10,
                                placeholder="Enter your story here...\n\nYou can write multiple paragraphs.\nEach paragraph will be processed separately.",
                                value="Once upon a time, there was a beautiful princess.\nShe lived in a castle surrounded by a magical forest.\nEvery day, she would explore the forest and discover new wonders."
                            )
                            
                            # Voice selection
                            with gr.Row():
                                language = gr.Dropdown(
                                    label="Language",
                                    choices=list(TTSConfig.LANGUAGES.keys()),
                                    value=single_settings["language"]
                                )
                                
                                # Voice dropdown will be updated based on language
                                voice_options = self._get_voice_options(single_settings["language"])
                                voice = gr.Dropdown(
                                    label="Voice",
                                    choices=voice_options,
                                    value=single_settings["voice"]
                                )
                            
                            # Settings
                            with gr.Row():
                                rate = gr.Slider(
                                    label="Speed",
                                    minimum=-30,
                                    maximum=30,
                                    step=1,
                                    value=single_settings["rate"],
                                    info="Negative = slower, Positive = faster"
                                )
                                
                                volume = gr.Slider(
                                    label="Volume",
                                    minimum=50,
                                    maximum=150,
                                    step=1,
                                    value=single_settings["volume"],
                                    info="100 = normal volume"
                                )
                            
                            pause = gr.Slider(
                                label="Pause between paragraphs (ms)",
                                minimum=100,
                                maximum=2000,
                                step=50,
                                value=single_settings["pause"]
                            )
                            
                            save_checkbox = gr.Checkbox(
                                label="Save these settings",
                                value=False
                            )
                            
                            # Generate button
                            generate_btn = gr.Button(
                                "🎤 Generate Audio Story",
                                variant="primary",
                                size="lg"
                            )
                        
                        with gr.Column(scale=1):
                            # Output
                            audio_output = gr.Audio(
                                label="Generated Audio",
                                type="filepath",
                                interactive=False
                            )
                            
                            status = gr.Textbox(
                                label="Status",
                                interactive=False
                            )
                            
                            # Subtitles section
                            with gr.Accordion("📝 Subtitles (SRT)", open=False):
                                subtitles_display = gr.Textbox(
                                    label="SRT Content",
                                    lines=8,
                                    interactive=False
                                )
                                
                                download_srt = gr.Button(
                                    "📥 Download SRT File",
                                    visible=False
                                )
                
                # ========== TAB 2: Q&A DIALOGUE ==========
                with gr.Tab("💬 Q&A Dialogue"):
                    dialogue_settings = self.default_settings["dialogue"]
                    
                    with gr.Row():
                        with gr.Column(scale=2):
                            # Content
                            dialogue_content = gr.Textbox(
                                label="Dialogue Content",
                                lines=10,
                                placeholder="Q: Question text\nA: Answer text\nQ: Next question\nA: Next answer\n\nUse Q: for questions and A: for answers.",
                                value="Q: What is your name?\nA: My name is AI Assistant.\nQ: What can you do?\nA: I can help you generate audio stories and dialogues."
                            )
                            
                            # Question settings
                            with gr.Row():
                                q_language = gr.Dropdown(
                                    label="Question Language",
                                    choices=list(TTSConfig.LANGUAGES.keys()),
                                    value=dialogue_settings["language_q"]
                                )
                                
                                q_voice_options = self._get_voice_options(dialogue_settings["language_q"])
                                q_voice = gr.Dropdown(
                                    label="Question Voice",
                                    choices=q_voice_options,
                                    value=dialogue_settings["voice_q"]
                                )
                            
                            # Answer settings
                            with gr.Row():
                                a_language = gr.Dropdown(
                                    label="Answer Language",
                                    choices=list(TTSConfig.LANGUAGES.keys()),
                                    value=dialogue_settings["language_a"]
                                )
                                
                                a_voice_options = self._get_voice_options(dialogue_settings["language_a"])
                                a_voice = gr.Dropdown(
                                    label="Answer Voice",
                                    choices=a_voice_options,
                                    value=dialogue_settings["voice_a"]
                                )
                            
                            # Settings
                            with gr.Row():
                                q_rate = gr.Slider(
                                    label="Question Speed",
                                    minimum=-30,
                                    maximum=30,
                                    step=1,
                                    value=dialogue_settings["rate_q"]
                                )
                                
                                a_rate = gr.Slider(
                                    label="Answer Speed",
                                    minimum=-30,
                                    maximum=30,
                                    step=1,
                                    value=dialogue_settings["rate_a"]
                                )
                            
                            with gr.Row():
                                q_volume = gr.Slider(
                                    label="Question Volume",
                                    minimum=50,
                                    maximum=150,
                                    step=1,
                                    value=dialogue_settings["volume_q"]
                                )
                                
                                a_volume = gr.Slider(
                                    label="Answer Volume",
                                    minimum=50,
                                    maximum=150,
                                    step=1,
                                    value=dialogue_settings["volume_a"]
                                )
                            
                            repeat_times = gr.Slider(
                                label="Repeat whole dialogue",
                                minimum=1,
                                maximum=5,
                                step=1,
                                value=dialogue_settings["repeat_times"],
                                info="Number of times to repeat the entire dialogue"
                            )
                            
                            save_dialogue = gr.Checkbox(
                                label="Save dialogue settings",
                                value=False
                            )
                            
                            generate_dialogue_btn = gr.Button(
                                "🎭 Generate Dialogue Audio",
                                variant="primary",
                                size="lg"
                            )
                        
                        with gr.Column(scale=1):
                            dialogue_audio = gr.Audio(
                                label="Generated Dialogue",
                                type="filepath",
                                interactive=False
                            )
                            
                            dialogue_status = gr.Textbox(
                                label="Status",
                                interactive=False
                            )
                
                # ========== TAB 3: MULTI CHARACTER ==========
                with gr.Tab("👥 Multi-Character Story"):
                    multi_settings = self.default_settings["multi_char"]
                    
                    with gr.Row():
                        with gr.Column(scale=2):
                            # Content
                            multi_content = gr.Textbox(
                                label="Story with Characters",
                                lines=10,
                                placeholder="CHAR1: Dialogue for character 1\nCHAR2: Dialogue for character 2\nCHAR3: Dialogue for character 3\nNARRATOR: Narration text\n\nUse CHAR1:, CHAR2:, CHAR3:, or NARRATOR: prefixes.",
                                value="CHAR1: Hello, my name is Alice.\nCHAR2: Nice to meet you, Alice. I'm Bob.\nNARRATOR: They shook hands and became friends.\nCHAR1: Would you like to explore the forest with me?\nCHAR2: That sounds like an adventure!"
                            )
                            
                            # Character 1
                            with gr.Row():
                                char1_lang = gr.Dropdown(
                                    label="Character 1 Language",
                                    choices=list(TTSConfig.LANGUAGES.keys()),
                                    value=multi_settings["language_char1"]
                                )
                                
                                char1_voice_options = self._get_voice_options(multi_settings["language_char1"])
                                char1_voice = gr.Dropdown(
                                    label="Character 1 Voice",
                                    choices=char1_voice_options,
                                    value=multi_settings["voice_char1"]
                                )
                            
                            # Character 2
                            with gr.Row():
                                char2_lang = gr.Dropdown(
                                    label="Character 2 Language",
                                    choices=list(TTSConfig.LANGUAGES.keys()),
                                    value=multi_settings["language_char2"]
                                )
                                
                                char2_voice_options = self._get_voice_options(multi_settings["language_char2"])
                                char2_voice = gr.Dropdown(
                                    label="Character 2 Voice",
                                    choices=char2_voice_options,
                                    value=multi_settings["voice_char2"]
                                )
                            
                            # Character 3 (optional)
                            with gr.Row():
                                char3_lang = gr.Dropdown(
                                    label="Character 3 Language",
                                    choices=list(TTSConfig.LANGUAGES.keys()),
                                    value=multi_settings["language_char1"]  # Default to char1 language
                                )
                                
                                char3_voice_options = self._get_voice_options(multi_settings["language_char1"])
                                char3_voice = gr.Dropdown(
                                    label="Character 3 Voice",
                                    choices=char3_voice_options,
                                    value=multi_settings["voice_char1"]  # Default to char1 voice
                                )
                            
                            # Settings
                            with gr.Row():
                                char1_rate = gr.Slider(
                                    label="Char1 Speed",
                                    minimum=-30,
                                    maximum=30,
                                    step=1,
                                    value=multi_settings["rate_char1"]
                                )
                                
                                char2_rate = gr.Slider(
                                    label="Char2 Speed",
                                    minimum=-30,
                                    maximum=30,
                                    step=1,
                                    value=multi_settings["rate_char2"]
                                )
                                
                                char3_rate = gr.Slider(
                                    label="Char3 Speed",
                                    minimum=-30,
                                    maximum=30,
                                    step=1,
                                    value=0
                                )
                            
                            with gr.Row():
                                char1_volume = gr.Slider(
                                    label="Char1 Volume",
                                    minimum=50,
                                    maximum=150,
                                    step=1,
                                    value=multi_settings["volume_char1"]
                                )
                                
                                char2_volume = gr.Slider(
                                    label="Char2 Volume",
                                    minimum=50,
                                    maximum=150,
                                    step=1,
                                    value=multi_settings["volume_char2"]
                                )
                                
                                char3_volume = gr.Slider(
                                    label="Char3 Volume",
                                    minimum=50,
                                    maximum=150,
                                    step=1,
                                    value=100
                                )
                            
                            multi_repeat = gr.Slider(
                                label="Repeat story",
                                minimum=1,
                                maximum=3,
                                step=1,
                                value=multi_settings["repeat_times"]
                            )
                            
                            save_multi = gr.Checkbox(
                                label="Save multi-character settings",
                                value=False
                            )
                            
                            generate_multi_btn = gr.Button(
                                "🎬 Generate Multi-Character Audio",
                                variant="primary",
                                size="lg"
                            )
                        
                        with gr.Column(scale=1):
                            multi_audio = gr.Audio(
                                label="Generated Story",
                                type="filepath",
                                interactive=False
                            )
                            
                            multi_status = gr.Textbox(
                                label="Status",
                                interactive=False
                            )
            
            # ========== EVENT HANDLERS ==========
            
            # Tab 1: Single Story
            language.change(
                self.update_voice_dropdown,
                inputs=[language],
                outputs=[voice]
            )
            
            generate_btn.click(
                self.generate_story,
                inputs=[
                    story_content, voice, rate, volume, pause, save_checkbox
                ],
                outputs=[audio_output, status]
            ).then(
                self.show_subtitles,
                inputs=[audio_output],
                outputs=[subtitles_display, download_srt]
            )
            
            # Tab 2: Q&A Dialogue
            q_language.change(
                self.update_voice_dropdown,
                inputs=[q_language],
                outputs=[q_voice]
            )
            
            a_language.change(
                self.update_voice_dropdown,
                inputs=[a_language],
                outputs=[a_voice]
            )
            
            generate_dialogue_btn.click(
                self.generate_dialogue,
                inputs=[
                    dialogue_content, q_voice, a_voice,
                    q_rate, a_rate, q_volume, a_volume,
                    repeat_times, save_dialogue
                ],
                outputs=[dialogue_audio, dialogue_status]
            )
            
            # Tab 3: Multi Character
            char1_lang.change(
                self.update_voice_dropdown,
                inputs=[char1_lang],
                outputs=[char1_voice]
            )
            
            char2_lang.change(
                self.update_voice_dropdown,
                inputs=[char2_lang],
                outputs=[char2_voice]
            )
            
            char3_lang.change(
                self.update_voice_dropdown,
                inputs=[char3_lang],
                outputs=[char3_voice]
            )
            
            generate_multi_btn.click(
                self.generate_multi_character,
                inputs=[
                    multi_content,
                    char1_voice, char2_voice, char3_voice,
                    char1_rate, char2_rate, char3_rate,
                    char1_volume, char2_volume, char3_volume,
                    multi_repeat, save_multi
                ],
                outputs=[multi_audio, multi_status]
            )
            
            # Footer
            gr.Markdown("---")
            gr.Markdown(
                """
                ### 📋 Usage Tips:
                1. **For best results**, keep each paragraph under 500 characters
                2. **Use proper punctuation** (.,!?) for natural pauses
                3. **Save your favorite voice settings** for quick reuse
                4. **Generated files** are saved in timestamped folders
                
                ### 🔧 Technical Notes:
                - Uses **edge-tts** for high-quality speech synthesis
                - No **pydub** dependency - works on all platforms
                - Supports **multiple languages and voices**
                - Generates **SRT subtitles** when available
                """
            )
        
        return app
    
    def _get_voice_options(self, language: str) -> List[str]:
        """Get voice options for a language"""
        return TTSConfig.LANGUAGES.get(language, [])
    
    def update_voice_dropdown(self, language: str):
        """Update voice dropdown based on selected language"""
        voices = self._get_voice_options(language)
        if voices:
            return gr.Dropdown(choices=voices, value=voices[0])
        return gr.Dropdown(choices=[])
    
    async def generate_story(self, content: str, voice: str, rate: int, 
                           volume: int, pause: int, save_settings: bool):
        """Generate story audio"""
        if save_settings:
            self.settings_manager.update_setting("single_char", "voice", voice)
            self.settings_manager.update_setting("single_char", "rate", rate)
            self.settings_manager.update_setting("single_char", "volume", volume)
            self.settings_manager.update_setting("single_char", "pause", pause)
        
        audio_path, srt_path, message = await self.tts_engine.generate_story_audio(
            content, voice, rate, volume, pause
        )
        
        return audio_path, message
    
    async def generate_dialogue(self, content: str, voice_q: str, voice_a: str,
                              rate_q: int, rate_a: int, volume_q: int, volume_a: int,
                              repeat_times: int, save_settings: bool):
        """Generate dialogue audio"""
        if save_settings:
            self.settings_manager.update_setting("dialogue", "voice_q", voice_q)
            self.settings_manager.update_setting("dialogue", "voice_a", voice_a)
            self.settings_manager.update_setting("dialogue", "rate_q", rate_q)
            self.settings_manager.update_setting("dialogue", "rate_a", rate_a)
            self.settings_manager.update_setting("dialogue", "volume_q", volume_q)
            self.settings_manager.update_setting("dialogue", "volume_a", volume_a)
            self.settings_manager.update_setting("dialogue", "repeat_times", repeat_times)
        
        audio_path, _, message = await self.tts_engine.generate_dialogue_audio(
            content, voice_q, voice_a, rate_q, rate_a, volume_q, volume_a, repeat_times
        )
        
        return audio_path, message
    
    async def generate_multi_character(self, content: str,
                                     voice_char1: str, voice_char2: str, voice_char3: str,
                                     rate_char1: int, rate_char2: int, rate_char3: int,
                                     volume_char1: int, volume_char2: int, volume_char3: int,
                                     repeat_times: int, save_settings: bool):
        """Generate multi-character audio"""
        if save_settings:
            self.settings_manager.update_setting("multi_char", "voice_char1", voice_char1)
            self.settings_manager.update_setting("multi_char", "voice_char2", voice_char2)
            self.settings_manager.update_setting("multi_char", "rate_char1", rate_char1)
            self.settings_manager.update_setting("multi_char", "rate_char2", rate_char2)
            self.settings_manager.update_setting("multi_char", "volume_char1", volume_char1)
            self.settings_manager.update_setting("multi_char", "volume_char2", volume_char2)
            self.settings_manager.update_setting("multi_char", "repeat_times", repeat_times)
        
        audio_path, _, message = await self.tts_engine.generate_multi_character_audio(
            content, voice_char1, voice_char2, voice_char3,
            rate_char1, rate_char2, rate_char3,
            volume_char1, volume_char2, volume_char3,
            repeat_times
        )
        
        return audio_path, message
    
    def show_subtitles(self, audio_path: str):
        """Show subtitles for generated audio"""
        if not audio_path or not isinstance(audio_path, str):
            return "No subtitles available", gr.Button(visible=False)
        
        srt_path = audio_path.replace('.mp3', '.srt')
        if os.path.exists(srt_path):
            try:
                with open(srt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content, gr.Button(visible=True)
            except Exception as e:
                return f"Error reading subtitles: {e}", gr.Button(visible=False)
        else:
            return "No subtitles available", gr.Button(visible=False)

# ==================== MAIN APPLICATION ====================
def main():
    """Main application entry point"""
    print("=" * 60)
    print("TTS Story Generator - Starting...")
    print(f"Python: {sys.version}")
    print(f"Gradio: {gr.__version__}")
    print(f"Edge TTS: Available" if EDGE_TTS_AVAILABLE else "Edge TTS: Not available")
    print("=" * 60)
    
    # Clean up old temp directories
    for dir_pattern in ["temp_audio", "output_*"]:
        try:
            import glob
            for dir_path in glob.glob(dir_pattern):
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
        except:
            pass
    
    # Create necessary directories
    os.makedirs("temp_audio", exist_ok=True)
    
    # Create and launch interface
    try:
        tts_interface = TTSInterface()
        app = tts_interface.create_interface()
        
        # Get port from environment variable (for Render/Heroku)
        port = int(os.environ.get("PORT", 7860))
        host = os.environ.get("HOST", "0.0.0.0")
        
        print(f"🚀 Launching TTS Story Generator on {host}:{port}")
        print("📱 Open your browser and navigate to the URL shown above")
        print("=" * 60)
        
        app.launch(
            server_name=host,
            server_port=port,
            share=False,
            debug=False,
            show_error=True,
            quiet=True
        )
        
    except Exception as e:
        print(f"❌ Error launching application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Set asyncio policy for compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the application
    main()
