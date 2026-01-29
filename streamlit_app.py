"""
TTS Voice Generator - Ứng dụng chuyển văn bản thành giọng nói
Phiên bản tối giản, chắc chắn chạy được trên Streamlit Cloud
"""

import streamlit as st
import edge_tts
import asyncio
import tempfile
import os
import re
import base64
from datetime import datetime
from typing import List, Optional
import json

# ==================== CẤU HÌNH ====================
st.set_page_config(
    page_title="TTS Voice Generator",
    page_icon="🔊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== DANH SÁCH GIỌNG ====================
VOICES = {
    "Tiếng Việt": [
        {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "gender": "Nữ"},
        {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "gender": "Nam"}
    ],
    "Tiếng Anh (Mỹ)": [
        {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Nữ"},
        {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Nam"},
        {"id": "en-US-AvaNeural", "name": "Ava", "gender": "Nữ"},
        {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "Nam"}
    ],
    "Tiếng Anh (Anh)": [
        {"id": "en-GB-SoniaNeural", "name": "Sonia", "gender": "Nữ"},
        {"id": "en-GB-RyanNeural", "name": "Ryan", "gender": "Nam"}
    ],
    "Tiếng Trung": [
        {"id": "zh-CN-XiaoxiaoNeural", "name": "Xiao Xiao", "gender": "Nữ"},
        {"id": "zh-CN-YunxiNeural", "name": "Yunxi", "gender": "Nam"}
    ]
}

# ==================== TIỆN ÍCH ====================
def init_session_state():
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

def cleanup_temp_file(file_path: str):
    """Xóa file tạm"""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except:
        pass

def get_voice_display_name(voice_id: str) -> str:
    """Lấy tên hiển thị của giọng"""
    for lang, voices in VOICES.items():
        for voice in voices:
            if voice["id"] == voice_id:
                return f"{lang} - {voice['name']} ({voice['gender']})"
    return voice_id

# ==================== TTS ENGINE ====================
class SimpleTTSEngine:
    """Engine TTS đơn giản"""
    
    @staticmethod
    async def generate_speech(
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
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_file.close()
            
            # Generate speech với edge-tts 7.2.0
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                rate=rate_str,
                pitch=pitch_str
            )
            
            await communicate.save(temp_file.name)
            
            return temp_file.name
            
        except Exception as e:
            st.error(f"Lỗi tạo giọng nói: {str(e)}")
            return None

# ==================== STREAMLIT APP ====================
def main():
    """Ứng dụng chính"""
    
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
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    .stTextArea textarea {
        border-radius: 10px;
        font-size: 16px;
        line-height: 1.6;
    }
    
    h1, h2, h3 {
        color: #1f77b4;
    }
    
    .audio-player {
        border-radius: 15px;
        padding: 20px;
        background: #f8f9fa;
        border: 1px solid #dee2e6;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Khởi tạo session state
    init_session_state()
    
    # Header
    st.title("🔊 TTS Voice Generator")
    st.markdown("Chuyển văn bản thành giọng nói chất lượng cao với nhiều giọng đọc")
    
    # Sidebar
    with st.sidebar:
        st.title("🎙️ Cài đặt")
        st.markdown("---")
        
        # Chọn ngôn ngữ
        languages = list(VOICES.keys())
        selected_lang = st.selectbox(
            "Ngôn ngữ",
            languages,
            index=0
        )
        
        # Chọn giọng
        voices = VOICES[selected_lang]
        voice_options = {f"{v['name']} ({v['gender']})": v['id'] for v in voices}
        
        selected_voice_name = st.selectbox(
            "Giọng nói",
            list(voice_options.keys())
        )
        
        selected_voice_id = voice_options[selected_voice_name]
        
        st.markdown("---")
        
        # Cài đặt âm thanh
        st.subheader("🎛️ Điều chỉnh âm thanh")
        
        rate = st.slider("Tốc độ", -50, 50, 0, 
                        help="Điều chỉnh tốc độ nói (-50% chậm hơn, +50% nhanh hơn)")
        
        pitch = st.slider("Cao độ", -50, 50, 0,
                         help="Điều chỉnh độ cao giọng nói")
        
        volume = st.slider("Âm lượng", 0, 200, 100,
                          help="Điều chỉnh âm lượng (100% = bình thường)")
        
        # Lưu cài đặt
        st.session_state.current_settings = {
            "voice": selected_voice_id,
            "rate": rate,
            "pitch": pitch,
            "volume": volume
        }
        
        st.markdown("---")
        
        # History
        if st.session_state.history:
            with st.expander("📜 Lịch sử gần đây", expanded=False):
                for i, item in enumerate(st.session_state.history[-3:][::-1]):
                    btn_text = f"#{len(st.session_state.history)-i}: {item['text'][:30]}..."
                    if st.button(btn_text, key=f"hist_{i}", use_container_width=True):
                        st.session_state.current_text = item['text']
                        st.session_state.current_settings = item['settings']
                        st.rerun()
        
        st.markdown("---")
        st.caption("Made with ❤️ by TTS Generator")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Input text area
        text = st.text_area(
            "📝 Nhập văn bản",
            value=st.session_state.current_text,
            height=300,
            placeholder="Nhập hoặc dán văn bản của bạn ở đây...",
            help="Bạn có thể nhập văn bản dài, ứng dụng sẽ tự động xử lý",
            key="input_text"
        )
        
        # Options
        with st.expander("⚡ Tùy chọn", expanded=True):
            col_opt1, col_opt2 = st.columns(2)
            
            with col_opt1:
                split_sentences = st.checkbox("Tách thành câu", value=True)
                add_pauses = st.checkbox("Thêm khoảng nghỉ", value=True)
            
            with col_opt2:
                output_format = st.selectbox("Định dạng", ["MP3", "WAV"], index=0)
        
        # Generate button
        if st.button("🎵 Tạo giọng nói", type="primary", use_container_width=True):
            if not text.strip():
                st.warning("⚠️ Vui lòng nhập văn bản")
                return
            
            # Lưu vào history
            history_item = {
                "text": text,
                "settings": st.session_state.current_settings.copy(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.history.append(history_item)
            
            # Generate audio
            with st.spinner("Đang xử lý văn bản và tạo giọng nói..."):
                try:
                    # Create speech
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    audio_file = loop.run_until_complete(
                        SimpleTTSEngine.generate_speech(
                            text=text,
                            voice_id=st.session_state.current_settings["voice"],
                            rate=st.session_state.current_settings["rate"],
                            pitch=st.session_state.current_settings["pitch"],
                            volume=st.session_state.current_settings["volume"]
                        )
                    )
                    
                    if audio_file:
                        st.session_state.current_audio = audio_file
                        st.success("✅ Tạo giọng nói thành công!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Không thể tạo giọng nói. Vui lòng thử lại.")
                        
                except Exception as e:
                    st.error(f"❌ Lỗi: {str(e)}")
    
    with col2:
        # Display audio player and download
        if st.session_state.current_audio and os.path.exists(st.session_state.current_audio):
            st.audio(st.session_state.current_audio, format="audio/mp3")
            
            # Thông tin
            with st.expander("📊 Thông tin chi tiết", expanded=True):
                st.write(f"**Giọng:** {get_voice_display_name(st.session_state.current_settings['voice'])}")
                st.write(f"**Tốc độ:** {st.session_state.current_settings['rate']}%")
                st.write(f"**Cao độ:** {st.session_state.current_settings['pitch']}Hz")
                st.write(f"**Âm lượng:** {st.session_state.current_settings['volume']}%")
                st.write(f"**Độ dài văn bản:** {len(st.session_state.current_text)} ký tự")
                st.write(f"**Thời gian tạo:** {datetime.now().strftime('%H:%M:%S')}")
            
            # Download button
            with open(st.session_state.current_audio, "rb") as f:
                audio_bytes = f.read()
            
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="📥 Tải audio",
                    data=audio_bytes,
                    file_name=f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                    mime="audio/mp3",
                    use_container_width=True
                )
            
            with col_dl2:
                if st.button("🗑️ Xóa", use_container_width=True):
                    cleanup_temp_file(st.session_state.current_audio)
                    st.session_state.current_audio = None
                    st.rerun()
            
            # Quick actions
            st.markdown("---")
            st.subheader("⚡ Hành động nhanh")
            
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if st.button("🔄 Tạo lại", use_container_width=True):
                    st.rerun()
            
            with col_act2:
                if st.button("📋 Sao chép văn bản", use_container_width=True):
                    st.code(st.session_state.current_text)
                    st.success("Đã sao chép vào clipboard!")
        
        else:
            st.info("👈 **Hướng dẫn sử dụng:**")
            st.markdown("""
            1. **Nhập văn bản** vào ô bên trái
            2. **Chọn giọng nói** và cài đặt từ sidebar
            3. **Nhấn nút "Tạo giọng nói"**
            4. **Nghe thử** và **tải về** file audio
            
            **Mẹo:**
            - Sử dụng dấu câu để ngắt nghỉ tự nhiên
            - Điều chỉnh tốc độ phù hợp với nội dung
            - Thử các giọng khác nhau để tìm giọng ưa thích
            """)
    
    # Footer
    st.markdown("---")
    st.caption("© 2024 TTS Voice Generator | Edge TTS 7.2.0 | Streamlit Cloud")

# ==================== RUN ====================
if __name__ == "__main__":
    main()
