"""
TTS Story Generator - Streamlit Version
Phiên bản đơn giản hóa từ code Gradio gốc
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
    page_title="TTS Story Generator",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== LỚP XỬ LÝ VĂN BẢN ====================
class TextProcessor:
    """Xử lý văn bản (đơn giản hóa từ code gốc)"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Làm sạch văn bản"""
        if not text:
            return ""
        
        # Chuẩn hóa ký tự
        replacements = {
            '’': "'", '‘': "'", '´': "'",
            '`': "'", '＂': '"', '＂': '"',
            '“': '"', '”': '"', '…': '...',
            '–': '-', '—': '-', '～': '~'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Chuẩn hóa khoảng trắng
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def split_into_paragraphs(text: str) -> List[str]:
        """Tách văn bản thành các đoạn"""
        if not text:
            return []
        
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        return paragraphs
    
    @staticmethod
    def process_special_cases(text: str) -> str:
        """Xử lý các trường hợp đặc biệt (đơn giản hóa)"""
        # Xử lý số điện thoại
        text = re.sub(
            r'\b(\d{3})[-.]?(\d{3})[-.]?(\d{4})\b',
            lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}",
            text
        )
        
        # Xử lý email
        text = re.sub(
            r'\b[\w\.-]+@[\w\.-]+\.\w+\b',
            lambda m: m.group(0).replace('@', ' at ').replace('.', ' dot '),
            text
        )
        
        # Xử lý từ viết tắt thông dụng
        abbreviations = {
            r'\bMr\.': 'Mister',
            r'\bMrs\.': 'Misses',
            r'\bDr\.': 'Doctor',
            r'\bProf\.': 'Professor',
            r'\betc\.': 'et cetera',
            r'\be\.g\.': 'for example',
            r'\bi\.e\.': 'that is',
        }
        
        for pattern, replacement in abbreviations.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text

# ==================== LỚP XỬ LÝ AUDIO ====================
class AudioProcessor:
    """Xử lý audio (đơn giản hóa)"""
    
    @staticmethod
    def enhance_audio(audio_path: str, volume: int = 100) -> str:
        """Cải thiện chất lượng audio"""
        try:
            audio = AudioSegment.from_file(audio_path)
            
            # Điều chỉnh volume
            if volume != 100:
                change_in_db = volume - 100  # Đơn giản hóa
                audio = audio + change_in_db
            
            # Chuẩn hóa
            audio = normalize(audio)
            
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
        """Ghép nhiều audio"""
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

