#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS Story Generator - Text-to-Speech Application
Deployment optimized version without pydub dependency issues
"""

# ==================== IMPORTS WITH ERROR HANDLING ====================
import os
import sys
import json
import re
import asyncio
import random
import time
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import io

# Try to import optional dependencies with fallbacks
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    print("Warning: numpy not available, using simple fallback")
    NUMPY_AVAILABLE = False

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

try:
    import webvtt
    WEBVTT_AVAILABLE = True
except ImportError:
    print("Warning: webvtt-py not available")
    WEBVTT_AVAILABLE = False

try:
    import natsort
    NATSORT_AVAILABLE = True
except ImportError:
    print("Warning: natsort not available")
    NATSORT_AVAILABLE = False

# Try pydub with comprehensive error handling
try:
    # First try to import audioop/pyaudioop dependencies
    try:
        import audioop
    except ImportError:
        try:
            import pyaudioop as audioop
        except ImportError:
            # Create a dummy audioop module
            class DummyAudioop:
                @staticmethod
                def getsample(*args, **kwargs):
                    return 0
                @staticmethod
                def max(*args, **kwargs):
                    return 0
                @staticmethod
                def minmax(*args, **kwargs):
                    return (0, 0)
                @staticmethod
                def avg(*args, **kwargs):
                    return 0
                @staticmethod
                def rms(*args, **kwargs):
                    return 0
                @staticmethod
                def cross(*args, **kwargs):
                    return 0
                @staticmethod
                def mul(*args, **kwargs):
                    return b''
                @staticmethod
                def add(*args, **kwargs):
                    return b''
                @staticmethod
                def bias(*args, **kwargs):
                    return b''
                @staticmethod
                def ulaw2lin(*args, **kwargs):
                    return b''
                @staticmethod
                def lin2ulaw(*args, **kwargs):
                    return b''
                @staticmethod
                def lin2alaw(*args, **kwargs):
                    return b''
                @staticmethod
                def alaw2lin(*args, **kwargs):
                    return b''
                @staticmethod
                def lin2lin(*args, **kwargs):
                    return b''
                @staticmethod
                def ratecv(*args, **kwargs):
                    return (b'', 0)
                @staticmethod
                def tomono(*args, **kwargs):
                    return b''
                @staticmethod
                def tostereo(*args, **kwargs):
                    return b''
                @staticmethod
                def findfactor(*args, **kwargs):
                    return 0
                @staticmethod
                def findfit(*args, **kwargs):
                    return (0, 0)
                @staticmethod
                def findmax(*args, **kwargs):
                    return 0
                @staticmethod
                def getsample(*args, **kwargs):
                    return 0
            audioop = DummyAudioop()
    
    from pydub import AudioSegment
    from pydub.effects import normalize, compress_dynamic_range
    PYDUB_AVAILABLE = True
    print("✓ pydub loaded successfully")
except Exception as e:
    print(f"⚠️ pydub not available: {e}")
    PYDUB_AVAILABLE = False
    
    # Create minimal AudioSegment replacement
    class SimpleAudioSegment:
        def __init__(self, data=None, frame_rate=24000, sample_width=2, channels=1):
            self.data = data
            self.frame_rate = frame_rate
            self.sample_width = sample_width
            self.channels = channels
            self._duration = len(data) // (sample_width * channels) if data else 0
            
        @classmethod
        def from_file(cls, file_path, format=None):
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                return cls(data=data, frame_rate=24000, sample_width=2, channels=1)
            except:
                return cls()
        
        @classmethod
        def from_mp3(cls, file_path):
            return cls.from_file(file_path)
        
        @classmethod
        def silent(cls, duration=1000, frame_rate=24000):
            # Create silence - simple implementation
            bytes_per_sample = 2  # 16-bit audio
            num_samples = int(frame_rate * duration / 1000)
            data = b'\x00' * (num_samples * bytes_per_sample)
            return cls(data=data, frame_rate=frame_rate)
        
        def export(self, file_path, format="mp3", bitrate="128k"):
            try:
                with open(file_path, 'wb') as f:
                    if self.data:
                        f.write(self.data)
                return file_path
            except:
                return None
        
        def fade_in(self, duration):
            return self
        
        def fade_out(self, duration):
            return self
        
        def __add__(self, other):
            if isinstance(other, (int, float)):
                return self
            if self.data and other.data:
                new_data = self.data + other.data
            else:
                new_data = self.data or other.data
            return SimpleAudioSegment(data=new_data, frame_rate=self.frame_rate)
        
        def __radd__(self, other):
            return self.__add__(other)
        
        def low_pass_filter(self, freq):
            return self
        
        def high_pass_filter(self, freq):
            return self
        
        @property
        def duration_seconds(self):
            return self._duration / self.frame_rate if self.frame_rate > 0 else 0
        
        def set_frame_rate(self, frame_rate):
            self.frame_rate = frame_rate
            return self
    
    AudioSegment = SimpleAudioSegment
    
    def normalize(audio):
        return audio
    
    def compress_dynamic_range(audio, threshold=-20.0, ratio=4.0, attack=5, release=50):
        return audio
    
    def low_pass_filter(audio, freq):
        return audio
    
    def high_pass_filter(audio, freq):
        return audio

# ==================== CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "edge_tts_settings.json"
    LANGUAGES = {
        "Tiếng Việt": [
            {"name": "vi-VN-HoaiMyNeural", "gender": "Nữ"},
            {"name": "vi-VN-NamMinhNeural", "gender": "Nam"}
        ],
        "English (US)": [
            {"name": "en-US-GuyNeural", "gender": "Nam"},
            {"name": "en-US-JennyNeural", "gender": "Nữ"},
            {"name": "en-US-AvaNeural", "gender": "Nữ"},
            {"name": "en-US-AndrewNeural", "gender": "Nam"},
            {"name": "en-US-EmmaNeural", "gender": "Nữ"},
            {"name": "en-US-BrianNeural", "gender": "Nam"}
        ],
        "English (UK)": [
            {"name": "en-GB-LibbyNeural", "gender": "Nữ"},
            {"name": "en-GB-MiaNeural", "gender": "Nữ"},
            {"name": "en-GB-RyanNeural", "gender": "Nam"},
            {"name": "en-GB-ThomasNeural", "gender": "Nam"}
        ]
    }
    
    @staticmethod
    def get_default_settings():
        return {
            "single_char": {
                "language": "Tiếng Việt",
                "voice": "Tiếng Việt - HoaiMy (Nữ)",
                "rate": 0,
                "pitch": 0,
                "volume": 100,
                "pause": 500
            },
            "multi_char": {
                "language_char1": "Tiếng Việt",
                "voice_char1": "Tiếng Việt - HoaiMy (Nữ)",
                "language_char2": "Tiếng Việt",
                "voice_char2": "Tiếng Việt - NamMinh (Nam)",
                "rate_char1": -20,
                "pitch_char1": 0,
                "volume_char1": 100,
                "rate_char2": -25,
                "pitch_char2": 0,
                "volume_char2": 100,
                "repeat_times": 1,
                "pause_between": 500
            },
            "dialogue": {
                "language_q": "Tiếng Việt",
                "voice_q": "Tiếng Việt - HoaiMy (Nữ)",
                "language_a": "Tiếng Việt",
                "voice_a": "Tiếng Việt - NamMinh (Nam)",
                "rate_q": -20,
                "pitch_q": 0,
                "volume_q": 100,
                "rate_a": -25,
                "pitch_a": 0,
                "volume_a": 100,
                "repeat_times": 2,
                "pause_q": 200,
                "pause_a": 500
            }
        }

# ==================== TEXT PROCESSOR ====================
class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
            
        text = TextProcessor._process_special_cases(text)
        re_tab = re.compile(r'[\r\t]')
        re_spaces = re.compile(r' +')
        re_punctuation = re.compile(r'(\s)([,.!?])')
        
        text = re_tab.sub(' ', text)
        text = re_spaces.sub(' ', text)
        text = re_punctuation.sub(r'\2', text)
        
        return text.strip()

    @staticmethod
    def _process_special_cases(text: str) -> str:
        """Process special text cases"""
        if not text:
            return text
            
        # Process emails
        email_pattern = r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b'
        text = re.sub(email_pattern, 
                     lambda m: m.group(0).replace('@', ' at ').replace('.', ' dot '), 
                     text)
        
        # Process URLs
        url_pattern = r'\b(https?://|www\.)[\w.-]+\.[a-zA-Z]{2,}[/\w.-]*\b'
        text = re.sub(url_pattern, 
                     lambda m: m.group(0).replace('.', ' dot ').replace('/', ' slash '), 
                     text)
        
        # Process phone numbers
        phone_pattern = r'\b(\d{3})[-. ]?(\d{3})[-. ]?(\d{4})\b'
        text = re.sub(phone_pattern, 
                     lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}", 
                     text)
        
        # Process percentages
        text = re.sub(r'(\d+\.?\d*)%', 
                     lambda m: f"{TextProcessor._number_to_words(m.group(1))} percent", 
                     text)
        
        # Process currency
        currency_map = {'$': 'dollars', '€': 'euros', '£': 'pounds', '¥': 'yen'}
        for symbol, word in currency_map.items():
            text = re.sub(f'\\{symbol}(\\d+(?:\\.\\d+)?)', 
                         lambda m: f"{TextProcessor._number_to_words(m.group(1))} {word}", 
                         text)
        
        # Process times
        time_pattern = r'\b(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?\b'
        text = re.sub(time_pattern, TextProcessor._time_to_words, text, flags=re.IGNORECASE)
        
        return text

    @staticmethod
    def _time_to_words(match):
        """Convert time to words"""
        hour, minute, period = match.groups()
        hour_int = int(hour)
        
        if period:
            period_text = f" {period.upper()}"
        else:
            period_text = ""
            
        hour_12 = hour_int % 12
        hour_text = "twelve" if hour_12 == 0 else TextProcessor._number_to_words(str(hour_12))
        
        minute_int = int(minute)
        if minute_int == 0:
            minute_text = "o'clock"
        elif minute_int < 10:
            minute_text = f"oh {TextProcessor._number_to_words(minute)}"
        else:
            minute_text = TextProcessor._number_to_words(minute)
            
        return f"{hour_text} {minute_text}{period_text}"

    @staticmethod
    def _number_to_words(number: str) -> str:
        """Convert number to words (simplified version)"""
        try:
            num = float(number.replace(',', ''))
            
            # Simple conversion for small numbers
            if num == 0:
                return "zero"
            elif num < 20:
                ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 
                       'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 
                       'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
                return ones[int(num)]
            elif num < 100:
                tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 
                       'sixty', 'seventy', 'eighty', 'ninety']
                ten, one = divmod(int(num), 10)
                result = tens[ten]
                if one > 0:
                    result += f" {TextProcessor._number_to_words(str(one))}"
                return result
            else:
                # For larger numbers, just return the digits
                return ' '.join(str(int(d)) if d.isdigit() else d for d in str(num))
        except:
            return number

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Split text into sentences"""
        if not text:
            return []
            
        # Split by sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def parse_dialogues(text: str, prefixes: List[str]) -> List[Tuple[str, str]]:
        """Parse dialogues with prefixes"""
        dialogues = []
        current_speaker = None
        current_text = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            found_prefix = None
            for prefix in prefixes:
                if line.lower().startswith(prefix.lower() + ':'):
                    found_prefix = prefix
                    break
                    
            if found_prefix:
                if current_speaker is not None:
                    dialogues.append((current_speaker, ' '.join(current_text)))
                
                current_speaker = found_prefix
                current_text = [line[len(found_prefix)+1:].strip()]
            elif current_speaker is not None:
                current_text.append(line)
                
        if current_speaker is not None:
            dialogues.append((current_speaker, ' '.join(current_text)))
            
        return dialogues

