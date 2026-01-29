"""
TTS Story Generator - Phiên bản đầy đủ với tất cả các tab
"""

import streamlit as st
import edge_tts
import os
import re
import asyncio
import tempfile
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import natsort
import base64

# ==================== CẤU HÌNH ====================
st.set_page_config(
    page_title="TTS Story Generator Pro",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CÁC CLASS CHÍNH ====================
class TextPreprocessor:
    """Tiền xử lý văn bản"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Làm sạch văn bản"""
        if not text:
            return ""
        
        # Chuẩn hóa ký tự
        replacements = {
            '’': "'", '‘': "'", '´': "'", '`': "'",
            '＂': '"', '＂': '"', '“': '"', '”': '"',
            '…': '...', '–': '-', '—': '-', '～': '~'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Chuẩn hóa khoảng trắng
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def split_into_lines(text: str) -> List[str]:
        """Tách văn bản thành các dòng"""
        return [line.strip() for line in text.split('\n') if line.strip()]
    
    @staticmethod
    def parse_dialogues(text: str, prefixes: List[str]) -> List[Tuple[str, str]]:
        """Phân tích hội thoại với các prefix"""
        dialogues = []
        current_speaker = None
        current_text = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Kiểm tra prefix
            found_prefix = None
            for prefix in prefixes:
                if line.lower().startswith(prefix.lower() + ':'):
                    found_prefix = prefix
                    break
            
            if found_prefix:
                if current_speaker is not None:
                    dialogues.append((current_speaker, ' '.join(current_text)))
                current_speaker = found_prefix
                content = line[len(found_prefix)+1:].strip()
                current_text = [content] if content else []
            elif current_speaker is not None:
                current_text.append(line)
        
        if current_speaker is not None and current_text:
            dialogues.append((current_speaker, ' '.join(current_text)))
        
        return dialogues

class AudioProcessor:
    """Xử lý audio"""
    
    @staticmethod
    def enhance_audio(audio_path: str, volume: int = 100) -> str:
        """Cải thiện chất lượng audio"""
        try:
            audio = AudioSegment.from_file(audio_path)
            
            # Điều chỉnh volume
            if volume != 100:
                change_in_db = volume - 100
                if change_in_db != 0:
                    audio = audio + change_in_db
            
            # Chuẩn hóa
            audio = normalize(audio)
            
            # Nén động
            audio = compress_dynamic_range(audio)
            
            # Thêm fade
            audio = audio.fade_in(50).fade_out(50)
            
            # Lưu file mới
            enhanced_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
            audio.export(enhanced_path, format='mp3', bitrate='256k')
            
            return enhanced_path
            
        except Exception as e:
            st.error(f"Lỗi xử lý audio: {str(e)}")
            return audio_path
    
    @staticmethod
    def merge_audios(audio_paths: List[str], pause_duration: int = 500) -> str:
        """Ghép nhiều audio với khoảng nghỉ"""
        if not audio_paths:
            return None
        
        if len(audio_paths) == 1:
            return audio_paths[0]
        
        try:
            merged = AudioSegment.empty()
            pause = AudioSegment.silent(duration=pause_duration)
            
            for i, audio_path in enumerate(audio_paths):
                audio = AudioSegment.from_file(audio_path)
                merged += audio
                
                if i < len(audio_paths) - 1:
                    merged += pause
            
            merged_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
            merged.export(merged_path, format='mp3', bitrate='256k')
            
            return merged_path
            
        except Exception as e:
            st.error(f"Lỗi ghép audio: {str(e)}")
            return None

class TTSEngine:
    """Engine TTS chính"""
    
    # Danh sách giọng đầy đủ
    VOICES = {
        "Tiếng Việt": [
            {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "gender": "Nữ"},
            {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "gender": "Nam"}
        ],
        "English (US)": [
            {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Nữ"},
            {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Nam"},
            {"id": "en-US-AvaNeural", "name": "Ava", "gender": "Nữ"},
            {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "Nam"},
            {"id": "en-US-EmmaNeural", "name": "Emma", "gender": "Nữ"},
            {"id": "en-US-BrianNeural", "name": "Brian", "gender": "Nam"},
            {"id": "en-US-AnaNeural", "name": "Ana", "gender": "Nữ"}
        ],
        "English (UK)": [
            {"id": "en-GB-LibbyNeural", "name": "Libby", "gender": "Nữ"},
            {"id": "en-GB-MiaNeural", "name": "Mia", "gender": "Nữ"},
            {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "Nam"},
            {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "Nữ"}
        ]
    }
    
    def __init__(self):
        self.text_processor = TextPreprocessor()
        self.audio_processor = AudioProcessor()
    
    async def generate_speech(
        self,
        text: str,
        voice_id: str,
        rate: int = 0,
        pitch: int = 0,
        volume: int = 100
    ) -> Optional[str]:
        """Tạo giọng nói từ văn bản"""
        try:
            if not text or not text.strip():
                return None
            
            # Format parameters
            rate_str = f"{rate:+d}%"
            pitch_str = f"{pitch:+d}Hz"
            
            # Tạo file tạm
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.close()
            
            # Generate speech
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                rate=rate_str,
                pitch=pitch_str
            )
            
            await communicate.save(temp_file.name)
            
            # Cải thiện audio
            enhanced_file = self.audio_processor.enhance_audio(temp_file.name, volume)
            
            # Xóa file tạm gốc
            try:
                os.unlink(temp_file.name)
            except:
                pass
            
            return enhanced_file
            
        except Exception as e:
            st.error(f"Lỗi tạo giọng nói: {str(e)}")
            return None

# ==================== CÁC PROCESSOR CHO TỪNG TAB ====================
class SingleCharacterProcessor:
    """Xử lý cho tab 1 nhân vật"""
    
    def __init__(self, tts_engine: TTSEngine):
        self.tts_engine = tts_engine
    
    async def process(
        self,
        content: str,
        voice_id: str,
        rate: int,
        pitch: int,
        volume: int,
        pause: int,
        save_settings: bool = False
    ) -> Tuple[Optional[str], str]:
        """Xử lý nội dung 1 nhân vật"""
        try:
            # Tách thành các dòng
            lines = self.tts_engine.text_processor.split_into_lines(content)
            
            if not lines:
                return None, "❌ Không có nội dung để xử lý"
            
            # Tạo audio cho từng dòng
            audio_files = []
            
            for i, line in enumerate(lines):
                audio_file = await self.tts_engine.generate_speech(
                    text=line,
                    voice_id=voice_id,
                    rate=rate,
                    pitch=pitch,
                    volume=volume
                )
                
                if audio_file:
                    audio_files.append(audio_file)
            
            if not audio_files:
                return None, "❌ Không tạo được file âm thanh"
            
            # Ghép các audio lại
            merged_audio = self.tts_engine.audio_processor.merge_audios(audio_files, pause)
            
            if merged_audio:
                # Xóa các file tạm riêng lẻ
                for file in audio_files:
                    try:
                        os.unlink(file)
                    except:
                        pass
                
                return merged_audio, "✅ Hoàn thành! Bấm vào nút phát để nghe"
            else:
                return None, "❌ Không thể ghép audio"
                
        except Exception as e:
            return None, f"❌ Lỗi: {str(e)}"

class MultiCharacterProcessor:
    """Xử lý cho tab đa nhân vật"""
    
    def __init__(self, tts_engine: TTSEngine):
        self.tts_engine = tts_engine
    
    def parse_story(self, content: str) -> List[Tuple[str, str]]:
        """Phân tích câu chuyện đa nhân vật"""
        dialogues = []
        current_character = None
        current_text = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Kiểm tra các prefix
            prefixes = ["CHAR1:", "CHAR2:", "CHAR3:", "NARRATOR:"]
            found_prefix = None
            
            for prefix in prefixes:
                if line.upper().startswith(prefix):
                    found_prefix = prefix.rstrip(':')
                    break
            
            if found_prefix:
                if current_character is not None:
                    dialogues.append((current_character, ' '.join(current_text)))
                current_character = found_prefix
                content = line[len(found_prefix)+1:].strip()
                current_text = [content] if content else []
            elif current_character is not None:
                current_text.append(line)
        
        if current_character is not None and current_text:
            dialogues.append((current_character, ' '.join(current_text)))
        
        return dialogues
    
    async def process(
        self,
        content: str,
        char1_voice: str,
        char2_voice: str,
        char3_voice: str,
        char1_rate: int,
        char2_rate: int,
        char3_rate: int,
        char1_pitch: int,
        char2_pitch: int,
        char3_pitch: int,
        char1_volume: int,
        char2_volume: int,
        char3_volume: int,
        repeat_times: int,
        pause_between: int,
        save_settings: bool = False
    ) -> Tuple[Optional[str], str]:
        """Xử lý nội dung đa nhân vật"""
        try:
            # Phân tích câu chuyện
            dialogues = self.parse_story(content)
            
            if not dialogues:
                return None, "❌ Không có nội dung hội thoại"
            
            # Tạo audio cho từng đoạn
            audio_files = []
            
            for character, text in dialogues:
                # Chọn giọng dựa trên nhân vật
                if character == "CHAR1":
                    voice_id = char1_voice
                    rate = char1_rate
                    pitch = char1_pitch
                    volume = char1_volume
                elif character == "CHAR2":
                    voice_id = char2_voice
                    rate = char2_rate
                    pitch = char2_pitch
                    volume = char2_volume
                elif character == "CHAR3":
                    voice_id = char3_voice
                    rate = char3_rate
                    pitch = char3_pitch
                    volume = char3_volume
                else:  # NARRATOR
                    voice_id = char1_voice  # Mặc định dùng giọng CHAR1
                    rate = char1_rate
                    pitch = char1_pitch
                    volume = char1_volume
                
                audio_file = await self.tts_engine.generate_speech(
                    text=text,
                    voice_id=voice_id,
                    rate=rate,
                    pitch=pitch,
                    volume=volume
                )
                
                if audio_file:
                    audio_files.append(audio_file)
            
            if not audio_files:
                return None, "❌ Không tạo được file âm thanh"
            
            # Lặp lại nếu cần
            if repeat_times > 1:
                original_files = audio_files.copy()
                for _ in range(repeat_times - 1):
                    audio_files.extend(original_files)
            
            # Ghép các audio lại
            merged_audio = self.tts_engine.audio_processor.merge_audios(audio_files, pause_between)
            
            if merged_audio:
                # Xóa các file tạm riêng lẻ
                for file in audio_files:
                    try:
                        os.unlink(file)
                    except:
                        pass
                
                return merged_audio, "✅ Hoàn thành! Bấm vào nút phát để nghe"
            else:
                return None, "❌ Không thể ghép audio"
                
        except Exception as e:
            return None, f"❌ Lỗi: {str(e)}"

class DialogueProcessor:
    """Xử lý cho tab hỏi đáp"""
    
    def __init__(self, tts_engine: TTSEngine):
        self.tts_engine = tts_engine
    
    def parse_dialogues(self, content: str) -> List[Tuple[str, str]]:
        """Phân tích hội thoại Q&A"""
        return self.tts_engine.text_processor.parse_dialogues(content, ["Q", "A"])
    
    async def process(
        self,
        content: str,
        voice_q: str,
        voice_a: str,
        rate_q: int,
        rate_a: int,
        pitch_q: int,
        pitch_a: int,
        volume_q: int,
        volume_a: int,
        repeat_times: int,
        pause_q: int,
        pause_a: int,
        save_settings: bool = False
    ) -> Tuple[Optional[str], str]:
        """Xử lý hội thoại Q&A"""
        try:
            # Phân tích hội thoại
            dialogues = self.parse_dialogues(content)
            
            if not dialogues:
                return None, "❌ Không có nội dung hội thoại"
            
            # Tạo audio cho từng cặp Q/A
            audio_files = []
            pause_durations = []
            
            for speaker, text in dialogues:
                # Chọn giọng dựa trên speaker
                if speaker.upper() == "Q":
                    voice_id = voice_q
                    rate = rate_q
                    pitch = pitch_q
                    volume = volume_q
                    next_pause = pause_q
                else:  # "A"
                    voice_id = voice_a
                    rate = rate_a
                    pitch = pitch_a
                    volume = volume_a
                    next_pause = pause_a
                
                audio_file = await self.tts_engine.generate_speech(
                    text=text,
                    voice_id=voice_id,
                    rate=rate,
                    pitch=pitch,
                    volume=volume
                )
                
                if audio_file:
                    audio_files.append(audio_file)
                    pause_durations.append(next_pause)
            
            if not audio_files:
                return None, "❌ Không tạo được file âm thanh"
            
            # Lặp lại nếu cần
            if repeat_times > 1:
                original_files = audio_files.copy()
                original_pauses = pause_durations.copy()
                for _ in range(repeat_times - 1):
                    audio_files.extend(original_files)
                    pause_durations.extend(original_pauses)
            
            # Ghép các audio lại với các khoảng nghỉ khác nhau
            merged_audio = self.merge_with_variable_pauses(audio_files, pause_durations)
            
            if merged_audio:
                # Xóa các file tạm riêng lẻ
                for file in audio_files:
                    try:
                        os.unlink(file)
                    except:
                        pass
                
                return merged_audio, "✅ Hoàn thành! Bấm vào nút phát để nghe"
            else:
                return None, "❌ Không thể ghép audio"
                
        except Exception as e:
            return None, f"❌ Lỗi: {str(e)}"
    
    def merge_with_variable_pauses(self, audio_files: List[str], pauses: List[int]) -> Optional[str]:
        """Ghép audio với các khoảng nghỉ khác nhau"""
        if not audio_files:
            return None
        
        try:
            merged = AudioSegment.empty()
            
            for i, audio_path in enumerate(audio_files):
                audio = AudioSegment.from_file(audio_path)
                merged += audio
                
                if i < len(audio_files) - 1 and i < len(pauses):
                    merged += AudioSegment.silent(duration=pauses[i])
            
            merged_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
            merged.export(merged_path, format='mp3', bitrate='256k')
            
            return merged_path
            
        except Exception as e:
            st.error(f"Lỗi ghép audio: {str(e)}")
            return None

# ==================== STREAMLIT APP ====================
class TTSApp:
    """Ứng dụng Streamlit chính"""
    
    def __init__(self):
        self.tts_engine = TTSEngine()
        self.single_processor = SingleCharacterProcessor(self.tts_engine)
        self.multi_processor = MultiCharacterProcessor(self.tts_engine)
        self.dialogue_processor = DialogueProcessor(self.tts_engine)
        self.init_session_state()
    
    def init_session_state(self):
        """Khởi tạo session state"""
        defaults = {
            'history': [],
            'current_audio': None,
            'current_text': "",
            'mode': 'single',
            'settings_single': {
                "voice": "vi-VN-HoaiMyNeural",
                "rate": 0,
                "pitch": 0,
                "volume": 100,
                "pause": 500
            },
            'settings_multi': {
                "char1_voice": "vi-VN-HoaiMyNeural",
                "char2_voice": "vi-VN-NamMinhNeural",
                "char3_voice": "vi-VN-HoaiMyNeural",
                "char1_rate": -20,
                "char2_rate": -25,
                "char3_rate": -15,
                "char1_pitch": 0,
                "char2_pitch": 0,
                "char3_pitch": 0,
                "char1_volume": 100,
                "char2_volume": 100,
                "char3_volume": 100,
                "repeat_times": 1,
                "pause_between": 500
            },
            'settings_dialogue': {
                "voice_q": "vi-VN-HoaiMyNeural",
                "voice_a": "vi-VN-NamMinhNeural",
                "rate_q": -20,
                "rate_a": -25,
                "pitch_q": 0,
                "pitch_a": 0,
                "volume_q": 100,
                "volume_a": 100,
                "repeat_times": 2,
                "pause_q": 200,
                "pause_a": 500
            }
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def get_voice_display_name(self, voice_id: str) -> str:
        """Lấy tên hiển thị của giọng"""
        for lang, voices in self.tts_engine.VOICES.items():
            for voice in voices:
                if voice["id"] == voice_id:
                    return f"{lang} - {voice['name']} ({voice['gender']})"
        return voice_id
    
    def render_sidebar(self):
        """Render sidebar"""
        with st.sidebar:
            st.title("📖 TTS Story Generator")
            st.markdown("---")
            
            # Chọn tab
            mode = st.radio(
                "Chọn chế độ",
                ["🎤 1 Nhân vật", "👥 Đa nhân vật", "💬 Hỏi & Đáp"],
                key="mode_selector"
            )
            
            # Map mode
            mode_map = {
                "🎤 1 Nhân vật": "single",
                "👥 Đa nhân vật": "multi",
                "💬 Hỏi & Đáp": "dialogue"
            }
            st.session_state.mode = mode_map[mode]
            
            st.markdown("---")
            
            # Cài đặt chung
            with st.expander("⚙️ Thông tin", expanded=False):
                st.caption("**Phiên bản:** 1.0.0")
                st.caption("**Edge TTS:** 7.2.0")
                st.caption("**Hỗ trợ:** Đa ngôn ngữ")
                st.caption("**Định dạng:** MP3")
            
            st.markdown("---")
            
            # History
            if st.session_state.history:
                with st.expander("📜 Lịch sử", expanded=False):
                    for i, item in enumerate(st.session_state.history[-3:][::-1]):
                        btn_text = f"{i+1}. {item['text'][:30]}..."
                        if st.button(btn_text, key=f"hist_{i}", use_container_width=True):
                            st.session_state.current_text = item['text']
                            st.rerun()
            
            st.markdown("---")
            st.caption("Made with ❤️ by TTS Generator")
    
    def render_single_character_tab(self):
        """Tab 1: 1 Nhân vật"""
        st.header("🎤 1 Nhân vật")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Input text
            content = st.text_area(
                "Nội dung truyện",
                value=st.session_state.current_text,
                height=300,
                placeholder="Nhập nội dung truyện (mỗi dòng là một đoạn)...",
                key="single_content"
            )
            
            # Voice settings
            with st.expander("🎙️ Cài đặt giọng", expanded=True):
                languages = list(self.tts_engine.VOICES.keys())
                selected_lang = st.selectbox(
                    "Ngôn ngữ",
                    languages,
                    index=0,
                    key="single_lang"
                )
                
                voices = self.tts_engine.VOICES[selected_lang]
                voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
                
                selected_voice_name = st.selectbox(
                    "Giọng đọc",
                    list(voice_options.keys()),
                    key="single_voice"
                )
                
                selected_voice_id = voice_options[selected_voice_name]
            
            # Audio settings
            with st.expander("🎛️ Điều chỉnh âm thanh", expanded=True):
                col_rate, col_pitch, col_volume = st.columns(3)
                with col_rate:
                    rate = st.slider("Tốc độ (%)", -30, 30, 0, key="single_rate")
                with col_pitch:
                    pitch = st.slider("Cao độ (Hz)", -30, 30, 0, key="single_pitch")
                with col_volume:
                    volume = st.slider("Âm lượng (%)", 50, 150, 100, key="single_volume")
                
                pause = st.slider("Khoảng nghỉ (ms)", 100, 2000, 500, key="single_pause")
            
            # Options
            save_settings = st.checkbox("Lưu cài đặt", value=False, key="single_save")
            
            # Generate button
            if st.button("🎤 Tạo truyện audio", type="primary", use_container_width=True):
                if not content.strip():
                    st.warning("Vui lòng nhập nội dung")
                    return
                
                self.generate_single_character(
                    content=content,
                    voice_id=selected_voice_id,
                    rate=rate,
                    pitch=pitch,
                    volume=volume,
                    pause=pause,
                    save_settings=save_settings
                )
        
        with col2:
            self.render_audio_player()
    
    def render_multi_character_tab(self):
        """Tab 2: Đa nhân vật"""
        st.header("👥 Đa nhân vật")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Input text
            content = st.text_area(
                "Nội dung câu chuyện",
                height=300,
                placeholder="CHAR1: Lời thoại nhân vật 1\nCHAR2: Lời thoại nhân vật 2\nCHAR3: Lời thoại nhân vật 3\nNARRATOR: Lời dẫn truyện",
                key="multi_content"
            )
            
            # Character settings
            with st.expander("🎭 Cài đặt nhân vật", expanded=True):
                st.subheader("Nhân vật 1 (CHAR1)")
                col_char1a, col_char1b = st.columns(2)
                with col_char1a:
                    char1_lang = st.selectbox(
                        "Ngôn ngữ NV1",
                        list(self.tts_engine.VOICES.keys()),
                        index=0,
                        key="char1_lang"
                    )
                    voices = self.tts_engine.VOICES[char1_lang]
                    voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
                    char1_voice_name = st.selectbox("Giọng NV1", list(voice_options.keys()), key="char1_voice")
                    char1_voice = voice_options[char1_voice_name]
                with col_char1b:
                    char1_rate = st.slider("Tốc độ (%)", -30, 30, -20, key="char1_rate")
                    char1_volume = st.slider("Âm lượng (%)", 50, 150, 100, key="char1_volume")
                
                st.subheader("Nhân vật 2 (CHAR2)")
                col_char2a, col_char2b = st.columns(2)
                with col_char2a:
                    char2_lang = st.selectbox(
                        "Ngôn ngữ NV2",
                        list(self.tts_engine.VOICES.keys()),
                        index=0,
                        key="char2_lang"
                    )
                    voices = self.tts_engine.VOICES[char2_lang]
                    voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
                    char2_voice_name = st.selectbox("Giọng NV2", list(voice_options.keys()), key="char2_voice")
                    char2_voice = voice_options[char2_voice_name]
                with col_char2b:
                    char2_rate = st.slider("Tốc độ (%)", -30, 30, -25, key="char2_rate")
                    char2_volume = st.slider("Âm lượng (%)", 50, 150, 100, key="char2_volume")
                
                st.subheader("Nhân vật 3 (CHAR3)")
                col_char3a, col_char3b = st.columns(2)
                with col_char3a:
                    char3_lang = st.selectbox(
                        "Ngôn ngữ NV3",
                        list(self.tts_engine.VOICES.keys()),
                        index=0,
                        key="char3_lang"
                    )
                    voices = self.tts_engine.VOICES[char3_lang]
                    voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
                    char3_voice_name = st.selectbox("Giọng NV3", list(voice_options.keys()), key="char3_voice")
                    char3_voice = voice_options[char3_voice_name]
                with col_char3b:
                    char3_rate = st.slider("Tốc độ (%)", -30, 30, -15, key="char3_rate")
                    char3_volume = st.slider("Âm lượng (%)", 50, 150, 100, key="char3_volume")
            
            # General settings
            with st.expander("🔄 Cài đặt chung", expanded=False):
                repeat_times = st.slider("Số lần lặp", 1, 5, 1, key="multi_repeat")
                pause_between = st.slider("Khoảng nghỉ (ms)", 100, 2000, 500, key="multi_pause")
                save_settings = st.checkbox("Lưu cài đặt", value=False, key="multi_save")
            
            # Generate button
            if st.button("🎧 Tạo câu chuyện audio", type="primary", use_container_width=True):
                if not content.strip():
                    st.warning("Vui lòng nhập nội dung")
                    return
                
                self.generate_multi_character(
                    content=content,
                    char1_voice=char1_voice,
                    char2_voice=char2_voice,
                    char3_voice=char3_voice,
                    char1_rate=char1_rate,
                    char2_rate=char2_rate,
                    char3_rate=char3_rate,
                    char1_pitch=0,  # Để đơn giản
                    char2_pitch=0,
                    char3_pitch=0,
                    char1_volume=char1_volume,
                    char2_volume=char2_volume,
                    char3_volume=char3_volume,
                    repeat_times=repeat_times,
                    pause_between=pause_between,
                    save_settings=save_settings
                )
        
        with col2:
            self.render_audio_player()
    
    def render_dialogue_tab(self):
        """Tab 3: Hỏi & Đáp"""
        st.header("💬 Hỏi & Đáp")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Input text
            content = st.text_area(
                "Nội dung hội thoại",
                height=300,
                placeholder="Q: Câu hỏi\nA: Câu trả lời\nQ: Câu hỏi tiếp theo\nA: Câu trả lời tiếp theo",
                key="dialogue_content"
            )
            
            # Voice settings for Q
            with st.expander("❓ Giọng câu hỏi (Q)", expanded=True):
                q_lang = st.selectbox(
                    "Ngôn ngữ câu hỏi",
                    list(self.tts_engine.VOICES.keys()),
                    index=0,
                    key="q_lang"
                )
                voices = self.tts_engine.VOICES[q_lang]
                voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
                q_voice_name = st.selectbox("Giọng câu hỏi", list(voice_options.keys()), key="q_voice")
                q_voice = voice_options[q_voice_name]
                
                col_q1, col_q2 = st.columns(2)
                with col_q1:
                    rate_q = st.slider("Tốc độ Q (%)", -30, 30, -20, key="rate_q")
                with col_q2:
                    volume_q = st.slider("Âm lượng Q (%)", 50, 150, 100, key="volume_q")
            
            # Voice settings for A
            with st.expander("❗ Giọng câu trả lời (A)", expanded=True):
                a_lang = st.selectbox(
                    "Ngôn ngữ câu trả lời",
                    list(self.tts_engine.VOICES.keys()),
                    index=0,
                    key="a_lang"
                )
                voices = self.tts_engine.VOICES[a_lang]
                voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
                a_voice_name = st.selectbox("Giọng câu trả lời", list(voice_options.keys()), key="a_voice")
                a_voice = voice_options[a_voice_name]
                
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    rate_a = st.slider("Tốc độ A (%)", -30, 30, -25, key="rate_a")
                with col_a2:
                    volume_a = st.slider("Âm lượng A (%)", 50, 150, 100, key="volume_a")
            
            # General settings
            with st.expander("🔄 Cài đặt lặp lại", expanded=False):
                repeat_times = st.slider("Số lần lặp", 1, 5, 2, key="dialogue_repeat")
                pause_q = st.slider("Nghỉ sau câu hỏi (ms)", 100, 1000, 200, key="pause_q")
                pause_a = st.slider("Nghỉ sau câu trả lời (ms)", 100, 2000, 500, key="pause_a")
                save_settings = st.checkbox("Lưu cài đặt", value=False, key="dialogue_save")
            
            # Generate button
            if st.button("🎧 Tạo audio hội thoại", type="primary", use_container_width=True):
                if not content.strip():
                    st.warning("Vui lòng nhập nội dung")
                    return
                
                self.generate_dialogue(
                    content=content,
                    voice_q=q_voice,
                    voice_a=a_voice,
                    rate_q=rate_q,
                    rate_a=rate_a,
                    pitch_q=0,  # Để đơn giản
                    pitch_a=0,
                    volume_q=volume_q,
                    volume_a=volume_a,
                    repeat_times=repeat_times,
                    pause_q=pause_q,
                    pause_a=pause_a,
                    save_settings=save_settings
                )
        
        with col2:
            self.render_audio_player()
    
    def generate_single_character(self, **kwargs):
        """Tạo audio cho 1 nhân vật"""
        with st.spinner("Đang xử lý..."):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                audio_file, message = loop.run_until_complete(
                    self.single_processor.process(**kwargs)
                )
                
                if audio_file:
                    st.session_state.current_audio = audio_file
                    st.session_state.current_text = kwargs['content']
                    
                    # Lưu vào history
                    history_item = {
                        "text": kwargs['content'][:100] + ("..." if len(kwargs['content']) > 100 else ""),
                        "mode": "single",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.history.append(history_item)
                    
                    st.success(message)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(message)
                    
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")
    
    def generate_multi_character(self, **kwargs):
        """Tạo audio cho đa nhân vật"""
        with st.spinner("Đang xử lý..."):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                audio_file, message = loop.run_until_complete(
                    self.multi_processor.process(**kwargs)
                )
                
                if audio_file:
                    st.session_state.current_audio = audio_file
                    
                    # Lưu vào history
                    history_item = {
                        "text": kwargs['content'][:100] + ("..." if len(kwargs['content']) > 100 else ""),
                        "mode": "multi",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.history.append(history_item)
                    
                    st.success(message)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(message)
                    
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")
    
    def generate_dialogue(self, **kwargs):
        """Tạo audio cho hội thoại"""
        with st.spinner("Đang xử lý..."):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                audio_file, message = loop.run_until_complete(
                    self.dialogue_processor.process(**kwargs)
                )
                
                if audio_file:
                    st.session_state.current_audio = audio_file
                    
                    # Lưu vào history
                    history_item = {
                        "text": kwargs['content'][:100] + ("..." if len(kwargs['content']) > 100 else ""),
                        "mode": "dialogue",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.history.append(history_item)
                    
                    st.success(message)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(message)
                    
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")
    
    def render_audio_player(self):
        """Hiển thị audio player"""
        if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
            # Audio player
            st.audio(st.session_state.current_audio, format="audio/mp3")
            
            # Thông tin
            with st.expander("📊 Thông tin file", expanded=True):
                file_size = os.path.getsize(st.session_state.current_audio) / 1024
                st.write(f"**Kích thước:** {file_size:.1f} KB")
                st.write(f"**Thời gian tạo:** {datetime.now().strftime('%H:%M:%S')}")
            
            # Download button
            with open(st.session_state.current_audio, "rb") as f:
                audio_bytes = f.read()
            
            st.download_button(
                label="📥 Tải audio",
                data=audio_bytes,
                file_name=f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                mime="audio/mp3",
                use_container_width=True
            )
            
            # Clear button
            if st.button("🗑️ Xóa file", use_container_width=True):
                try:
                    os.unlink(st.session_state.current_audio)
                except:
                    pass
                st.session_state.current_audio = None
                st.rerun()
        
        else:
            st.info("👈 **Hướng dẫn:**")
            st.markdown("""
            1. Chọn chế độ phù hợp
            2. Nhập nội dung văn bản
            3. Cấu hình giọng nói và cài đặt
            4. Nhấn nút tạo audio
            5. Nghe và tải về
            """)
    
    def run(self):
        """Chạy ứng dụng chính"""
        # CSS tùy chỉnh
        st.markdown("""
        <style>
        .stApp {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .stButton > button {
            border-radius: 10px;
            font-weight: bold;
        }
        
        .stTextArea textarea {
            font-size: 16px;
            line-height: 1.6;
        }
        
        h1, h2, h3 {
            color: #1f77b4;
        }
        
        .tab-content {
            padding: 20px;
            background: #f8f9fa;
            border-radius: 15px;
            margin: 10px 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Header
        st.title("📖 TTS Story Generator Pro")
        st.markdown("Chuyển văn bản thành giọng nói với 3 chế độ khác nhau")
        
        # Render sidebar
        self.render_sidebar()
        
        # Tabs
        tab1, tab2, tab3 = st.tabs(["🎤 1 Nhân vật", "👥 Đa nhân vật", "💬 Hỏi & Đáp"])
        
        with tab1:
            self.render_single_character_tab()
        
        with tab2:
            self.render_multi_character_tab()
        
        with tab3:
            self.render_dialogue_tab()
        
        # Footer
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption("© 2024 TTS Generator")
        with col2:
            st.caption("Edge TTS 7.2.0")
        with col3:
            st.caption("Streamlit Cloud")

# ==================== MAIN ====================
def main():
    """Hàm chính"""
    try:
        app = TTSApp()
        app.run()
    except Exception as e:
        st.error(f"Đã xảy ra lỗi: {str(e)}")
        st.info("Vui lòng làm mới trang.")

if __name__ == "__main__":
    main()