# ==================== CORE TTS ENGINE ====================
class TTSEngine:
    """Engine TTS chính"""
    
    # Danh sách giọng (đơn giản hóa)
    VOICES = {
        "Tiếng Việt": [
            {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "gender": "Nữ"},
            {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "gender": "Nam"}
        ],
        "English (US)": [
            {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Nữ"},
            {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Nam"},
            {"id": "en-US-AvaNeural", "name": "Ava", "gender": "Nữ"}
        ],
        "English (UK)": [
            {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "Nữ"},
            {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "Nam"}
        ]
    }
    
    def __init__(self):
        self.text_processor = TextProcessor()
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
            
            # Tiền xử lý văn bản
            processed_text = self.text_processor.clean_text(text)
            processed_text = self.text_processor.process_special_cases(processed_text)
            
            # Format parameters
            rate_str = f"{rate:+d}%"
            pitch_str = f"{pitch:+d}Hz"
            
            # Tạo file tạm
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_file.close()
            
            # Generate speech
            communicate = edge_tts.Communicate(
                text=processed_text,
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

# ==================== STREAMLIT APP ====================
class TTSApp:
    """Ứng dụng Streamlit chính"""
    
    def __init__(self):
        self.tts_engine = TTSEngine()
        self.init_session_state()
    
    def init_session_state(self):
        """Khởi tạo session state"""
        if 'history' not in st.session_state:
            st.session_state.history = []
        
        if 'current_audio' not in st.session_state:
            st.session_state.current_audio = None
        
        if 'current_text' not in st.session_state:
            st.session_state.current_text = ""
        
        if 'current_settings' not in st.session_state:
            st.session_state.current_settings = {
                "voice": "vi-VN-HoaiMyNeural",
                "rate": 0,
                "pitch": 0,
                "volume": 100,
                "pause": 500,
                "language": "Tiếng Việt"
            }
        
        if 'audio_files' not in st.session_state:
            st.session_state.audio_files = []
        
        if 'mode' not in st.session_state:
            st.session_state.mode = "single"
    
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
            
            # Chọn chế độ
            mode = st.radio(
                "Chế độ",
                ["🎤 1 Nhân vật", "👥 Đa nhân vật", "💬 Hỏi & Đáp"],
                index=0
            )
            
            # Map mode
            mode_map = {
                "🎤 1 Nhân vật": "single",
                "👥 Đa nhân vật": "multi",
                "💬 Hỏi & Đáp": "dialogue"
            }
            st.session_state.mode = mode_map[mode]
            
            st.markdown("---")
            
            # Cài đặt giọng
            with st.expander("🎙️ Cài đặt giọng", expanded=True):
                languages = list(self.tts_engine.VOICES.keys())
                selected_lang = st.selectbox(
                    "Ngôn ngữ",
                    languages,
                    index=0
                )
                
                voices = self.tts_engine.VOICES[selected_lang]
                voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
                
                selected_voice_name = st.selectbox(
                    "Giọng nói",
                    list(voice_options.keys())
                )
                
                selected_voice_id = voice_options[selected_voice_name]
            
            st.markdown("---")
            
            # Cài đặt âm thanh
            with st.expander("🎛️ Điều chỉnh âm thanh", expanded=True):
                rate = st.slider("Tốc độ", -50, 50, 0)
                pitch = st.slider("Cao độ", -50, 50, 0)
                volume = st.slider("Âm lượng", 50, 150, 100)
                pause = st.slider("Khoảng nghỉ (ms)", 100, 2000, 500)
            
            # Lưu cài đặt
            st.session_state.current_settings = {
                "voice": selected_voice_id,
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "pause": pause,
                "language": selected_lang
            }
            
            st.markdown("---")
            
            # History
            if st.session_state.history:
                with st.expander("📜 Lịch sử", expanded=False):
                    for i, item in enumerate(st.session_state.history[-3:][::-1]):
                        btn_text = f"{i+1}. {item['text'][:30]}..."
                        if st.button(btn_text, key=f"hist_{i}", use_container_width=True):
                            st.session_state.current_text = item['text']
                            st.session_state.current_settings = item['settings']
                            st.rerun()
            
            st.markdown("---")
            st.caption("Made with ❤️ by TTS Generator")
    
    def render_single_character_mode(self):
        """Chế độ 1 nhân vật"""
        st.header("🎤 1 Nhân vật")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Input text
            text = st.text_area(
                "Nội dung truyện",
                value=st.session_state.current_text,
                height=300,
                placeholder="Nhập nội dung truyện (mỗi dòng là một đoạn)...",
                help="Mỗi dòng sẽ được xử lý như một đoạn riêng biệt"
            )
            
            # Options
            with st.expander("⚙️ Tùy chọn", expanded=False):
                save_settings = st.checkbox("Lưu cài đặt", value=False)
                output_format = st.selectbox("Định dạng", ["MP3", "WAV"], index=0)
            
            # Generate button
            if st.button("🎤 Tạo truyện audio", type="primary", use_container_width=True):
                if not text.strip():
                    st.warning("Vui lòng nhập nội dung")
                    return
                
                self.generate_story(text, save_settings)
        
        with col2:
            self.render_audio_player()
    
    def render_multi_character_mode(self):
        """Chế độ đa nhân vật"""
        st.header("👥 Đa nhân vật")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Input text với định dạng đặc biệt
            text = st.text_area(
                "Nội dung câu chuyện",
                height=300,
                placeholder="CHAR1: Lời thoại nhân vật 1\nCHAR2: Lời thoại nhân vật 2\nCHAR3: Lời thoại nhân vật 3\nNARRATOR: Lời dẫn truyện",
                help="Sử dụng định dạng: CHAR1:, CHAR2:, CHAR3:, NARRATOR: để chỉ định người nói"
            )
            
            # Cài đặt cho các nhân vật
            with st.expander("🎭 Cài đặt nhân vật", expanded=False):
                st.info("Tất cả nhân vật sẽ dùng cùng giọng từ sidebar")
            
            # Generate button
            if st.button("🎧 Tạo câu chuyện audio", type="primary", use_container_width=True):
                if not text.strip():
                    st.warning("Vui lòng nhập nội dung")
                    return
                
                st.info("Chức năng đang phát triển...")
        
        with col2:
            self.render_audio_player()
    
    def render_dialogue_mode(self):
        """Chế độ hỏi đáp"""
        st.header("💬 Hỏi & Đáp")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Input text với định dạng Q/A
            text = st.text_area(
                "Nội dung hội thoại",
                height=300,
                placeholder="Q: Câu hỏi\nA: Câu trả lời\nQ: Câu hỏi tiếp theo\nA: Câu trả lời tiếp theo",
                help="Sử dụng Q: cho câu hỏi, A: cho câu trả lời"
            )
            
            # Cài đặt
            with st.expander("⚙️ Cài đặt", expanded=False):
                repeat_times = st.slider("Số lần lặp", 1, 5, 2)
                pause_q = st.slider("Nghỉ sau câu hỏi (ms)", 100, 1000, 200)
                pause_a = st.slider("Nghỉ sau câu trả lời (ms)", 100, 2000, 500)
            
            # Generate button
            if st.button("🎧 Tạo audio hội thoại", type="primary", use_container_width=True):
                if not text.strip():
                    st.warning("Vui lòng nhập nội dung")
                    return
                
                st.info("Chức năng đang phát triển...")
        
        with col2:
            self.render_audio_player()
    
    def generate_story(self, text: str, save_settings: bool = False):
        """Tạo story audio"""
        with st.spinner("Đang xử lý..."):
            try:
                # Tách thành các đoạn
                paragraphs = self.tts_engine.text_processor.split_into_paragraphs(text)
                
                if not paragraphs:
                    st.error("Không có nội dung để xử lý")
                    return
                
                # Tạo audio cho từng đoạn
                audio_files = []
                
                for i, paragraph in enumerate(paragraphs):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    audio_file = loop.run_until_complete(
                        self.tts_engine.generate_speech(
                            text=paragraph,
                            voice_id=st.session_state.current_settings["voice"],
                            rate=st.session_state.current_settings["rate"],
                            pitch=st.session_state.current_settings["pitch"],
                            volume=st.session_state.current_settings["volume"]
                        )
                    )
                    
                    if audio_file:
                        audio_files.append(audio_file)
                
                if not audio_files:
                    st.error("Không thể tạo audio")
                    return
                
                # Ghép các audio lại
                merged_audio = self.tts_engine.audio_processor.merge_audios(
                    audio_files, 
                    st.session_state.current_settings["pause"]
                )
                
                if merged_audio:
                    # Lưu vào session state
                    st.session_state.current_audio = merged_audio
                    st.session_state.current_text = text
                    
                    # Lưu vào history
                    history_item = {
                        "text": text[:100] + ("..." if len(text) > 100 else ""),
                        "settings": st.session_state.current_settings.copy(),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state.history.append(history_item)
                    
                    # Lưu cài đặt nếu cần
                    if save_settings:
                        self.save_settings_to_file()
                    
                    st.success("✅ Tạo audio thành công!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Không thể ghép audio")
                    
            except Exception as e:
                st.error(f"Lỗi: {str(e)}")
    
    def render_audio_player(self):
        """Hiển thị audio player và download options"""
        if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
            # Audio player
            st.audio(st.session_state.current_audio, format="audio/mp3")
            
            # Thông tin
            with st.expander("📊 Thông tin", expanded=True):
                st.write(f"**Giọng:** {self.get_voice_display_name(st.session_state.current_settings['voice'])}")
                st.write(f"**Ngôn ngữ:** {st.session_state.current_settings['language']}")
                st.write(f"**Tốc độ:** {st.session_state.current_settings['rate']}%")
                st.write(f"**Cao độ:** {st.session_state.current_settings['pitch']}Hz")
                st.write(f"**Âm lượng:** {st.session_state.current_settings['volume']}%")
                st.write(f"**Khoảng nghỉ:** {st.session_state.current_settings['pause']}ms")
            
            # Download button
            with open(st.session_state.current_audio, "rb") as f:
                audio_bytes = f.read()
            
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="📥 Tải audio",
                    data=audio_bytes,
                    file_name=f"tts_story_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                    mime="audio/mp3",
                    use_container_width=True
                )
            
            with col_dl2:
                if st.button("🗑️ Xóa", use_container_width=True):
                    self.cleanup_temp_files()
                    st.session_state.current_audio = None
                    st.rerun()
            
            # Quick actions
            st.markdown("---")
            st.subheader("⚡ Hành động nhanh")
            
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if st.button("🔄 Tạo lại", use_container_width=True):
                    if st.session_state.current_text:
                        self.generate_story(st.session_state.current_text)
            
            with col_act2:
                if st.button("📋 Sao chép văn bản", use_container_width=True):
                    st.code(st.session_state.current_text)
                    st.success("Đã sao chép!")
        
        else:
            st.info("👈 **Hướng dẫn sử dụng:**")
            st.markdown("""
            1. **Nhập văn bản** vào ô bên trái
            2. **Chọn giọng nói** và cài đặt từ sidebar
            3. **Nhấn nút "Tạo truyện audio"**
            4. **Nghe thử** và **tải về** file audio
            
            **Tính năng:**
            - Hỗ trợ đa ngôn ngữ
            - Điều chỉnh tốc độ, cao độ, âm lượng
            - Tự động thêm khoảng nghỉ giữa các đoạn
            - Lưu lịch sử làm việc
            """)
    
    def save_settings_to_file(self):
        """Lưu cài đặt vào file"""
        try:
            settings = {
                "single_char": st.session_state.current_settings.copy(),
                "timestamp": datetime.now().isoformat()
            }
            
            with open("tts_settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            st.success("Đã lưu cài đặt!")
            
        except Exception as e:
            st.error(f"Lỗi lưu cài đặt: {str(e)}")
    
    def cleanup_temp_files(self):
        """Dọn dẹp file tạm"""
        try:
            if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
                os.unlink(st.session_state.current_audio)
        except:
            pass
        
        # Cleanup other temp files if any
        for audio_file in st.session_state.audio_files:
            try:
                if os.path.exists(audio_file):
                    os.unlink(audio_file)
            except:
                pass
        
        st.session_state.audio_files = []
    
    def run(self):
        """Chạy ứng dụng chính"""
        # CSS tùy chỉnh
        st.markdown("""
        <style>
        .stApp {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .stButton > button {
            border-radius: 8px;
            font-weight: bold;
        }
        
        .stTextArea textarea {
            font-size: 16px;
            line-height: 1.6;
        }
        
        h1, h2, h3 {
            color: #1f77b4;
        }
        
        .audio-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Header
        st.title("📖 TTS Story Generator")
        st.markdown("Chuyển văn bản thành giọng nói với nhiều chế độ")
        
        # Render sidebar
        self.render_sidebar()
        
        # Render main content based on mode
        if st.session_state.mode == "single":
            self.render_single_character_mode()
        elif st.session_state.mode == "multi":
            self.render_multi_character_mode()
        elif st.session_state.mode == "dialogue":
            self.render_dialogue_mode()
        
        # Footer
        st.markdown("---")
        st.caption("© 2024 TTS Story Generator | Edge TTS 7.2.0 | Streamlit Cloud")

# ==================== MAIN ====================
def main():
    """Hàm chính"""
    try:
        app = TTSApp()
        app.run()
    except Exception as e:
        st.error(f"Đã xảy ra lỗi: {str(e)}")
        st.info("Vui lòng làm mới trang hoặc thử lại sau.")

if __name__ == "__main__":
    main()