# ==================== SIMPLE AUDIO PROCESSOR ====================
class SimpleAudioProcessor:
    """Simple audio processor without complex dependencies"""
    
    @staticmethod
    def calculate_pause(text: str) -> int:
        """Calculate pause duration based on text ending"""
        if not text:
            return 0
            
        text = text.strip()
        last_char = text[-1] if text else ''
        
        pause_map = {
            '.': 500,
            '!': 400,
            '?': 400,
            ',': 200,
            ';': 300,
            ':': 250
        }
        
        return pause_map.get(last_char, 300)
    
    @staticmethod
    def merge_audio_files(file_paths: List[str], output_path: str, pause_between: int = 500) -> bool:
        """Merge multiple audio files with pauses between them"""
        try:
            if not file_paths:
                return False
                
            # Simple implementation: just use the first file if pydub not available
            if PYDUB_AVAILABLE:
                merged = AudioSegment.empty()
                pause = AudioSegment.silent(duration=pause_between)
                
                for i, file_path in enumerate(file_paths):
                    if os.path.exists(file_path):
                        audio = AudioSegment.from_file(file_path)
                        audio = audio.fade_in(10).fade_out(10)
                        merged += audio
                        
                        if i < len(file_paths) - 1:
                            merged += pause
                
                merged.export(output_path, format="mp3", bitrate="256k")
            else:
                # Fallback: copy the first file
                import shutil
                if os.path.exists(file_paths[0]):
                    shutil.copy2(file_paths[0], output_path)
                else:
                    # Create a dummy file
                    with open(output_path, 'wb') as f:
                        f.write(b'')  # Empty file
                        
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error merging audio: {e}")
            return False

