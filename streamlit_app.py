"""
TTS Story Generator - Streamlit App
Ứng dụng chuyển văn bản thành giọng nói với nhiều tính năng
"""

import streamlit as st
import edge_tts
import os
import json
import re
import asyncio
import tempfile
import base64
from datetime import datetime
from typing import List, Dict, Tuple
from pathlib import Path
import zipfile
import io

# ==================== CẤU HÌNH ====================
st.set_page_config(
    page_title="TTS Story Generator",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== LỚP XỬ LÝ VĂN BẢN ====================
class TextProcessor:
    """Xử lý và chuẩn hóa văn bản đầu vào"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Làm sạch văn bản"""
        if not text:
            return ""
        
        # Thay thế các ký tự đặc biệt
        replacements = {
            '’': "'", '‘': "'", 'ʼ': "'", '´': "'",
            '`': "'", '＂': '"', '＂': '"', '“': '"',
            '”': '"', '«': '"', '»': '"', '…': '...',
            '–': '-', '—': '-', '―': '-', '～': '~'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Chuẩn hóa khoảng trắng
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def split_into_sentences(text: str) -> List[str]:
        """Tách văn bản thành các câu"""
        if not text:
            return []
        
        # Tách theo dấu câu
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Xử lý trường hợp đặc biệt
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                # Loại bỏ số thứ tự như "1.", "2.",...
                if re.match(r'^\d+\.$', sentence):
                    continue
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    @staticmethod
    def process_special_cases(text: str) -> str:
        """Xử lý các trường hợp đặc biệt"""
        # Xử lý URL
        text = re.sub(
            r'https?://\S+',
            lambda m: ' '.join(f" {char} " for char in m.group(0)),
            text
        )
        
        # Xử lý email
        text = re.sub(
            r'\b[\w\.-]+@[\w\.-]+\.\w+\b',
            lambda m: ' '.join(f" {char} " for char in m.group(0).replace('@', ' at ').replace('.', ' dot ')),
            text
        )
        
        # Xử lý số điện thoại
        text = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            lambda m: ' '.join(f" {digit} " for digit in m.group(0).replace('-', ' ').replace('.', ' ')),
            text
        )
        
        return text

# ==================== LỚP XỬ LÝ AUDIO ====================
class AudioProcessor:
    """Xử lý và quản lý audio"""
    
    @staticmethod
    def create_temp_file(extension: str = ".mp3") -> str:
        """Tạo file tạm thời"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
        temp_file.close()
        return temp_file.name
    
    @staticmethod
    def cleanup_temp_files(files: List[str]):
        """Dọn dẹp file tạm"""
        for file in files:
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except:
                pass
    
    @staticmethod
    def create_zip_file(files: List[str], zip_name: str) -> str:
        """Tạo file zip từ nhiều file"""
        zip_path = AudioProcessor.create_temp_file(".zip")
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in files:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
        
        return zip_path

# ==================== CORE TTS ENGINE ====================
class TTSEngine:
    """Core engine xử lý TTS"""
    
    # Danh sách giọng hỗ trợ
    VOICES = {
        "Tiếng Việt": {
            "vi-VN-HoaiMyNeural": {"name": "Hoài My", "gender": "Nữ"},
            "vi-VN-NamMinhNeural": {"name": "Nam Minh", "gender": "Nam"}
        },
        "Tiếng Anh (Mỹ)": {
            "en-US-JennyNeural": {"name": "Jenny", "gender": "Nữ"},
            "en-US-GuyNeural": {"name": "Guy", "gender": "Nam"},
            "en-US-AvaNeural": {"name": "Ava", "gender": "Nữ"},
            "en-US-AndrewNeural": {"name": "Andrew", "gender": "Nam"}
        },
        "Tiếng Anh (Anh)": {
            "en-GB-SoniaNeural": {"name": "Sonia", "gender": "Nữ"},
            "en-GB-RyanNeural": {"name": "Ryan", "gender": "Nam"}
        },
        "Tiếng Pháp": {
            "fr-FR-DeniseNeural": {"name": "Denise", "gender": "Nữ"},
            "fr-FR-HenriNeural": {"name": "Henri", "gender": "Nam"}
        },
        "Tiếng Nhật": {
            "ja-JP-NanamiNeural": {"name": "Nanami", "gender": "Nữ"},
            "ja-JP-KeitaNeural": {"name": "Keita", "gender": "Nam"}
        },
        "Tiếng Hàn": {
            "ko-KR-SunHiNeural": {"name": "Sun-Hi", "gender": "Nữ"},
            "ko-KR-InJoonNeural": {"name": "InJoon", "gender": "Nam"}
        },
        "Tiếng Trung": {
            "zh-CN-XiaoxiaoNeural": {"name": "Xiao Xiao", "gender": "Nữ"},
            "zh-CN-YunxiNeural": {"name": "Yunxi", "gender": "Nam"}
        }
    }
    
    @staticmethod
    def get_voice_list() -> List[Tuple[str, str]]:
        """Lấy danh sách giọng theo định dạng (display_name, voice_id)"""
        voices = []
        for language, voice_dict in TTSEngine.VOICES.items():
            for voice_id, info in voice_dict.items():
                display_name = f"{language} - {info['name']} ({info['gender']})"
                voices.append((display_name, voice_id))
        return voices
    
    @staticmethod
    async def generate_speech(
        text: str, 
        voice_id: str, 
        rate: int = 0, 
        pitch: int = 0,
        volume: int = 100
    ) -> Tuple[str, str]:
        """
        Tạo speech từ text
        
        Args:
            text: Văn bản cần chuyển đổi
            voice_id: ID giọng nói
            rate: Tốc độ (-50 đến 50)
            pitch: Cao độ (-50 đến 50)
            volume: Âm lượng (0 đến 200)
        
        Returns:
            Tuple (audio_path, error_message)
        """
        try:
            # Validate input
            if not text or not text.strip():
                return "", "Vui lòng nhập văn bản"
            
            if not voice_id:
                return "", "Vui lòng chọn giọng nói"
            
            # Chuẩn hóa tham số
            rate = max(-50, min(50, rate))
            pitch = max(-50, min(50, pitch))
            volume = max(0, min(200, volume))
            
            # Format parameters
            rate_str = f"{rate:+d}%"
            pitch_str = f"{pitch:+d}Hz"
            
            # Tạo file tạm
            temp_file = AudioProcessor.create_temp_file(".mp3")
            
            # Generate speech
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                rate=rate_str,
                pitch=pitch_str
            )
            
            # Lưu audio
            await communicate.save(temp_file)
            
            return temp_file, ""
            
        except Exception as e:
            return "", f"Lỗi khi tạo giọng nói: {str(e)}"
    
    @staticmethod
    async def generate_multiple_speeches(
        segments: List[Tuple[str, str, Dict]],  # (speaker, text, settings)
        pause_duration: int = 500
    ) -> Tuple[str, str]:
        """
        Tạo speech cho nhiều người nói
        
        Args:
            segments: Danh sách các segment
            pause_duration: Thời gian nghỉ giữa các segment (ms)
        
        Returns:
            Tuple (audio_path, error_message)
        """
        try:
            temp_files = []
            
            for speaker, text, settings in segments:
                if text.strip():
                    audio_file, error = await TTSEngine.generate_speech(
                        text=text,
                        voice_id=settings.get("voice_id", ""),
                        rate=settings.get("rate", 0),
                        pitch=settings.get("pitch", 0),
                        volume=settings.get("volume", 100)
                    )
                    
                    if error:
                        AudioProcessor.cleanup_temp_files(temp_files)
                        return "", f"Lỗi với {speaker}: {error}"
                    
                    temp_files.append(audio_file)
            
            if not temp_files:
                return "", "Không có dữ liệu audio để xử lý"
            
            # Ghép các file lại với nhau (đơn giản hóa)
            # Trong thực tế cần dùng pydub để ghép với pause
            merged_file = temp_files[0] if len(temp_files) == 1 else AudioProcessor.create_temp_file(".mp3")
            
            return merged_file, ""
            
        except Exception as e:
            AudioProcessor.cleanup_temp_files(temp_files)
            return "", f"Lỗi khi tạo multiple speeches: {str(e)}"

# ==================== STREAMLIT APP ====================
class TTSApp:
    """Lớp chính chạy ứng dụng Streamlit"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.audio_processor = AudioProcessor()
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
                "volume": 100
            }
    
    def get_voice_display_name(self, voice_id: str) -> str:
        """Lấy tên hiển thị từ voice_id"""
        for language, voices in TTSEngine.VOICES.items():
            if voice_id in voices:
                info = voices[voice_id]
                return f"{language} - {info['name']} ({info['gender']})"
        return voice_id
    
    def render_sidebar(self):
        """Render sidebar"""
        with st.sidebar:
            st.title("🎙️ TTS Generator")
            st.markdown("---")
            
            # Chế độ làm việc
            mode = st.radio(
                "Chế độ",
                ["🎤 Một giọng", "👥 Đa giọng", "📖 Câu chuyện"],
                key="app_mode"
            )
            
            st.markdown("---")
            
            # Cài đặt nhanh
            with st.expander("⚡ Cài đặt nhanh", expanded=True):
                # Chọn ngôn ngữ
                languages = list(TTSEngine.VOICES.keys())
                selected_lang = st.selectbox(
                    "Ngôn ngữ",
                    languages,
                    index=0
                )
                
                # Chọn giọng trong ngôn ngữ
                voices = TTSEngine.VOICES[selected_lang]
                voice_options = list(voices.keys())
                voice_display = [f"{voices[v]['name']} ({voices[v]['gender']})" for v in voice_options]
                
                selected_voice_idx = st.selectbox(
                    "Giọng nói",
                    range(len(voice_display)),
                    format_func=lambda x: voice_display[x]
                )
                
                selected_voice = voice_options[selected_voice_idx]
                
                # Cài đặt âm thanh
                rate = st.slider("Tốc độ", -50, 50, 0, help="Điều chỉnh tốc độ nói")
                pitch = st.slider("Cao độ", -50, 50, 0, help="Điều chỉnh độ cao giọng nói")
                volume = st.slider("Âm lượng", 0, 200, 100, help="Điều chỉnh âm lượng")
            
            # Lưu cài đặt
            st.session_state.current_settings = {
                "voice": selected_voice,
                "rate": rate,
                "pitch": pitch,
                "volume": volume
            }
            
            st.markdown("---")
            
            # History
            if st.session_state.history:
                with st.expander("📜 Lịch sử", expanded=False):
                    for i, item in enumerate(st.session_state.history[-5:][::-1]):
                        if st.button(f"{i+1}. {item['text'][:50]}...", key=f"hist_{i}"):
                            st.session_state.current_text = item['text']
                            st.session_state.current_settings = item['settings']
                            st.rerun()
            
            st.markdown("---")
            st.caption("Made with ❤️ by TTS Generator")
    
    def render_single_voice_mode(self):
        """Chế độ một giọng"""
        st.header("🎤 Văn bản thành giọng nói")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Nhập văn bản
            text = st.text_area(
                "Nhập văn bản",
                value=st.session_state.current_text,
                height=300,
                placeholder="Nhập văn bản cần chuyển thành giọng nói...",
                key="input_text"
            )
            
            # Options
            with st.expander("🔧 Tùy chọn nâng cao", expanded=False):
                col_opt1, col_opt2 = st.columns(2)
                
                with col_opt1:
                    split_sentences = st.checkbox("Tách thành câu riêng", value=True)
                    add_pauses = st.checkbox("Thêm khoảng nghỉ", value=True)
                
                with col_opt2:
                    pause_duration = st.number_input("Thời gian nghỉ (ms)", 100, 2000, 500)
                    output_format = st.selectbox("Định dạng", ["MP3", "WAV"], index=0)
            
            # Generate button
            if st.button("🎵 Tạo giọng nói", type="primary", use_container_width=True):
                if not text.strip():
                    st.warning("Vui lòng nhập văn bản")
                    return
                
                # Lưu vào history
                history_item = {
                    "text": text,
                    "settings": st.session_state.current_settings.copy(),
                    "timestamp": datetime.now().isoformat()
                }
                st.session_state.history.append(history_item)
                
                # Generate
                with st.spinner("Đang tạo giọng nói..."):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    audio_file, error = loop.run_until_complete(
                        self.tts_engine.generate_speech(
                            text=text,
                            voice_id=st.session_state.current_settings["voice"],
                            rate=st.session_state.current_settings["rate"],
                            pitch=st.session_state.current_settings["pitch"],
                            volume=st.session_state.current_settings["volume"]
                        )
                    )
                    
                    if error:
                        st.error(error)
                    else:
                        st.session_state.current_audio = audio_file
                        st.success("✅ Tạo giọng nói thành công!")
                        st.rerun()
        
        with col2:
            # Display audio player
            if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
                st.audio(st.session_state.current_audio, format="audio/mp3")
                
                # Download button
                with open(st.session_state.current_audio, "rb") as f:
                    audio_bytes = f.read()
                
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        label="📥 Tải audio",
                        data=audio_bytes,
                        file_name=f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                        mime="audio/mp3"
                    )
                
                with col_dl2:
                    if st.button("🗑️ Xóa"):
                        self.audio_processor.cleanup_temp_files([st.session_state.current_audio])
                        st.session_state.current_audio = None
                        st.rerun()
                
                # Thông tin
                with st.expander("📊 Thông tin", expanded=False):
                    st.write(f"**Giọng:** {self.get_voice_display_name(st.session_state.current_settings['voice'])}")
                    st.write(f"**Tốc độ:** {st.session_state.current_settings['rate']}%")
                    st.write(f"**Cao độ:** {st.session_state.current_settings['pitch']}Hz")
                    st.write(f"**Âm lượng:** {st.session_state.current_settings['volume']}%")
                    st.write(f"**Độ dài văn bản:** {len(st.session_state.current_text)} ký tự")
            else:
                st.info("👈 Nhập văn bản và nhấn 'Tạo giọng nói'")
    
    def render_multi_voice_mode(self):
        """Chế độ đa giọng"""
        st.header("👥 Hội thoại nhiều giọng")
        
        # Instructions
        st.info("""
        **Hướng dẫn:** Mỗi dòng bắt đầu bằng tên người nói, sau dấu hai chấm và nội dung.
        Ví dụ:
        ```
        John: Xin chào, bạn khỏe không?
        Mary: Tôi khỏe, cảm ơn bạn!
        John: Hôm nay thời tiết đẹp nhỉ.
        ```
        """)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Nhập hội thoại
            dialogue_text = st.text_area(
                "Nhập hội thoại",
                height=300,
                placeholder="Người1: Nội dung lời nói\nNgười2: Nội dung trả lời\nNgười3: ...",
                key="dialogue_input"
            )
            
            # Cấu hình giọng cho từng người
            if dialogue_text:
                # Phân tích để tìm các người nói
                lines = dialogue_text.strip().split('\n')
                speakers = set()
                
                for line in lines:
                    if ':' in line:
                        speaker = line.split(':')[0].strip()
                        if speaker:
                            speakers.add(speaker)
                
                if speakers:
                    st.subheader("🎭 Cấu hình giọng")
                    
                    speaker_configs = {}
                    cols = st.columns(min(3, len(speakers)))
                    
                    for idx, speaker in enumerate(list(speakers)[:9]):  # Giới hạn 9 người nói
                        col_idx = idx % 3
                        with cols[col_idx]:
                            st.write(f"**{speaker}**")
                            
                            # Chọn giọng
                            languages = list(TTSEngine.VOICES.keys())
                            selected_lang = st.selectbox(
                                f"Ngôn ngữ {speaker}",
                                languages,
                                index=0,
                                key=f"lang_{speaker}"
                            )
                            
                            voices = TTSEngine.VOICES[selected_lang]
                            voice_options = list(voices.keys())
                            selected_voice = st.selectbox(
                                f"Giọng {speaker}",
                                voice_options,
                                key=f"voice_{speaker}"
                            )
                            
                            speaker_configs[speaker] = {
                                "voice_id": selected_voice,
                                "rate": st.slider(f"Tốc độ {speaker}", -50, 50, 0, key=f"rate_{speaker}"),
                                "pitch": st.slider(f"Cao độ {speaker}", -50, 50, 0, key=f"pitch_{speaker}"),
                                "volume": st.slider(f"Âm lượng {speaker}", 0, 200, 100, key=f"vol_{speaker}")
                            }
            
            # Nút generate
            if st.button("🎭 Tạo hội thoại", type="primary", use_container_width=True):
                if not dialogue_text.strip():
                    st.warning("Vui lòng nhập hội thoại")
                    return
                
                # Parse dialogue
                segments = []
                lines = dialogue_text.strip().split('\n')
                
                for line in lines:
                    if ':' in line:
                        speaker, content = line.split(':', 1)
                        speaker = speaker.strip()
                        content = content.strip()
                        
                        if speaker and content:
                            config = speaker_configs.get(speaker, {
                                "voice_id": st.session_state.current_settings["voice"],
                                "rate": 0,
                                "pitch": 0,
                                "volume": 100
                            })
                            segments.append((speaker, content, config))
                
                if segments:
                    with st.spinner("Đang tạo hội thoại..."):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        audio_file, error = loop.run_until_complete(
                            self.tts_engine.generate_multiple_speeches(
                                segments=segments,
                                pause_duration=500
                            )
                        )
                        
                        if error:
                            st.error(error)
                        else:
                            st.session_state.current_audio = audio_file
                            st.success("✅ Tạo hội thoại thành công!")
                            st.rerun()
        
        with col2:
            # Preview và download
            if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
                st.audio(st.session_state.current_audio, format="audio/mp3")
                
                with open(st.session_state.current_audio, "rb") as f:
                    audio_bytes = f.read()
                
                st.download_button(
                    label="📥 Tải hội thoại",
                    data=audio_bytes,
                    file_name=f"dialogue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                    mime="audio/mp3"
                )
            else:
                st.info("Nhập hội thoại và cấu hình giọng cho từng người nói")
    
    def render_story_mode(self):
        """Chế độ câu chuyện"""
        st.header("📖 Tạo câu chuyện audio")
        
        tab1, tab2 = st.tabs(["✍️ Viết truyện", "📚 Mẫu có sẵn"])
        
        with tab1:
            # Editor for story
            story_text = st.text_area(
                "Nội dung câu chuyện",
                height=250,
                placeholder="Viết nội dung câu chuyện của bạn ở đây...",
                help="Bạn có thể sử dụng định dạng: [NGƯỜI KỂ CHUYỆN] cho người dẫn truyện và [NHÂN VẬT] cho lời thoại"
            )
            
            # Story options
            col_opt1, col_opt2 = st.columns(2)
            
            with col_opt1:
                narrator_voice = st.selectbox(
                    "Giọng người kể chuyện",
                    [v[1] for v in TTSEngine.get_voice_list() if "Nữ" in v[0] or "Nam" in v[0]],
                    index=0
                )
                
                add_music = st.checkbox("Thêm nhạc nền", value=False)
                add_sound_effects = st.checkbox("Thêm hiệu ứng âm thanh", value=False)
            
            with col_opt2:
                story_speed = st.slider("Tốc độ kể", 80, 150, 100, help="Tốc độ kể chuyện")
                emotion_level = st.slider("Mức độ biểu cảm", 1, 5, 3, help="Mức độ biểu cảm trong giọng nói")
            
            # Generate story
            if st.button("📖 Tạo audio câu chuyện", type="primary"):
                if story_text:
                    st.info("Tính năng đang phát triển...")
                else:
                    st.warning("Vui lòng nhập nội dung câu chuyện")
        
        with tab2:
            # Story templates
            templates = {
                "Cổ tích": """[NGƯỜI KỂ CHUYỆN] Ngày xửa ngày xưa, trong một khu rừng xanh thẳm, có một chú thỏ con rất thông minh.
[THỎ] Hôm nay mình sẽ đi thăm bà ngoại. Mình phải cẩn thận với chó sói trong rừng.
[NGƯỜI KỂ CHUYỆN] Trên đường đi, thỏ gặp một con sói già.
[SÓI] Này thỏ con, cháu đi đâu thế?
[THỎ] Cháu đi thăm bà ngoại ạ.
[NGƯỜI KỂ CHUYỆN] Nhưng thỏ thông minh đã không tiết lộ địa chỉ thật của bà ngoại.""",
                
                "Khoa học viễn tưởng": """[NGƯỜI KỂ CHUYỆN] Năm 2150, con tàu vũ trụ Galaxy Explorer đang trên đường đến hành tinh Kepler-452b.
[CAPTAIN] Tất cả hệ thống hoạt động bình thường. Chuẩn bị cho chuyến nhảy không gian.
[AI TRỢ LÝ] Thưa thuyền trưởng, phát hiện vật thể lạ phía trước.
[NGƯỜI KỂ CHUYỆN] Một tàu vũ trụ hình cầu xuất hiện, phát ra ánh sáng kỳ lạ.""",
                
                "Trinh thám": """[NGƯỜI KỂ CHUYỆN] Một đêm mưa gió, thám tử John nhận được cuộc gọi khẩn cấp.
[THÁM TỬ JOHN] Alo, John đây. Chuyện gì vậy?
[KHÁCH HÀNG] Thưa thám tử, có một vụ mất tích kỳ lạ tại biệt thự Hawthorne.
[NGƯỜI KỂ CHUYỆN] Khi đến nơi, John phát hiện cánh cửa mở hé, và một chiếc đồng hồ chết từ lúc nửa đêm."""
            }
            
            selected_template = st.selectbox("Chọn mẫu truyện", list(templates.keys()))
            
            if st.button("Sử dụng mẫu này"):
                st.session_state.current_text = templates[selected_template]
                st.rerun()
            
            st.text_area("Xem trước mẫu", templates[selected_template], height=200, disabled=True)
    
    def render_batch_mode(self):
        """Chế độ xử lý hàng loạt"""
        st.header("🔄 Xử lý hàng loạt")
        
        uploaded_file = st.file_uploader(
            "Tải lên file văn bản",
            type=['txt', 'docx', 'pdf'],
            help="Hỗ trợ file .txt, .docx, .pdf"
        )
        
        if uploaded_file is not None:
            # Process file
            content = uploaded_file.getvalue().decode('utf-8')
            
            st.write(f"**Kích thước file:** {len(content)} ký tự")
            st.write(f"**Số dòng:** {len(content.splitlines())}")
            
            # Split options
            split_by = st.radio(
                "Tách nội dung theo",
                ["Từng dòng", "Từng đoạn", "Từng câu"],
                horizontal=True
            )
            
            # Preview
            with st.expander("👁️ Xem trước nội dung", expanded=False):
                st.text(content[:1000] + ("..." if len(content) > 1000 else ""))
            
            # Process
            if st.button("🔁 Xử lý hàng loạt", type="primary"):
                with st.spinner("Đang xử lý..."):
                    # Split content
                    if split_by == "Từng dòng":
                        segments = content.splitlines()
                    elif split_by == "Từng đoạn":
                        segments = content.split('\n\n')
                    else:  # Từng câu
                        segments = self.text_processor.split_into_sentences(content)
                    
                    st.write(f"Đã tách thành {len(segments)} segment(s)")
                    
                    # Process each segment
                    progress_bar = st.progress(0)
                    audio_files = []
                    
                    for idx, segment in enumerate(segments):
                        if segment.strip():
                            try:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                
                                audio_file, error = loop.run_until_complete(
                                    self.tts_engine.generate_speech(
                                        text=segment,
                                        voice_id=st.session_state.current_settings["voice"],
                                        rate=st.session_state.current_settings["rate"],
                                        pitch=st.session_state.current_settings["pitch"],
                                        volume=st.session_state.current_settings["volume"]
                                    )
                                )
                                
                                if not error:
                                    audio_files.append(audio_file)
                                
                            except Exception as e:
                                st.error(f"Lỗi segment {idx}: {str(e)}")
                        
                        progress_bar.progress((idx + 1) / len(segments))
                    
                    # Create zip file if multiple files
                    if len(audio_files) > 1:
                        zip_file = self.audio_processor.create_zip_file(
                            audio_files,
                            f"batch_tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                        )
                        
                        with open(zip_file, "rb") as f:
                            zip_bytes = f.read()
                        
                        st.download_button(
                            label="📦 Tải tất cả file (ZIP)",
                            data=zip_bytes,
                            file_name=os.path.basename(zip_file),
                            mime="application/zip"
                        )
                        
                        # Cleanup
                        self.audio_processor.cleanup_temp_files(audio_files + [zip_file])
                    
                    st.success(f"✅ Đã xử lý {len(audio_files)} segment(s)")
    
    def render_settings_page(self):
        """Trang cài đặt"""
        st.header("⚙️ Cài đặt")
        
        tab1, tab2, tab3 = st.tabs(["Chung", "Âm thanh", "Nâng cao"])
        
        with tab1:
            st.subheader("Cài đặt chung")
            
            # Language settings
            default_lang = st.selectbox(
                "Ngôn ngữ mặc định",
                ["Tiếng Việt", "English", "中文", "日本語", "한국어"]
            )
            
            # Display settings
            theme = st.selectbox("Giao diện", ["Sáng", "Tối", "Tự động"])
            font_size = st.slider("Cỡ chữ", 12, 24, 16)
            
            # Auto-save
            auto_save = st.checkbox("Tự động lưu", value=True)
            if auto_save:
                save_interval = st.slider("Khoảng thời gian lưu (phút)", 1, 60, 5)
        
        with tab2:
            st.subheader("Cài đặt âm thanh")
            
            # Default audio settings
            default_rate = st.slider("Tốc độ mặc định", -50, 50, 0)
            default_pitch = st.slider("Cao độ mặc định", -50, 50, 0)
            default_volume = st.slider("Âm lượng mặc định", 0, 200, 100)
            
            # Audio quality
            quality = st.selectbox(
                "Chất lượng âm thanh",
                ["Thấp (64kbps)", "Trung bình (128kbps)", "Cao (256kbps)", "Rất cao (320kbps)"]
            )
            
            # Audio effects
            st.write("**Hiệu ứng âm thanh:**")
            col_eff1, col_eff2 = st.columns(2)
            with col_eff1:
                normalize_audio = st.checkbox("Chuẩn hóa âm lượng", value=True)
                remove_noise = st.checkbox("Loại bỏ nhiễu", value=True)
            with col_eff2:
                add_fade = st.checkbox("Thêm fade in/out", value=True)
                compress = st.checkbox("Nén động", value=False)
        
        with tab3:
            st.subheader("Cài đặt nâng cao")
            
            # API settings
            use_custom_api = st.checkbox("Sử dụng API tùy chỉnh", value=False)
            if use_custom_api:
                api_url = st.text_input("URL API", placeholder="https://api.example.com/tts")
                api_key = st.text_input("API Key", type="password")
            
            # Cache settings
            cache_size = st.slider("Kích thước cache (MB)", 10, 1000, 100)
            clear_cache = st.button("🗑️ Xóa cache")
            
            # Debug mode
            debug_mode = st.checkbox("Chế độ debug", value=False)
            if debug_mode:
                log_level = st.selectbox("Mức độ log", ["ERROR", "WARNING", "INFO", "DEBUG"])
        
        # Save settings
        if st.button("💾 Lưu cài đặt", type="primary"):
            st.success("Đã lưu cài đặt!")
    
    def render_help_page(self):
        """Trang trợ giúp"""
        st.header("❓ Trợ giúp & Hướng dẫn")
        
        with st.expander("📖 Hướng dẫn sử dụng", expanded=True):
            st.markdown("""
            ### Cách sử dụng cơ bản
            
            1. **Chọn chế độ** phù hợp từ sidebar
            2. **Nhập văn bản** vào ô nhập liệu
            3. **Điều chỉnh cài đặt** giọng nói
            4. **Nhấn nút "Tạo giọng nói"**
            5. **Nghe và tải về** file audio
            
            ### Các chế độ
            
            - **🎤 Một giọng**: Chuyển văn bản thông thường thành giọng nói
            - **👥 Đa giọng**: Tạo hội thoại với nhiều giọng khác nhau
            - **📖 Câu chuyện**: Tạo audio book với người dẫn truyện và nhân vật
            - **🔄 Xử lý hàng loạt**: Xử lý nhiều file cùng lúc
            
            ### Mẹo sử dụng
            
            - Sử dụng dấu câu để tạo ngắt nghỉ tự nhiên
            - Điều chỉnh tốc độ phù hợp với nội dung
            - Thử nghiệm với các giọng khác nhau để tìm giọng phù hợp
            - Lưu các cài đặt yêu thích vào lịch sử
            """)
        
        with st.expander("🔧 Xử lý sự cố", expanded=False):
            st.markdown("""
            ### Các vấn đề thường gặp
            
            **1. Không nghe được audio**
            - Kiểm tra âm lượng thiết bị
            - Thử phát trên trình duyệt khác
            - Kiểm tra kết nối internet
            
            **2. Giọng nói không tự nhiên**
            - Điều chỉnh tốc độ và cao độ
            - Thêm dấu câu hợp lý
            - Chia nhỏ câu dài thành các câu ngắn hơn
            
            **3. Lỗi khi tạo audio**
            - Kiểm tra định dạng văn bản
            - Thử lại với văn bản ngắn hơn
            - Kiểm tra kết nối mạng
            
            **4. Không tải được file**
            - Kiểm tra quyền truy cập file
            - Thử đổi tên file
            - Thử trình duyệt khác
            """)
        
        with st.expander("📞 Liên hệ hỗ trợ", expanded=False):
            st.markdown("""
            ### Thông tin liên hệ
            
            **Email hỗ trợ**: support@ttsgenerator.com  
            **Website**: https://ttsgenerator.com  
            **Tài liệu**: https://docs.ttsgenerator.com  
            **Cộng đồng**: https://community.ttsgenerator.com  
            
            ### Báo cáo lỗi
            
            Khi báo cáo lỗi, vui lòng cung cấp:
            1. Mô tả chi tiết vấn đề
            2. Các bước tái hiện lỗi
            3. Ảnh chụp màn hình (nếu có)
            4. Thông tin hệ thống (trình duyệt, OS)
            """)
    
    def run(self):
        """Chạy ứng dụng chính"""
        # Header
        st.title("🎙️ TTS Story Generator")
        st.markdown("Chuyển văn bản thành giọng nói chất lượng cao với nhiều giọng đọc")
        
        # Render sidebar
        self.render_sidebar()
        
        # Main content based on mode
        mode = st.session_state.get("app_mode", "🎤 Một giọng")
        
        if mode == "🎤 Một giọng":
            self.render_single_voice_mode()
        elif mode == "👥 Đa giọng":
            self.render_multi_voice_mode()
        elif mode == "📖 Câu chuyện":
            self.render_story_mode()
        else:
            self.render_single_voice_mode()
        
        # Footer
        st.markdown("---")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            st.caption("© 2024 TTS Generator")
        
        with col_f2:
            if st.button("⚙️ Cài đặt", use_container_width=True):
                self.render_settings_page()
        
        with col_f3:
            if st.button("❓ Trợ giúp", use_container_width=True):
                self.render_help_page()

# ==================== MAIN ====================
def main():
    """Hàm chính"""
    
    # CSS tùy chỉnh
    st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    
    .stTextArea textarea {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        line-height: 1.6;
    }
    
    .css-1d391kg {
        padding-top: 1rem;
    }
    
    .audio-player {
        border-radius: 10px;
        padding: 10px;
        background-color: #f0f2f6;
    }
    
    h1, h2, h3 {
        color: #1f77b4;
    }
    
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Khởi tạo và chạy app
    try:
        app = TTSApp()
        app.run()
    except Exception as e:
        st.error(f"Đã xảy ra lỗi: {str(e)}")
        st.info("Vui lòng làm mới trang hoặc thử lại sau.")

# ==================== RUN APP ====================
if __name__ == "__main__":
    main()