# ==================== SUBTITLE GENERATOR ====================
class SubtitleGenerator:
    """Generate subtitles for audio"""
    
    @staticmethod
    def generate_srt_from_texts(texts: List[str], durations: List[int]) -> str:
        """Generate SRT subtitles from texts and durations"""
        if not texts or not durations:
            return ""
            
        srt_lines = []
        current_time = 0
        
        for i, (text, duration) in enumerate(zip(texts, durations), 1):
            start_time = timedelta(milliseconds=current_time)
            end_time = timedelta(milliseconds=current_time + duration)
            
            start_str = f"{start_time.seconds // 3600:02}:{(start_time.seconds % 3600) // 60:02}:{start_time.seconds % 60:02},{start_time.microseconds // 1000:03}"
            end_str = f"{end_time.seconds // 3600:02}:{(end_time.seconds % 3600) // 60:02}:{end_time.seconds % 60:02},{end_time.microseconds // 1000:03}"
            
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_str} --> {end_str}")
            srt_lines.append(text)
            srt_lines.append("")
            
            current_time += duration + 300  # Add pause between sentences
            
        return "\n".join(srt_lines)
    
    @staticmethod
    def save_srt(content: str, file_path: str) -> bool:
        """Save SRT content to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error saving SRT: {e}")
            return False

# ==================== BASE TTS PROCESSOR ====================
class BaseTTSProcessor:
    """Base TTS processor with common functionality"""
    
    def __init__(self):
        self.voice_map = {}
        self.settings = {}
        self.text_processor = TextProcessor()
        self.audio_processor = SimpleAudioProcessor()
        self.subtitle_generator = SubtitleGenerator()
        self.initialize_voices()
        self.load_settings()
    
    def initialize_voices(self):
        """Initialize voice mapping"""
        for lang, voices in TTSConfig.LANGUAGES.items():
            for voice in voices:
                voice_name = voice['name'].split('-')[-1].replace('Neural', '')
                display_name = f"{lang} - {voice_name} ({voice['gender']})"
                self.voice_map[display_name] = voice['name']
    
    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists(TTSConfig.SETTINGS_FILE):
                with open(TTSConfig.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            else:
                self.settings = TTSConfig.get_default_settings()
        except Exception as e:
            print(f"Error loading settings: {e}")
            self.settings = TTSConfig.get_default_settings()
    
    def save_settings(self):
        """Save settings to file"""
        try:
            with open(TTSConfig.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, 
                            pitch: int = 0, volume: int = 100) -> Tuple[Optional[str], List]:
        """Generate speech from text using Edge TTS"""
        if not EDGE_TTS_AVAILABLE:
            print("Edge TTS not available")
            return None, []
            
        try:
            # Create rate string for Edge TTS
            rate_str = f"{rate:+d}%" if rate != 0 else "+0%"
            
            # Create communicate object
            communicate = edge_tts.Communicate(
                text, 
                voice_id, 
                rate=rate_str
            )
            
            # Generate temporary filename
            temp_dir = "temp_audio"
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f"temp_{random.randint(10000, 99999)}.mp3")
            
            # Generate audio
            subtitles = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    with open(temp_file, "ab") as f:
                        f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    subtitles.append({
                        "text": chunk["text"],
                        "start": chunk["offset"],
                        "end": chunk["offset"] + chunk["duration"]
                    })
            
            return temp_file, subtitles
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None, []
    
    def cleanup_temp_files(self, files: List[str]):
        """Clean up temporary files"""
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error removing file {file_path}: {e}")

# ==================== SINGLE CHARACTER PROCESSOR ====================
class StoryTTSProcessor(BaseTTSProcessor):
    """Processor for single character stories"""
    
    def __init__(self):
        super().__init__()
    
    async def process_story(self, content: str, voice: str, rate: int, pitch: int, 
                          volume: int, pause: int, save_settings: bool) -> Tuple[Optional[str], Optional[str], str]:
        """Process a story with single character"""
        try:
            # Get voice ID
            voice_id = self.voice_map.get(voice)
            if not voice_id:
                return None, None, "❌ Voice not found"
            
            # Split content into sentences
            sentences = self.text_processor.split_sentences(content)
            if not sentences:
                return None, None, "❌ No content to process"
            
            # Generate audio for each sentence
            audio_files = []
            all_subtitles = []
            
            for i, sentence in enumerate(sentences):
                temp_file, subtitles = await self.generate_speech(
                    sentence, voice_id, rate, pitch, volume
                )
                
                if temp_file and os.path.exists(temp_file):
                    audio_files.append(temp_file)
                    all_subtitles.extend(subtitles)
                else:
                    print(f"Failed to generate audio for sentence {i+1}")
            
            if not audio_files:
                return None, None, "❌ Failed to generate any audio"
            
            # Merge audio files
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"output_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)
            
            merged_audio = os.path.join(output_dir, "story.mp3")
            success = self.audio_processor.merge_audio_files(audio_files, merged_audio, pause)
            
            if not success:
                self.cleanup_temp_files(audio_files)
                return None, None, "❌ Failed to merge audio files"
            
            # Generate subtitles
            srt_file = os.path.join(output_dir, "story.srt")
            if all_subtitles:
                # Simple SRT generation
                srt_content = []
                current_time = 0
                
                for i, sub in enumerate(all_subtitles, 1):
                    start = timedelta(milliseconds=sub["start"])
                    end = timedelta(milliseconds=sub["end"])
                    
                    start_str = f"{start.seconds // 3600:02}:{(start.seconds % 3600) // 60:02}:{start.seconds % 60:02},{start.microseconds // 1000:03}"
                    end_str = f"{end.seconds // 3600:02}:{(end.seconds % 3600) // 60:02}:{end.seconds % 60:02},{end.microseconds // 1000:03}"
                    
                    srt_content.append(f"{i}")
                    srt_content.append(f"{start_str} --> {end_str}")
                    srt_content.append(sub["text"])
                    srt_content.append("")
                
                with open(srt_file, 'w', encoding='utf-8') as f:
                    f.write("\n".join(srt_content))
            else:
                srt_file = None
            
            # Clean up temp files
            self.cleanup_temp_files(audio_files)
            
            # Save settings if requested
            if save_settings:
                self.settings["single_char"] = {
                    "voice": voice,
                    "rate": rate,
                    "pitch": pitch,
                    "volume": volume,
                    "pause": pause
                }
                self.save_settings()
            
            return merged_audio, srt_file, "✅ Story generated successfully!"
            
        except Exception as e:
            print(f"Error in process_story: {e}")
            return None, None, f"❌ Error: {str(e)}"

# ==================== MULTI CHARACTER PROCESSOR ====================
class MultiCharacterTTSProcessor(BaseTTSProcessor):
    """Processor for multi-character stories"""
    
    def __init__(self):
        super().__init__()
    
    def parse_story(self, content: str) -> List[Tuple[str, str]]:
        """Parse multi-character story content"""
        dialogues = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for character tags
            if line.upper().startswith("CHAR1:"):
                dialogues.append(("CHAR1", line[6:].strip()))
            elif line.upper().startswith("CHAR2:"):
                dialogues.append(("CHAR2", line[6:].strip()))
            elif line.upper().startswith("CHAR3:"):
                dialogues.append(("CHAR3", line[6:].strip()))
            elif line.upper().startswith("NARRATOR:"):
                dialogues.append(("NARRATOR", line[9:].strip()))
            elif dialogues:
                # Continue previous dialogue
                last_char, last_text = dialogues[-1]
                dialogues[-1] = (last_char, f"{last_text} {line}")
        
        return dialogues
    
    async def process_story(self, content: str, char1_voice: str, char2_voice: str, 
                          char3_voice: str, char1_rate: int, char2_rate: int, 
                          char3_rate: int, char1_volume: int, char2_volume: int, 
                          char3_volume: int, repeat_times: int, pause_between: int, 
                          save_settings: bool) -> Tuple[Optional[str], Optional[str], str]:
        """Process multi-character story"""
        try:
            # Parse dialogues
            dialogues = self.parse_story(content)
            if not dialogues:
                return None, None, "❌ No dialogues found"
            
            # Generate audio for each dialogue
            audio_files = []
            
            for char, text in dialogues:
                if not text:
                    continue
                    
                # Select voice based on character
                if char == "CHAR1":
                    voice_id = self.voice_map.get(char1_voice)
                    rate = char1_rate
                    volume = char1_volume
                elif char == "CHAR2":
                    voice_id = self.voice_map.get(char2_voice)
                    rate = char2_rate
                    volume = char2_volume
                elif char == "CHAR3":
                    voice_id = self.voice_map.get(char3_voice)
                    rate = char3_rate
                    volume = char3_volume
                else:  # NARRATOR uses char1 voice
                    voice_id = self.voice_map.get(char1_voice)
                    rate = char1_rate
                    volume = char1_volume
                
                if not voice_id:
                    continue
                
                temp_file, _ = await self.generate_speech(text, voice_id, rate, 0, volume)
                if temp_file and os.path.exists(temp_file):
                    audio_files.append(temp_file)
            
            if not audio_files:
                return None, None, "❌ Failed to generate audio"
            
            # Merge with repetition
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"output_multi_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Create repeated audio files list
            repeated_files = []
            for _ in range(repeat_times):
                repeated_files.extend(audio_files)
            
            merged_audio = os.path.join(output_dir, "multi_story.mp3")
            success = self.audio_processor.merge_audio_files(repeated_files, merged_audio, pause_between)
            
            if not success:
                self.cleanup_temp_files(audio_files)
                return None, None, "❌ Failed to merge audio"
            
            # Save settings if requested
            if save_settings:
                self.settings["multi_char"] = {
                    "voice_char1": char1_voice,
                    "voice_char2": char2_voice,
                    "voice_char3": char3_voice,
                    "rate_char1": char1_rate,
                    "rate_char2": char2_rate,
                    "rate_char3": char3_rate,
                    "volume_char1": char1_volume,
                    "volume_char2": char2_volume,
                    "volume_char3": char3_volume,
                    "repeat_times": repeat_times,
                    "pause_between": pause_between
                }
                self.save_settings()
            
            # Clean up
            self.cleanup_temp_files(audio_files)
            
            return merged_audio, None, "✅ Multi-character story generated!"
            
        except Exception as e:
            print(f"Error in multi-character processing: {e}")
            return None, None, f"❌ Error: {str(e)}"

# ==================== DIALOGUE PROCESSOR ====================
class DialogueTTSProcessor(BaseTTSProcessor):
    """Processor for Q&A dialogues"""
    
    def __init__(self):
        super().__init__()
    
    def parse_dialogues(self, content: str) -> List[Tuple[str, str]]:
        """Parse Q&A dialogues"""
        dialogues = []
        lines = content.split('\n')
        current_speaker = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.upper().startswith("Q:"):
                if current_speaker is not None:
                    dialogues.append((current_speaker, " ".join(current_text)))
                current_speaker = "Q"
                current_text = [line[2:].strip()]
            elif line.upper().startswith("A:"):
                if current_speaker is not None:
                    dialogues.append((current_speaker, " ".join(current_text)))
                current_speaker = "A"
                current_text = [line[2:].strip()]
            elif current_speaker is not None:
                current_text.append(line)
        
        if current_speaker is not None:
            dialogues.append((current_speaker, " ".join(current_text)))
        
        return dialogues
    
    async def process_dialogues(self, content: str, voice_q: str, voice_a: str,
                              rate_q: int, rate_a: int, volume_q: int, volume_a: int,
                              repeat_times: int, pause_q: int, pause_a: int,
                              save_settings: bool) -> Tuple[Optional[str], Optional[str], str]:
        """Process Q&A dialogues"""
        try:
            # Parse dialogues
            dialogues = self.parse_dialogues(content)
            if not dialogues:
                return None, None, "❌ No dialogues found"
            
            # Generate audio
            audio_files = []
            
            for speaker, text in dialogues:
                if not text:
                    continue
                    
                if speaker == "Q":
                    voice_id = self.voice_map.get(voice_q)
                    rate = rate_q
                    volume = volume_q
                else:  # "A"
                    voice_id = self.voice_map.get(voice_a)
                    rate = rate_a
                    volume = volume_a
                
                if not voice_id:
                    continue
                
                temp_file, _ = await self.generate_speech(text, voice_id, rate, 0, volume)
                if temp_file and os.path.exists(temp_file):
                    audio_files.append((speaker, temp_file))
            
            if not audio_files:
                return None, None, "❌ Failed to generate audio"
            
            # Create output with repetition
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"output_dialogue_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Prepare files for merging
            files_to_merge = []
            for _ in range(repeat_times):
                for speaker, file_path in audio_files:
                    files_to_merge.append(file_path)
            
            merged_audio = os.path.join(output_dir, "dialogue.mp3")
            
            # Simple merge - use first file if pydub not available
            if PYDUB_AVAILABLE and len(files_to_merge) > 0:
                merged = AudioSegment.empty()
                for i, file_path in enumerate(files_to_merge):
                    if os.path.exists(file_path):
                        audio = AudioSegment.from_file(file_path)
                        merged += audio
                        
                        # Add pause based on speaker
                        if i < len(files_to_merge) - 1:
                            next_speaker = audio_files[(i + 1) % len(audio_files)][0]
                            pause_duration = pause_q if next_speaker == "Q" else pause_a
                            merged += AudioSegment.silent(duration=pause_duration)
                
                merged.export(merged_audio, format="mp3", bitrate="256k")
            else:
                # Fallback
                if files_to_merge and os.path.exists(files_to_merge[0]):
                    import shutil
                    shutil.copy2(files_to_merge[0], merged_audio)
                else:
                    merged_audio = None
            
            # Save settings
            if save_settings:
                self.settings["dialogue"] = {
                    "voice_q": voice_q,
                    "voice_a": voice_a,
                    "rate_q": rate_q,
                    "rate_a": rate_a,
                    "volume_q": volume_q,
                    "volume_a": volume_a,
                    "repeat_times": repeat_times,
                    "pause_q": pause_q,
                    "pause_a": pause_a
                }
                self.save_settings()
            
            # Clean up
            for _, file_path in audio_files:
                self.cleanup_temp_files([file_path])
            
            if not merged_audio or not os.path.exists(merged_audio):
                return None, None, "❌ Failed to create merged audio"
            
            return merged_audio, None, "✅ Dialogue generated successfully!"
            
        except Exception as e:
            print(f"Error in dialogue processing: {e}")
            return None, None, f"❌ Error: {str(e)}"

# ==================== HELPER FUNCTIONS ====================
def update_voice_dropdown(language: str, tab_type: str = "single") -> gr.Dropdown:
    """Update voice dropdown based on selected language"""
    processor = BaseTTSProcessor()
    voice_options = [v for v in processor.voice_map.keys() if v.startswith(language)]
    
    if voice_options:
        return gr.Dropdown(choices=voice_options, value=voice_options[0])
    return gr.Dropdown(choices=[])

def show_subtitles(audio_path: str) -> str:
    """Show subtitles for audio file"""
    if not audio_path or not isinstance(audio_path, str):
        return "No audio file available"
    
    srt_path = audio_path.replace('.mp3', '.srt')
    if os.path.exists(srt_path):
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading subtitles: {e}"
    else:
        return "No subtitles available"

# ==================== GRADIO INTERFACE ====================
def create_interface():
    """Create Gradio interface"""
    if not GRADIO_AVAILABLE:
        print("Gradio not available")
        return None
    
    # Initialize processors
    single_processor = StoryTTSProcessor()
    multi_processor = MultiCharacterTTSProcessor()
    dialogue_processor = DialogueTTSProcessor()
    
    # Load default settings
    default_settings = TTSConfig.get_default_settings()
    single_settings = default_settings["single_char"]
    multi_settings = default_settings["multi_char"]
    dialogue_settings = default_settings["dialogue"]
    
    with gr.Blocks(title="TTS Story Generator", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🎵 TTS Story Generator")
        gr.Markdown("Generate audio stories with text-to-speech")
        
        with gr.Tabs():
            # ========== TAB 1: SINGLE CHARACTER ==========
            with gr.Tab("📖 Single Character"):
                with gr.Row():
                    with gr.Column(scale=2):
                        content = gr.Textbox(
                            label="Story Content",
                            lines=10,
                            placeholder="Enter your story here... Each sentence will be on a new line.",
                            value="Once upon a time, in a faraway land, there was a beautiful princess.\nShe lived in a castle surrounded by a magical forest."
                        )
                        
                        with gr.Row():
                            language = gr.Dropdown(
                                label="Language",
                                choices=list(TTSConfig.LANGUAGES.keys()),
                                value=single_settings["language"]
                            )
                            voice = gr.Dropdown(
                                label="Voice",
                                choices=[v for v in single_processor.voice_map.keys() 
                                        if v.startswith(single_settings["language"])],
                                value=single_settings["voice"]
                            )
                        
                        with gr.Row():
                            rate = gr.Slider(
                                label="Speed (%)",
                                minimum=-30,
                                maximum=30,
                                step=1,
                                value=single_settings["rate"]
                            )
                            volume = gr.Slider(
                                label="Volume (%)",
                                minimum=50,
                                maximum=150,
                                step=1,
                                value=single_settings["volume"]
                            )
                        
                        pause = gr.Slider(
                            label="Pause between sentences (ms)",
                            minimum=100,
                            maximum=2000,
                            step=50,
                            value=single_settings["pause"]
                        )
                        
                        save_settings = gr.Checkbox(
                            label="Save settings",
                            value=False
                        )
                        
                        generate_btn = gr.Button(
                            "Generate Audio",
                            variant="primary",
                            size="lg"
                        )
                    
                    with gr.Column(scale=1):
                        audio_output = gr.Audio(
                            label="Generated Audio",
                            type="filepath"
                        )
                        
                        status = gr.Textbox(
                            label="Status",
                            interactive=False
                        )
                        
                        with gr.Accordion("Subtitles", open=False):
                            subtitles_display = gr.Textbox(
                                label="SRT Content",
                                lines=10,
                                interactive=False
                            )
            
            # ========== TAB 2: MULTI CHARACTER ==========
            with gr.Tab("👥 Multi Character"):
                with gr.Row():
                    with gr.Column(scale=2):
                        content = gr.Textbox(
                            label="Story with Characters",
                            lines=10,
                            placeholder="CHAR1: Dialogue for character 1\nCHAR2: Dialogue for character 2\nCHAR3: Dialogue for character 3\nNARRATOR: Narration text",
                            value="CHAR1: Hello, how are you?\nCHAR2: I'm fine, thank you!\nNARRATOR: They continued their conversation."
                        )
                        
                        with gr.Row():
                            char1_lang = gr.Dropdown(
                                label="Character 1 Language",
                                choices=list(TTSConfig.LANGUAGES.keys()),
                                value=multi_settings["language_char1"]
                            )
                            char1_voice = gr.Dropdown(
                                label="Character 1 Voice",
                                choices=[v for v in multi_processor.voice_map.keys() 
                                        if v.startswith(multi_settings["language_char1"])],
                                value=multi_settings["voice_char1"]
                            )
                        
                        with gr.Row():
                            char2_lang = gr.Dropdown(
                                label="Character 2 Language",
                                choices=list(TTSConfig.LANGUAGES.keys()),
                                value=multi_settings["language_char2"]
                            )
                            char2_voice = gr.Dropdown(
                                label="Character 2 Voice",
                                choices=[v for v in multi_processor.voice_map.keys() 
                                        if v.startswith(multi_settings["language_char2"])],
                                value=multi_settings["voice_char2"]
                            )
                        
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
                        
                        with gr.Row():
                            repeat_times = gr.Slider(
                                label="Repeat Times",
                                minimum=1,
                                maximum=5,
                                step=1,
                                value=multi_settings["repeat_times"]
                            )
                            pause_between = gr.Slider(
                                label="Pause Between (ms)",
                                minimum=100,
                                maximum=2000,
                                step=50,
                                value=multi_settings["pause_between"]
                            )
                        
                        save_settings_multi = gr.Checkbox(
                            label="Save settings",
                            value=False
                        )
                        
                        generate_multi_btn = gr.Button(
                            "Generate Multi-Character Audio",
                            variant="primary",
                            size="lg"
                        )
                    
                    with gr.Column(scale=1):
                        audio_output_multi = gr.Audio(
                            label="Generated Audio",
                            type="filepath"
                        )
                        
                        status_multi = gr.Textbox(
                            label="Status",
                            interactive=False
                        )
            
            # ========== TAB 3: Q&A DIALOGUE ==========
            with gr.Tab("💬 Q&A Dialogue"):
                with gr.Row():
                    with gr.Column(scale=2):
                        content = gr.Textbox(
                            label="Q&A Dialogue",
                            lines=10,
                            placeholder="Q: Question text\nA: Answer text\nQ: Next question\nA: Next answer",
                            value="Q: What is your name?\nA: My name is AI Assistant.\nQ: What can you do?\nA: I can help you generate audio stories."
                        )
                        
                        with gr.Row():
                            q_lang = gr.Dropdown(
                                label="Question Language",
                                choices=list(TTSConfig.LANGUAGES.keys()),
                                value=dialogue_settings["language_q"]
                            )
                            q_voice = gr.Dropdown(
                                label="Question Voice",
                                choices=[v for v in dialogue_processor.voice_map.keys() 
                                        if v.startswith(dialogue_settings["language_q"])],
                                value=dialogue_settings["voice_q"]
                            )
                        
                        with gr.Row():
                            a_lang = gr.Dropdown(
                                label="Answer Language",
                                choices=list(TTSConfig.LANGUAGES.keys()),
                                value=dialogue_settings["language_a"]
                            )
                            a_voice = gr.Dropdown(
                                label="Answer Voice",
                                choices=[v for v in dialogue_processor.voice_map.keys() 
                                        if v.startswith(dialogue_settings["language_a"])],
                                value=dialogue_settings["voice_a"]
                            )
                        
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
                        
                        with gr.Row():
                            repeat_dialogue = gr.Slider(
                                label="Repeat Times",
                                minimum=1,
                                maximum=5,
                                step=1,
                                value=dialogue_settings["repeat_times"]
                            )
                            pause_q = gr.Slider(
                                label="Pause After Q (ms)",
                                minimum=100,
                                maximum=1000,
                                step=50,
                                value=dialogue_settings["pause_q"]
                            )
                        
                        save_settings_dialogue = gr.Checkbox(
                            label="Save settings",
                            value=False
                        )
                        
                        generate_dialogue_btn = gr.Button(
                            "Generate Dialogue Audio",
                            variant="primary",
                            size="lg"
                        )
                    
                    with gr.Column(scale=1):
                        audio_output_dialogue = gr.Audio(
                            label="Generated Audio",
                            type="filepath"
                        )
                        
                        status_dialogue = gr.Textbox(
                            label="Status",
                            interactive=False
                        )
        
        # ========== EVENT HANDLERS ==========
        
        # Tab 1: Single Character
        language.change(
            lambda lang: update_voice_dropdown(lang, "single"),
            inputs=language,
            outputs=voice
        )
        
        generate_btn.click(
            single_processor.process_story,
            inputs=[content, voice, rate, 0, volume, pause, save_settings],
            outputs=[audio_output, audio_output, status]
        ).then(
            show_subtitles,
            inputs=audio_output,
            outputs=subtitles_display
        )
        
        # Tab 2: Multi Character
        char1_lang.change(
            lambda lang: update_voice_dropdown(lang, "multi"),
            inputs=char1_lang,
            outputs=char1_voice
        )
        
        char2_lang.change(
            lambda lang: update_voice_dropdown(lang, "multi"),
            inputs=char2_lang,
            outputs=char2_voice
        )
        
        generate_multi_btn.click(
            multi_processor.process_story,
            inputs=[content, char1_voice, char2_voice, char1_voice,
                   char1_rate, char2_rate, char1_rate,
                   char1_volume, char2_volume, char1_volume,
                   repeat_times, pause_between, save_settings_multi],
            outputs=[audio_output_multi, audio_output_multi, status_multi]
        )
        
        # Tab 3: Q&A Dialogue
        q_lang.change(
            lambda lang: update_voice_dropdown(lang, "dialogue"),
            inputs=q_lang,
            outputs=q_voice
        )
        
        a_lang.change(
            lambda lang: update_voice_dropdown(lang, "dialogue"),
            inputs=a_lang,
            outputs=a_voice
        )
        
        generate_dialogue_btn.click(
            dialogue_processor.process_dialogues,
            inputs=[content, q_voice, a_voice, q_rate, a_rate,
                   q_volume, a_volume, repeat_dialogue, pause_q, 500,
                   save_settings_dialogue],
            outputs=[audio_output_dialogue, audio_output_dialogue, status_dialogue]
        )
        
        # ========== FOOTER ==========
        gr.Markdown("---")
        gr.Markdown(
            """
            **Tips:**
            - Use clear punctuation for better speech synthesis
            - Adjust pause duration for natural pacing
            - Save your favorite voice settings for future use
            - Generated files are stored temporarily
            """
        )
    
    return app

# ==================== MAIN ENTRY POINT ====================
def main():
    """Main application entry point"""
    print("=" * 50)
    print("TTS Story Generator")
    print(f"Python: {sys.version}")
    print(f"Gradio available: {GRADIO_AVAILABLE}")
    print(f"Edge TTS available: {EDGE_TTS_AVAILABLE}")
    print(f"Pydub available: {PYDUB_AVAILABLE}")
    print("=" * 50)
    
    # Create output directories
    os.makedirs("temp_audio", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    # Clean up old temp files
    for temp_dir in ["temp_audio", "output_*"]:
        try:
            import shutil, glob
            for dir_path in glob.glob(temp_dir):
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
        except:
            pass
    
    # Create and launch app
    app = create_interface()
    if app:
        # Get port from environment variable (for Render/Heroku)
        port = int(os.environ.get("PORT", 7860))
        host = os.environ.get("HOST", "0.0.0.0")
        
        print(f"🚀 Launching app on {host}:{port}")
        app.launch(
            server_name=host,
            server_port=port,
            share=False,
            debug=False,
            show_error=True
        )
    else:
        print("❌ Failed to create Gradio interface")
        sys.exit(1)

if __name__ == "__main__":
    # Set asyncio policy for Windows compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run main function
    main()
