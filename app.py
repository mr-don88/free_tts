import gradio as gr
import edge_tts
import os
import random
import json
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
import asyncio
from datetime import datetime
import zipfile
import natsort
import time
import webvtt
import re
from typing import Dict, List, Tuple, Optional
from datetime import timedelta

import numpy as np
import wave
import time





# Khởi tạo môi trường - Ưu tiên GPU

class TTSModel:
    def __init__(self):
        self.models = {}
        self.tokenizer = Tokenizer()
        self.voice_cache = {}
        self.voice_files = self._discover_voices()
        
        try:
            if self.use_cuda:
                self.models['cuda'] = torch.compile(KModel().to('cuda').eval(), mode='max-autotune')
                with torch.no_grad():
                    _ = self.models['cuda'](torch.randn(1, 64).cuda(), torch.randn(1, 80, 100).cuda(), 1.0)
            
            self.models['cpu'] = KModel().to('cpu').eval()
        except Exception as e:
            print(f"Error loading model: {e}")
            self.models = {'cpu': KModel().to('cpu').eval()}
        
        self.pipelines = {
            'a': KPipeline(lang_code='a', model=False),
            'b': KPipeline(lang_code='b', model=False)
        }
    
    def _discover_voices(self):
        """Discover available voice files in the voices folder"""
        voice_files = {}
        voices_dir = "voices"
        
        if not os.path.exists(voices_dir):
            os.makedirs(voices_dir)
            print(f"Created voices directory at {os.path.abspath(voices_dir)}")
            return voice_files
            
        for file in os.listdir(voices_dir):
            if file.endswith(".pt"):
                voice_name = os.path.splitext(file)[0]
                voice_files[voice_name] = os.path.join(voices_dir, file)
                print(f"Found voice: {voice_name}")
                
        return voice_files

    def get_voice_list(self):
        """Get list of available voices for the UI"""
        voices = list(self.voice_files.keys())
        if not voices:
            print("Warning: No voice files found in voices folder")
        return voices

class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
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
        """Pipeline xử lý đặc biệt với thứ tự tối ưu"""
        text = TextProcessor._process_emails(text)
        text = TextProcessor._process_websites(text)
        text = TextProcessor._process_phone_numbers(text)
        text = TextProcessor._process_temperatures(text)
        text = TextProcessor._process_measurements(text)
        text = TextProcessor._process_currency(text)
        text = TextProcessor._process_percentages(text)
        text = TextProcessor._process_math_operations(text)
        text = TextProcessor._process_times(text)
        text = TextProcessor._process_years(text)
        text = TextProcessor._process_special_symbols(text)
        
        return text
    
    @staticmethod
    def _process_emails(text: str) -> str:
        """Process emails with correct English pronunciation for all special characters"""
        def convert_email(match):
            full_email = match.group(0)
            # Replace each special character with its English pronunciation
            processed = (full_email
                        .replace('@', ' at ')
                        .replace('.', ' dot ')
                        .replace('-', ' dash ')
                        .replace('_', ' underscore ')
                        .replace('+', ' plus ')
                        .replace('/', ' slash ')
                        .replace('=', ' equals '))
            return processed

        # Regex to match all email formats
        email_pattern = r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b'
        return re.sub(email_pattern, convert_email, text)

    @staticmethod
    def _process_websites(text: str) -> str:
        """Process websites with correct English pronunciation for special characters"""
        def convert_website(match):
            url = match.group(1)
            # Replace each special character with its English pronunciation
            return (url.replace('.', ' dot ')
                     .replace('-', ' dash ')
                     .replace('_', ' underscore ')
                     .replace('/', ' slash ')
                     .replace('?', ' question mark ')
                     .replace('=', ' equals ')
                     .replace('&', ' ampersand '))

        # Only process websites that don't contain @ (to avoid conflict with emails)
        website_pattern = r'\b(?![\w.-]*@)((?:https?://)?(?:www\.)?[\w.-]+\.[a-z]{2,}(?:[/?=&#][\w.-]*)*)\b'
        return re.sub(website_pattern, convert_website, text, flags=re.IGNORECASE)

    @staticmethod
    def _process_temperatures(text: str) -> str:
        """Process temperatures and cardinal directions with degree symbols"""
        def temp_to_words(temp, unit):
            temp_text = TextProcessor._number_to_words(temp)
            unit = unit.upper() if unit else ''
            
            unit_map = {
                'C': 'degrees Celsius',
                'F': 'degrees Fahrenheit',
                'N': 'degrees north',
                'S': 'degrees south',
                'E': 'degrees east', 
                'W': 'degrees west',
                '': 'degrees'  # Default case for just number with degree symbol
            }
            unit_text = unit_map.get(unit, f'degrees {unit}')
            
            return f"{temp_text} {unit_text}"
        
        # Process formats like 75°F, 100°C, 15°N, 120°E
        text = re.sub(
            r'(-?\d+)°([NSEWCFnsewcf]?)',
            lambda m: temp_to_words(m.group(1), m.group(2)),
            text,
            flags=re.IGNORECASE
        )
        
        # Add degree symbol pronunciation when standalone
        text = re.sub(r'°', ' degrees ', text)
        
        return text

    @staticmethod
    def _process_measurements(text: str) -> str:
        """Xử lý đơn vị đo lường, đọc chuẩn số thập phân (1.65m → 'one point six five meters')"""
        units_map = {
            'km/h': 'kilometers per hour',
            'mph': 'miles per hour',
            'kg': 'kilograms',
            'g': 'grams',
            'cm': 'centimeters',
            'm': 'meter',  # Sửa thành singular để xử lý số nhiều sau
            'mm': 'millimeters',
            'L': 'liter',
            'l': 'liter',
            'ml': 'milliliter',
            'mL': 'milliliter',
            'h': 'hour',
            'min': 'minute',
            's': 'second'
        }
    
        plural_units = {'L', 'l', 'mL', 'ml'}  # Đơn vị không thêm 's' dù số nhiều
    
        def measurement_to_words(value, unit):
            try:
                unit_lower = unit.lower()
                unit_text = units_map.get(unit, units_map.get(unit_lower, unit))
    
                # Đọc số thập phân: one point six five
                if '.' in value:
                    integer, decimal = value.split('.')
                    value_text = (
                        f"{TextProcessor._number_to_words(integer)} "
                        f"point {' '.join(TextProcessor._digit_to_word(d) for d in decimal)}"
                    )
                else:
                    value_text = TextProcessor._number_to_words(value)
    
                # Xử lý số nhiều (thêm 's' nếu value != 1 và đơn vị không nằm trong plural_units)
                if float(value) != 1 and unit in units_map and unit not in plural_units:
                    unit_text += 's'
    
                return f"{value_text} {unit_text}"
            except:
                return f"{value}{unit}"  # Giữ nguyên nếu có lỗi
    
        # Regex bắt các số + đơn vị (kể cả viết liền như 1.65m)
        text = re.sub(
            r'(-?\d+\.?\d*)\s*({})s?\b'.format('|'.join(re.escape(key) for key in units_map.keys())),
            lambda m: measurement_to_words(m.group(1), m.group(2)),
            text,
            flags=re.IGNORECASE
        )
        return text
    
    @staticmethod
    def _process_currency(text: str) -> str:
        """Xử lý tiền tệ (hỗ trợ số nguyên, thập phân, và dấu chấm cuối câu)"""
        currency_map = {
            '$': 'dollars',
            '€': 'euros',
            '£': 'pounds',
            '¥': 'yen',
            '₩': 'won',
            '₽': 'rubles'
        }
    
        def currency_to_words(value, symbol):
            # Xử lý dấu chấm kết thúc câu (ví dụ: $20.)
            if value.endswith('.'):
                value = value[:-1]
                return f"{TextProcessor._number_to_words(value)} {currency_map.get(symbol, '')}."
    
            # Xử lý số thập phân (ví dụ: $20.5 → "twenty dollars and fifty cents")
            if '.' in value:
                integer_part, decimal_part = value.split('.')
                decimal_part = decimal_part.ljust(2, '0')  # Đảm bảo 2 chữ số
                return (
                    f"{TextProcessor._number_to_words(integer_part)} {currency_map.get(symbol, '')} "
                    f"and {TextProcessor._number_to_words(decimal_part)} cents"
                )
    
            # Số nguyên (ví dụ: $20 → "twenty dollars")
            return f"{TextProcessor._number_to_words(value)} {currency_map.get(symbol, '')}"
    
        # Regex bắt tiền tệ (số nguyên hoặc thập phân, không bắt dấu chấm cuối nếu không có số)
        text = re.sub(
            r'([$€£¥₩₽])(\d+(?:\.\d+)?)(?=\s|$|\.|,|;)',  # Chỉ khớp nếu sau số là ký tự kết thúc
            lambda m: currency_to_words(m.group(2), m.group(1)),
            text
        )
    
        return text

    @staticmethod
    def _process_percentages(text: str) -> str:
        """Xử lý phần trăm"""
        text = re.sub(
            r'(\d+\.?\d*)%',
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} percent",
            text
        )
        return text

    @staticmethod
    def _process_math_operations(text: str) -> str:
        """Xử lý các phép toán và khoảng số"""
        math_map = {
            '+': 'plus',
            '-': 'minus',  # Mặc định là "minus", sẽ xử lý riêng cho khoảng số
            '×': 'times',
            '*': 'times',
            '÷': 'divided by',
            '/': 'divided by',
            '=': 'equals',
            '>': 'is greater than',
            '<': 'is less than'
        }
    
        # Xử lý KHOẢNG SỐ (3-4 → "three to four") khi KHÔNG có dấu = hoặc phép toán sau -
        text = re.sub(
            r'(\d+)\s*-\s*(\d+)(?!\s*[=+×*÷/><])',  # Chỉ áp dụng khi KHÔNG có dấu =/+/*... sau -
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} to {TextProcessor._number_to_words(m.group(2))}",
            text
        )
    
        # Xử lý PHÉP TRỪ (chỉ khi có dấu = hoặc phép toán sau -)
        text = re.sub(
            r'(\d+)\s*-\s*(\d+)(?=\s*[=+×*÷/><])',  # Chỉ áp dụng khi CÓ dấu =/+/*... sau -
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} minus {TextProcessor._number_to_words(m.group(2))}",
            text
        )
    
        # Xử lý các PHÉP TOÁN KHÁC (+, *, /, ...)
        text = re.sub(
            r'(\d+)\s*([+×*÷/=><])\s*(\d+)',
            lambda m: (f"{TextProcessor._number_to_words(m.group(1))} "
                      f"{math_map.get(m.group(2), m.group(2))} "
                      f"{TextProcessor._number_to_words(m.group(3))}"),
            text
        )
    
        # Xử lý phân số 4/5
        text = re.sub(
            r'(\d+)/(\d+)',
            lambda m: (f"{TextProcessor._number_to_words(m.group(1))} "
                      f"divided by {TextProcessor._number_to_words(m.group(2))}"),
            text
        )
    
        return text

    @staticmethod
    def _process_special_symbols(text: str) -> str:
        """Xử lý các ký hiệu đặc biệt"""
        symbol_map = {
            '@': 'at',
            '#': 'number',
            '&': 'and',
            '_': 'underscore'
        }

        # Xử lý @home → at home
        text = re.sub(
            r'@(\w+)',
            lambda m: f"at {m.group(1)}",
            text
        )

        # Xử lý #1 → number one
        text = re.sub(
            r'#(\d+)',
            lambda m: f"number {TextProcessor._number_to_words(m.group(1))}",
            text
        )

        # Xử lý các ký hiệu đơn lẻ
        for symbol, replacement in symbol_map.items():
            text = text.replace(symbol, f' {replacement} ')

        return text

    @staticmethod
    def _process_times(text: str) -> str:
        """Xử lý MỌI định dạng thời gian (giờ:phút:giây, có/không AM/PM)"""
        text = re.sub(
            r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM|am|pm)?\b',
            lambda m: TextProcessor._time_to_words(m.group(1), m.group(2), m.group(3), m.group(4)),
            text
        )
        return text
    
    @staticmethod
    def _time_to_words(hour: str, minute: str, second: str = None, period: str = None) -> str:
        """Chuyển thời gian thành giọng nói tự nhiên (bao gồm giây nếu có)"""
        hour_int = int(hour)
        minute_int = int(minute)
        
        # 1. Xử lý AM/PM (viết hoa chuẩn)
        period_text = f" {period.upper()}" if period else ""
        
        # 2. Chuyển đổi giờ 24h → 12h
        hour_12 = hour_int % 12
        hour_text = "twelve" if hour_12 == 0 else TextProcessor._number_to_words(str(hour_12))
        
        # 3. Xử lý phút
        minute_text = " \u200Bo'clock\u200B " if minute_int == 0 else \
                     f"oh {TextProcessor._number_to_words(minute)}" if minute_int < 10 else \
                     TextProcessor._number_to_words(minute)
        
        # 4. Xử lý giây (nếu có)
        second_text = ""
        if second and int(second) > 0:
            second_text = f" and {TextProcessor._number_to_words(second)} seconds"
        
        # 5. Ghép câu logic
        if minute_int == 0 and not second_text:
            return f"{hour_text}{minute_text}{period_text}"  # 3:00 → "three o'clock"
        else:
            return f"{hour_text} {minute_text}{second_text}{period_text}"  # 3:05:30 → "three oh five and thirty seconds"

    @staticmethod
    def _process_years(text: str) -> str:
        """Xử lý các năm trong văn bản"""
        # Xử lý năm 4 chữ số từ 1000-2999 (phổ biến nhất)
        text = re.sub(
            r'\b(1[0-9]{3}|2[0-9]{3})\b',
            lambda m: TextProcessor._year_to_words(m.group(1)),
            text
        )
    
        # Xử lý năm 2 chữ số (nếu cần)
        text = re.sub(
            r'\b([0-9]{2})\b',
            lambda m: TextProcessor._two_digit_year_to_words(m.group(1)),
            text
        )
    
        return text

    @staticmethod
    def _year_to_words(year: str) -> str:
        """Chuyển năm 4 chữ số thành chữ"""
        if len(year) != 4:
            return year
    
        # Năm từ 2000-2099 có thể đọc là "two thousand twenty-one" hoặc "twenty twenty-one"
        if year.startswith('20'):
            # Lựa chọn cách đọc phổ biến hơn
            return f"twenty {TextProcessor._two_digit_year_to_words(year[2:])}"
    
        # Các năm khác đọc bình thường
        return TextProcessor._number_to_words(year)

    @staticmethod
    def _two_digit_year_to_words(num: str) -> str:
        """Chuyển số 2 chữ số thành chữ (cho năm)"""
        if len(num) != 2:
            return num
    
        num_int = int(num)
        if num_int == 0:
            return "zero zero"
        if num_int < 10:
            return f"oh {TextProcessor._digit_to_word(num[1])}"
    
        ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
                'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
                'seventeen', 'eighteen', 'nineteen']
        tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 
               'eighty', 'ninety']
    
        if num_int < 20:
            return ones[num_int]
    
        ten, one = divmod(num_int, 10)
        if one == 0:
            return tens[ten]
        return f"{tens[ten]} {ones[one]}"        

    @staticmethod
    def _process_phone_numbers(text: str) -> str:
        """Xử lý số điện thoại với regex chính xác hơn"""
        # Pattern mới tránh xung đột với số La Mã
        phone_pattern = r'\b(\d{3})[-. ]?(\d{3})[-. ]?(\d{4})\b'
    
        def phone_to_words(match):
            groups = match.groups()
            # Đọc từng số trong từng nhóm và thêm dấu phẩy (,) để tạo ngắt nghỉ
            parts = []
            for part in groups:
                digits = ' '.join([TextProcessor._digit_to_word(d) for d in part])
                parts.append(digits)
            return ', '.join(parts)  # Thêm dấu phẩy để tạo ngắt nghỉ khi đọc
    
        return re.sub(phone_pattern, phone_to_words, text)    
        @staticmethod
        def _process_currency_numbers(text: str) -> str:
            return re.sub(
                r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\b',
                lambda m: f"{TextProcessor._number_to_words(m.group(1))} dollars" if '$' in m.group(0) 
                         else TextProcessor._number_to_words(m.group(1)),
                text
            )

    @staticmethod
    def _digit_to_word(digit: str) -> str:
        digit_map = {
            '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
            '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
        }
        return digit_map.get(digit, digit)

    @staticmethod
    def _number_to_words(number: str) -> str:
        num_str = number.replace(',', '')
    
        try:
            if '.' in num_str:
                integer_part, decimal_part = num_str.split('.')
                integer_text = TextProcessor._int_to_words(integer_part)
                decimal_text = ' '.join([TextProcessor._digit_to_word(d) for d in decimal_part])
                return f"{integer_text} point {decimal_text}"
            return TextProcessor._int_to_words(num_str)
        except:
            return number

    @staticmethod
    def _digits_to_words(digits: str) -> str:
        return ' '.join([TextProcessor._digit_to_word(d) for d in digits])

    @staticmethod
    def _int_to_words(num_str: str) -> str:
        num = int(num_str)
        if num == 0:
            return 'zero'
        
        units = ['', 'thousand', 'million', 'billion', 'trillion']
        words = []
        level = 0
        
        while num > 0:
            chunk = num % 1000
            if chunk != 0:
                words.append(TextProcessor._convert_less_than_thousand(chunk) + ' ' + units[level])
            num = num // 1000
            level += 1
        
        return ' '.join(reversed(words)).strip()

    @staticmethod
    def _convert_less_than_thousand(num: int) -> str:
        ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
                'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
                'seventeen', 'eighteen', 'nineteen']
        tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 
               'eighty', 'ninety']
        
        if num == 0:
            return ''
        if num < 20:
            return ones[num]
        if num < 100:
            return tens[num // 10] + (' ' + ones[num % 10] if num % 10 != 0 else '')
        return ones[num // 100] + ' hundred' + (' ' + TextProcessor._convert_less_than_thousand(num % 100) if num % 100 != 0 else '')

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        re_special_cases = re.compile(r'(?<!\w)([A-Z][a-z]*\.)(?=\s)')
        re_sentence_split = re.compile(r'(?<=[.!?])\s+')
        
        sentences = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                stripped = re_special_cases.sub(r'\1Ⓝ', stripped)
                parts = re_sentence_split.split(stripped)
                for part in parts:
                    part = part.replace('Ⓝ', '')
                    if part:
                        sentences.append(part)
        return sentences

    @staticmethod
    def parse_dialogues(text: str, prefixes: List[str]) -> List[Tuple[str, str]]:
        """Phân tích nội dung hội thoại với các prefix chỉ định"""
        dialogues = []
        current = None
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Kiểm tra xem dòng có bắt đầu bằng bất kỳ prefix nào không
            found_prefix = None
            for prefix in prefixes:
                if line.lower().startswith(prefix.lower() + ':'):
                    found_prefix = prefix
                    break
                    
            if found_prefix:
                if current:
                    # Xử lý các trường hợp đặc biệt trước khi thêm vào dialogues
                    processed_content = TextProcessor._process_special_cases(current[1])
                    dialogues.append((current[0], processed_content))
                
                speaker = found_prefix
                content = line[len(found_prefix)+1:].strip()
                current = (speaker, content)
            elif current:
                current = (current[0], current[1] + ' ' + line)
                
        if current:
            # Xử lý các trường hợp đặc biệt cho dòng cuối cùng
            processed_content = TextProcessor._process_special_cases(current[1])
            dialogues.append((current[0], processed_content))
            
        return dialogues


class AudioProcessor:
    @staticmethod
    def enhance_audio(audio: np.ndarray, volume: float = 1.0, pitch: float = 1.0) -> np.ndarray:
        # 1. Chuẩn hóa và bảo vệ chống clipping
        max_sample = np.max(np.abs(audio)) + 1e-8
        audio = (audio / max_sample) * 0.9 * volume  # Giữ headroom 10%
        
        # 2. Soft clipping để tránh distortion
        audio = np.tanh(audio * 1.5) / 1.5  # Hàm tanh cho soft clipping mượt
        
        # 3. Chuyển sang AudioSegment với xử lý pitch
        audio_seg = AudioSegment(
            (audio * 32767).astype(np.int16).tobytes(),
            frame_rate=24000,
            sample_width=2,
            channels=1
        )
        
        # 4. Xử lý pitch với crossfade
        if pitch != 1.0:
            audio_seg = audio_seg._spawn(
                audio_seg.raw_data,
                overrides={"frame_rate": int(audio_seg.frame_rate * pitch)}
            ).set_frame_rate(24000).fade_in(10).fade_out(10)
        
        # 5. Xử lý động và lọc tần
        audio_seg = compress_dynamic_range(
            audio_seg,
            threshold=-12.0,
            ratio=3.5,
            attack=5,
            release=50
        )
        audio_seg = audio_seg.low_pass_filter(11000).high_pass_filter(200)
        
        # 6. Chuẩn hóa an toàn
        if audio_seg.max_dBFS > -1.0:
            audio_seg = audio_seg.apply_gain(-audio_seg.max_dBFS * 0.8)
        
        return np.array(audio_seg.get_array_of_samples()) / 32768.0

    @staticmethod
    def calculate_pause(text: str, pause_settings: Dict[str, int]) -> int:
        """Calculate pause duration with more precise rules"""
        text = text.strip()
        if not text:
            return 0
            
        # Special cases that should have no pause
        if re.search(r'(?:^|\s)(?:Mr|Mrs|Ms|Dr|Prof|St|A\.M|P\.M|etc|e\.g|i\.e)\.$', text, re.IGNORECASE):
            return 0
            
        # Time formats (12:30) - minimal pause
        if re.search(r'\b\d{1,2}:\d{2}\b', text):
            return pause_settings.get('time_colon_pause', 50)  # Default 50ms for times
            
        # Determine pause based on last character
        last_char = text[-1]
        return pause_settings.get(last_char, pause_settings['default_pause'])

    @staticmethod
    def combine_segments(segments: List[AudioSegment], pauses: List[int]) -> AudioSegment:
        """Combine audio segments with frame-accurate timing"""
        combined = AudioSegment.silent(duration=0)  # Start with 0 silence
        
        for i, (seg, pause) in enumerate(zip(segments, pauses)):
            # Apply fades without affecting duration
            seg = seg.fade_in(10).fade_out(10)
            
            # Add segment
            combined += seg
            
            # Add pause if not the last segment
            if i < len(segments) - 1:
                combined += AudioSegment.silent(duration=max(50, pause))
        
        return combined
        
    @staticmethod
    def combine_with_pauses(segments: List[AudioSegment], pauses: List[int]) -> AudioSegment:
        combined = AudioSegment.empty()
        for i, (seg, pause) in enumerate(zip(segments, pauses)):
            seg = seg.fade_in(50).fade_out(50)
            combined += seg
            if i < len(segments) - 1:
                combined += AudioSegment.silent(duration=pause)
        return combined


# ==================== SYSTEM CONFIGURATION ====================
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
            {"name": "en-US-BrianNeural", "gender": "Nam"},
            {"name": "en-US-AnaNeural", "gender": "Nữ"},
            {"name": "en-US-AndrewMultilingualNeural", "gender": "Nam"},
            {"name": "en-US-AriaNeural", "gender": "Nữ"},
            {"name": "en-US-AvaMultilingualNeural", "gender": "Nữ"},
            {"name": "en-US-BrianMultilingualNeural", "gender": "Nam"},
            {"name": "en-US-ChristopherNeural", "gender": "Nam"},
            {"name": "en-US-EmmaMultilingualNeural", "gender": "Nữ"},
            {"name": "en-US-EricNeural", "gender": "Nam"},
            {"name": "en-US-MichelleNeural", "gender": "Nữ"},
            {"name": "en-US-RogerNeural", "gender": "Nam"},
            {"name": "en-US-SteffanNeural", "gender": "Nam"}
        ],
        "English (UK)": [
            {"name": "en-GB-LibbyNeural", "gender": "Nữ"},
            {"name": "en-GB-MiaNeural", "gender": "Nữ"},
            {"name": "en-GB-RyanNeural", "gender": "Nam"},
            {"name": "en-GB-MaisieNeural", "gender": "Nữ"},
            {"name": "en-GB-SoniaNeural", "gender": "Nữ"},
            {"name": "en-GB-ThomasNeural", "gender": "Nam"}
        ]
    }

# ==================== AUDIO PROCESSOR ====================
class AudioProcessor:
    @staticmethod
    def calculate_pause(text: str, pause_settings: Dict[str, int]) -> int:
        """Calculate pause duration with more precise rules"""
        text = text.strip()
        if not text:
            return 0
            
        # Special cases that should have no pause
        if re.search(r'(?:^|\s)(?:Mr|Mrs|Ms|Dr|Prof|St|A\.M|P\.M|etc|e\.g|i\.e)\.$', text, re.IGNORECASE):
            return 0
            
        # Time formats (12:30) - minimal pause
        if re.search(r'\b\d{1,2}:\d{2}\b', text):
            return pause_settings.get('time_colon_pause', 50)  # Default 50ms for times
            
        # Determine pause based on last character
        last_char = text[-1]
        return pause_settings.get(last_char, pause_settings['default_pause'])

    @staticmethod
    def combine_with_pauses(segments: List[AudioSegment], pauses: List[int]) -> AudioSegment:
        combined = AudioSegment.empty()
        for i, (seg, pause) in enumerate(zip(segments, pauses)):
            seg = seg.fade_in(50).fade_out(50)
            combined += seg
            if i < len(segments) - 1:
                combined += AudioSegment.silent(duration=pause)
        return combined

# ==================== SUBTITLE GENERATOR ====================
class SubtitleGenerator:
    @staticmethod
    def clean_subtitle_text(text: str) -> str:
        """Remove Q:/A:/CHARx: prefixes from subtitle text"""
        cleaned = re.sub(r'^(Q|A|CHAR\d+):\s*', '', text.strip())
        return cleaned
        
    @staticmethod
    def split_long_sentences(text: str, max_length: int = 120) -> List[str]:
        """Split long sentences at punctuation marks while preserving meaning"""
        sentences = []
        current = ""
        
        # Split at punctuation first
        parts = re.split(r'([.!?])', text)
        
        # Recombine with punctuation but check length
        for i in range(0, len(parts)-1, 2):
            part = parts[i] + (parts[i+1] if i+1 < len(parts) else "")
            if len(current + part) <= max_length:
                current += part
            else:
                if current:
                    sentences.append(current)
                current = part
        
        if current:
            sentences.append(current)
            
        return sentences

    @staticmethod
    def generate_srt(audio_segments: List[AudioSegment], sentences: List[str], pause_settings: Dict[str, int]) -> str:
        """Generate SRT format subtitles with precise timing information"""
        subtitles = []
        current_time = 150  # Start with initial silence (150ms)
        max_subtitle_length = 120  # Maximum characters per subtitle line
        
        for i, (seg, sentence) in enumerate(zip(audio_segments, sentences)):
            # Remove Q: and A: prefixes if present
            cleaned_sentence = re.sub(r'^(Q|A|CHAR\d+):\s*', '', sentence.strip())
            
            # Split long sentences into smaller chunks at punctuation
            sentence_chunks = SubtitleGenerator.split_long_sentences(cleaned_sentence, max_subtitle_length)
            
            # Calculate duration per chunk (equal division for simplicity)
            chunk_duration = len(seg) / max(1, len(sentence_chunks))
            
            for j, chunk in enumerate(sentence_chunks):
                start_time = current_time + (j * chunk_duration)
                end_time = start_time + chunk_duration
                
                # Add subtitle entry
                subtitles.append({
                    'start': int(start_time),
                    'end': int(end_time),
                    'text': chunk.strip()
                })
            
            # Update current time with segment duration
            current_time += len(seg)
            
            # Add pause if not the last segment
            if i < len(audio_segments) - 1:
                pause = AudioProcessor.calculate_pause(sentence, pause_settings)
                current_time += max(100, pause)
        
        # Convert to SRT format with precise timing
        srt_content = []
        for idx, sub in enumerate(subtitles, 1):
            start_time = timedelta(milliseconds=sub['start'])
            end_time = timedelta(milliseconds=sub['end'])
            
            # Format: 00:00:01,040 --> 00:00:09,760
            start_str = f"{start_time.total_seconds() // 3600:02.0f}:{(start_time.total_seconds() % 3600) // 60:02.0f}:{start_time.total_seconds() % 60:06.3f}".replace('.', ',')
            end_str = f"{end_time.total_seconds() // 3600:02.0f}:{(end_time.total_seconds() % 3600) // 60:02.0f}:{end_time.total_seconds() % 60:06.3f}".replace('.', ',')
            
            srt_content.append(
                f"{idx}\n"
                f"{start_str} --> {end_str}\n"
                f"{sub['text']}\n"
            )
        
        return "\n".join(srt_content)

# ==================== BASE PROCESSOR CLASS ====================
class BaseTTSProcessor:
    def __init__(self):
        self.voice_map = {}
        self.initialize_voices()
        self.load_settings()
        self.audio_processor = AudioProcessor()
        self.subtitle_generator = SubtitleGenerator()
        
    def initialize_voices(self):
        for lang, voices in TTSConfig.LANGUAGES.items():
            for voice in voices:
                voice_name = voice['name'].split('-')[-1].replace('Neural', '')
                display_name = f"{lang} - {voice_name} ({voice['gender']})"
                self.voice_map[display_name] = voice['name']
    
    def load_settings(self):
        if os.path.exists(TTSConfig.SETTINGS_FILE):
            with open(TTSConfig.SETTINGS_FILE, 'r') as f:
                self.settings = json.load(f)
        else:
            self.settings = {}
    
    def save_settings(self):
        with open(TTSConfig.SETTINGS_FILE, 'w') as f:
            json.dump(self.settings, f)

    async def generate_speech(self, text, voice_id, rate, pitch, volume):
        try:
            # Add random delay between requests to prevent server overload
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            rate_str = f"{rate}%" if rate != 0 else "+0%"
            pitch_str = f"+{pitch}Hz" if pitch >=0 else f"{pitch}Hz"
            
            communicate = edge_tts.Communicate(text, voice_id, rate=rate_str, pitch=pitch_str)
            temp_file = f"temp_{random.randint(1000,9999)}.mp3"
            
            # Generate audio and subtitles
            subs = []
            start_time = 0
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    with open(temp_file, "ab") as audio_file:
                        audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    subs.append({
                        "text": chunk["text"],
                        "start": chunk["offset"],
                        "end": chunk["offset"] + chunk["duration"]
                    })
                    start_time = end_time
            
            # Audio processing pipeline
            audio = AudioSegment.from_file(temp_file)
            
            # Apply volume adjustment (limit to +10dB max)
            volume_adjustment = min(max(volume - 100, -50), 10)  # Limit to +10dB max
            audio = audio + volume_adjustment
            
            # Apply audio processing effects
            audio = normalize(audio)
            audio = compress_dynamic_range(audio, threshold=-20.0, ratio=4.0)
            audio = low_pass_filter(audio, 14000)  # Reduce high-frequency hiss
            audio = high_pass_filter(audio, 100)  # Remove ultra-low frequencies
            
            # Export with higher bitrate
            audio.export(temp_file, format="mp3", bitrate="256k")
            
            return temp_file, subs
        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            return None, []

    def generate_srt(self, subtitles, output_path):
        """Generate SRT file from subtitles data"""
        if not subtitles:
            return None
            
        srt_path = output_path.replace('.mp3', '.srt')
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, start=1):
                    start = timedelta(milliseconds=sub["start"])
                    end = timedelta(milliseconds=sub["end"])
                    
                    # Format: 00:00:01,040 --> 00:00:09,760
                    start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                    end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                    
                    f.write(f"{i}\n{start_str} --> {end_str}\n{sub['text']}\n\n")
            return srt_path
        except Exception as e:
            print(f"Error generating SRT: {e}")
            return None

    def _format_time(self, milliseconds):
        """Convert milliseconds to SRT time format"""
        seconds, milliseconds = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
		
    def check_srt_generated(self, audio_path):
        if not audio_path:
            return False
        srt_path = audio_path.replace('.mp3', '.srt')
        return os.path.exists(srt_path)		

# ==================== TAB 1: SINGLE CHARACTER ====================
class StoryTTSProcessor(BaseTTSProcessor):
    def __init__(self):
        super().__init__()
        if not self.settings.get("single_char"):
            self.settings["single_char"] = {
                "language": "Tiếng Việt",
                "voice": "Tiếng Việt - HoaiMy (Nữ)",
                "rate": 0,
                "pitch": 0,
                "volume": 100,
                "pause": 500
            }
    
    async def process_story(self, content, voice, rate, pitch, volume, pause, save_settings):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        voice_dir = f"story_{timestamp}"
        os.makedirs(voice_dir, exist_ok=True)
        
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        all_subs = []
        audio_files = []
        
        for idx, text in enumerate(lines):
            try:
                temp_file, subs = await self.generate_speech(
                    text, 
                    self.voice_map[voice], 
                    rate, 
                    pitch, 
                    volume
                )
                if temp_file:
                    new_name = f"{voice_dir}/line_{idx+1:03d}.mp3"
                    os.rename(temp_file, new_name)
                    audio_files.append(new_name)
                    
                    # Process subtitles
                    if subs:
                        line_subs = []
                        for sub in subs:
                            line_subs.append({
                                "text": sub["text"],
                                "start": sub["start"],
                                "end": sub["end"]
                            })
                        all_subs.append(line_subs)
            except Exception as e:
                print(f"❌ Lỗi dòng {idx+1}: {str(e)}")
        
        if not audio_files:
            return None, None, "❌ Không tạo được file âm thanh"
        
        merged_path = self.merge_audio(voice_dir, pause)
        srt_path = self.generate_full_srt(all_subs, pause, merged_path)
        
        if save_settings:
            self.settings["single_char"] = {
                "language": next(k for k in TTSConfig.LANGUAGES.keys() if voice.startswith(k)),
                "voice": voice,
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "pause": pause
            }
            self.save_settings()
        
        return merged_path, srt_path, "✅ Hoàn thành! Bấm vào nút phát để nghe"

    def merge_audio(self, voice_dir, pause_duration):
        files = natsort.natsorted([f for f in os.listdir(voice_dir) if f.startswith("line_")])
        merged = AudioSegment.empty()
        pause = AudioSegment.silent(duration=pause_duration)
        
        for file in files:
            try:
                audio = AudioSegment.from_file(os.path.join(voice_dir, file))
                audio = audio.fade_in(50).fade_out(50)
                audio = normalize(audio)
                merged += audio + pause
            except Exception as e:
                print(f"❌ Lỗi file {file}: {str(e)}")
        
        merged = merged.low_pass_filter(15000)
        merged = compress_dynamic_range(merged)
        
        output_path = os.path.join(voice_dir, "merged_story.mp3")
        merged.export(output_path, format="mp3", bitrate="256k")
        return output_path

    def generate_full_srt(self, all_subs, pause_duration, audio_path):
        """Generate SRT for the full merged audio"""
        if not any(all_subs):
            return None
            
        vtt = webvtt.WebVTT()
        current_time = 0
        
        for line_subs in all_subs:
            for sub in line_subs:
                start = current_time + sub["start"]
                end = current_time + sub["end"]
                vtt.captions.append(webvtt.Caption(
                    self._format_time(start),
                    self._format_time(end),
                    sub["text"]
                ))
            
            # Add pause time after each line
            current_time += line_subs[-1]["end"] + pause_duration if line_subs else 0
        
        srt_path = audio_path.replace('.mp3', '.srt')
        vtt.save(srt_path)
        return srt_path

def generate_story_audio(self, text: str, voice: str, speed: float, device: str,
                       pause_settings: Dict[str, int], volume: float = 1.0, pitch: float = 1.0) -> Tuple[Tuple[int, np.ndarray], str, str]:
    start_time = time.time()
    clean_text = self.text_processor.clean_text(text)
    sentences = self.text_processor.split_sentences(clean_text)
    
    if not sentences:
        return None, "No content to read", ""
    
    audio_segments = []
    pause_durations = []
    
    # Adjust pause settings based on speed
    speed_factor = max(0.5, min(2.0, speed))
    adjusted_pause_settings = {
        k: int(v / speed_factor) for k, v in pause_settings.items()
    }
    
    # Generate each audio segment
    for sentence in sentences:
        result = self.generate_sentence_audio(sentence, voice, speed, device, volume, pitch)
        if not result:
            continue
            
        sample_rate, audio_data = result
        audio_seg = AudioSegment(
            (audio_data * 32767).astype(np.int16).tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1
        )
        audio_segments.append(audio_seg)
        
        # Calculate precise pause duration
        pause = self.audio_processor.calculate_pause(sentence, adjusted_pause_settings)
        pause_durations.append(pause)
    
    if not audio_segments:
        return None, "Failed to generate audio", ""
    
    # Combine with frame-accurate timing
    combined_audio = self.audio_processor.combine_segments(audio_segments, pause_durations)
    
    # Export with precise timing
    with io.BytesIO() as buffer:
        combined_audio.export(buffer, format="mp3", bitrate="256k", parameters=["-ar", str(combined_audio.frame_rate)])
        buffer.seek(0)
        audio_data = np.frombuffer(buffer.read(), dtype=np.uint8)
    
    # Generate subtitles with the same timing used for audio
    subtitles = self.subtitle_generator.generate_srt(audio_segments, sentences, adjusted_pause_settings)
    
    stats = (f"Processed {len(clean_text)} chars, {len(clean_text.split())} words\n"
            f"Audio duration: {len(combined_audio)/1000:.2f}s\n"
            f"Time: {time.time() - start_time:.2f}s\n"
            f"Device: {device.upper()}")
    
    return (combined_audio.frame_rate, audio_data), stats, subtitles	

# ==================== TAB 2: MULTI CHARACTER ====================
class MultiCharacterTTSProcessor(BaseTTSProcessor):
    def __init__(self):
        super().__init__()
        if not self.settings.get("multi_char"):
            self.settings["multi_char"] = {
                "language_char1": "Tiếng Việt",
                "voice_char1": "Tiếng Việt - HoaiMy (Nữ)",
                "language_char2": "Tiếng Việt",
                "voice_char2": "Tiếng Việt - NamMinh (Nam)",
                "language_char3": "Tiếng Việt",
                "voice_char3": "Tiếng Việt - HoaiMy (Nữ)",
                "rate_char1": -20,
                "pitch_char1": 0,
                "volume_char1": 100,
                "rate_char2": -25,
                "pitch_char2": 0,
                "volume_char2": 100,
                "rate_char3": -15,
                "pitch_char3": 0,
                "volume_char3": 100,
                "repeat_times": 1,
                "pause_between": 500
            }
    
    def parse_story(self, content):
        dialogues = []
        
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
                
            if line.upper().startswith("CHAR1:"):
                dialogues.append(("CHAR1", line[6:].strip()))
            elif line.upper().startswith("CHAR2:"):
                dialogues.append(("CHAR2", line[6:].strip()))
            elif line.upper().startswith("CHAR3:"):
                dialogues.append(("CHAR3", line[6:].strip()))
            elif line.upper().startswith("NARRATOR:"):
                dialogues.append(("NARRATOR", line[9:].strip()))
            else:
                if dialogues:
                    last_char, last_text = dialogues[-1]
                    dialogues[-1] = (last_char, f"{last_text} {line}")
        
        return dialogues

    async def process_story(self, content, output_format, 
                          char1_voice, char2_voice, char3_voice,
                          char1_rate, char2_rate, char3_rate,
                          char1_pitch, char2_pitch, char3_pitch,
                          char1_volume, char2_volume, char3_volume,
                          repeat_times, pause_between, save_settings):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        voice_dir = f"story_{timestamp}"
        os.makedirs(voice_dir, exist_ok=True)

        dialogues = self.parse_story(content)
        all_subs = []
        audio_files = []
        
        for idx, (character, text) in enumerate(dialogues):
            file_prefix = f"{idx+1:03d}"
            
            if character == "CHAR1":
                voice_id = self.voice_map[char1_voice]
                rate = char1_rate
                pitch = char1_pitch
                volume = char1_volume
                file_name = f"{file_prefix}_CHAR1.{output_format.lower()}"
            elif character == "CHAR2":
                voice_id = self.voice_map[char2_voice]
                rate = char2_rate
                pitch = char2_pitch
                volume = char2_volume
                file_name = f"{file_prefix}_CHAR2.{output_format.lower()}"
            elif character == "CHAR3":
                voice_id = self.voice_map[char3_voice]
                rate = char3_rate
                pitch = char3_pitch
                volume = char3_volume
                file_name = f"{file_prefix}_CHAR3.{output_format.lower()}"
            else:  # NARRATOR
                voice_id = self.voice_map[char1_voice]
                rate = char1_rate
                pitch = char1_pitch
                volume = char1_volume
                file_name = f"{file_prefix}_NARRATOR.{output_format.lower()}"

            try:
                temp_file, subs = await self.generate_speech(text, voice_id, rate, pitch, volume)
                if temp_file:
                    new_path = os.path.join(voice_dir, file_name)
                    os.rename(temp_file, new_path)
                    audio_files.append(new_path)
                    
                    if subs:
                        char_subs = []
                        for sub in subs:
                            char_subs.append({
                                "text": f"{character}: {sub['text']}",
                                "start": sub["start"],
                                "end": sub["end"]
                            })
                        all_subs.append(char_subs)
            except Exception as e:
                print(f"❌ Lỗi khi tạo giọng nói cho đoạn {idx+1}: {str(e)}")

        if not audio_files:
            return None, None, "❌ Không tạo được file âm thanh"

        merged_path = self.merge_story(voice_dir, output_format, repeat_times, pause_between)
        srt_path = self.generate_full_srt(all_subs, pause_between, merged_path, repeat_times)
        
        if save_settings:
            self.settings["multi_char"] = {
                "language_char1": next(k for k in TTSConfig.LANGUAGES.keys() if char1_voice.startswith(k)),
                "voice_char1": char1_voice,
                "language_char2": next(k for k in TTSConfig.LANGUAGES.keys() if char2_voice.startswith(k)),
                "voice_char2": char2_voice,
                "language_char3": next(k for k in TTSConfig.LANGUAGES.keys() if char3_voice.startswith(k)),
                "voice_char3": char3_voice,
                "rate_char1": char1_rate,
                "pitch_char1": char1_pitch,
                "volume_char1": char1_volume,
                "rate_char2": char2_rate,
                "pitch_char2": char2_pitch,
                "volume_char2": char2_volume,
                "rate_char3": char3_rate,
                "pitch_char3": char3_pitch,
                "volume_char3": char3_volume,
                "repeat_times": repeat_times,
                "pause_between": pause_between
            }
            self.save_settings()

        return merged_path, srt_path, "✅ Hoàn thành! Bấm vào nút phát để nghe"

    def merge_story(self, voice_dir, fmt, repeat_count, pause_between):
        all_files = sorted(
            [f for f in os.listdir(voice_dir) if f.endswith(f".{fmt.lower()}")],
            key=lambda x: int(x.split('_')[0])
        )
        
        merged = AudioSegment.empty()
        pause = AudioSegment.silent(duration=pause_between)

        for file in all_files:
            try:
                audio = AudioSegment.from_file(os.path.join(voice_dir, file))
                audio = audio.fade_in(50).fade_out(50)
                for _ in range(repeat_count):
                    merged += normalize(audio)
                    merged += pause
            except Exception as e:
                print(f"❌ Lỗi khi xử lý file {file}: {str(e)}")
                return None

        merged = merged.low_pass_filter(15000)
        merged = compress_dynamic_range(merged)
        
        output_path = os.path.join(voice_dir, f"story_merged.{fmt.lower()}")
        merged.export(output_path, format=fmt.lower(), bitrate="256k")
        return output_path

    def generate_full_srt(self, all_subs, pause_between, audio_path, repeat_times):
        """Generate SRT for the full merged audio with character markers"""
        if not any(all_subs):
            return None
            
        vtt = webvtt.WebVTT()
        current_time = 0
        
        for _ in range(repeat_times):
            for line_subs in all_subs:
                for sub in line_subs:
                    start = current_time + sub["start"]
                    end = current_time + sub["end"]
                    vtt.captions.append(webvtt.Caption(
                        self._format_time(start),
                        self._format_time(end),
                        sub["text"]
                    ))
                
                current_time += (line_subs[-1]["end"] if line_subs else 0) + pause_between
        
        srt_path = audio_path.replace('.mp3', '.srt')
        vtt.save(srt_path)
        return srt_path

# ==================== TAB 3: Q&A DIALOGUE ====================
class DialogueTTSProcessor(BaseTTSProcessor):
    def __init__(self):
        super().__init__()
        if not self.settings.get("dialogue"):
            self.settings["dialogue"] = {
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
    
    def parse_dialogues(self, content):
        dialogues = []
        current_speaker = None
        current_text = []

        for line in content.splitlines():
            line = line.strip()
            if not line: continue

            if line.upper().startswith(("Q:", "A:")):
                if current_speaker is not None:
                    dialogues.append((current_speaker, " ".join(current_text)))
                
                parts = line.split(":", 1)
                current_speaker = parts[0].upper()
                current_text = [parts[1].strip()] if len(parts) > 1 else [""]
            else:
                current_text.append(line)

        if current_speaker is not None:
            dialogues.append((current_speaker, " ".join(current_text)))

        return dialogues

    async def process_dialogues(self, content, output_format, 
                             language_q, voice_q, rate_q, pitch_q, volume_q,
                             language_a, voice_a, rate_a, pitch_a, volume_a,
                             repeat_times, pause_q, pause_a, save_settings):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        voice_dir = f"dialogues_{timestamp}"
        os.makedirs(voice_dir, exist_ok=True)

        dialogues = self.parse_dialogues(content)
        all_subs = []
        audio_files = []
        
        for idx, (speaker, text) in enumerate(dialogues):
            voice_id = self.voice_map[voice_q if speaker == "Q" else voice_a]
            rate = rate_q if speaker == "Q" else rate_a
            pitch = pitch_q if speaker == "Q" else pitch_a
            volume = volume_q if speaker == "Q" else volume_a

            try:
                temp_file, subs = await self.generate_speech(text, voice_id, rate, pitch, volume)
                if temp_file:
                    prefix = speaker
                    new_name = f"{voice_dir}/{prefix}_{idx+1:03d}.{output_format.lower()}"
                    os.rename(temp_file, new_name)
                    audio_files.append(new_name)
                    
                    if subs:
                        speaker_subs = []
                        for sub in subs:
                            speaker_subs.append({
                                "text": f"{speaker}: {sub['text']}",
                                "start": sub["start"],
                                "end": sub["end"]
                            })
                        all_subs.append(speaker_subs)
            except Exception as e:
                print(f"❌ Error generating speech for line {idx+1}: {str(e)}")

        if not audio_files:
            return None, None, "❌ Failed to generate audio files"

        merged_path = self.merge_with_exact_repetition(voice_dir, output_format, repeat_times, pause_q, pause_a)
        srt_path = self.generate_full_srt(all_subs, pause_q, pause_a, merged_path, repeat_times)
        
        if save_settings:
            self.settings["dialogue"] = {
                "language_q": language_q,
                "voice_q": voice_q,
                "language_a": language_a,
                "voice_a": voice_a,
                "rate_q": rate_q,
                "pitch_q": pitch_q,
                "volume_q": volume_q,
                "rate_a": rate_a,
                "pitch_a": pitch_a,
                "volume_a": volume_a,
                "repeat_times": repeat_times,
                "pause_q": pause_q,
                "pause_a": pause_a
            }
            self.save_settings()

        return merged_path, srt_path, "✅ Done! Click play to listen"

    def merge_with_exact_repetition(self, voice_dir, fmt, repeat_count, pause_q, pause_a):
        q_files = natsort.natsorted([f for f in os.listdir(voice_dir) if f.startswith("Q_") and f.endswith(f".{fmt.lower()}")])
        a_files = natsort.natsorted([f for f in os.listdir(voice_dir) if f.startswith("A_") and f.endswith(f".{fmt.lower()}")])

        if len(q_files) != len(a_files):
            print(f"❌ Mismatched Q ({len(q_files)}) and A ({len(a_files)}) files")
            return None

        merged = AudioSegment.empty()
        short_pause = AudioSegment.silent(duration=pause_q)
        long_pause = AudioSegment.silent(duration=pause_a)

        for q_file, a_file in zip(q_files, a_files):
            try:
                q_audio = AudioSegment.from_file(os.path.join(voice_dir, q_file))
                a_audio = AudioSegment.from_file(os.path.join(voice_dir, a_file))

                q_audio = q_audio.fade_in(50).fade_out(50)
                a_audio = a_audio.fade_in(50).fade_out(50)
                
                q_audio = normalize(q_audio)
                a_audio = normalize(a_audio)
                
                for _ in range(repeat_count):
                    merged += q_audio
                    merged += short_pause
                    merged += a_audio
                    merged += long_pause
            except Exception as e:
                print(f"❌ Error processing {q_file} or {a_file}: {str(e)}")
                return None

        merged = normalize(merged)
        merged = compress_dynamic_range(merged, threshold=-20.0, ratio=4.0)
        
        output_path = os.path.join(voice_dir, f"merged_repeat_{repeat_count}x.{fmt.lower()}")
        merged.export(output_path, format=fmt.lower(), bitrate="256k")
        return output_path

    def generate_full_srt(self, all_subs, pause_q, pause_a, audio_path, repeat_times):
        """Generate SRT for Q&A with exact repetition"""
        if not any(all_subs):
            return None
            
        vtt = webvtt.WebVTT()
        current_time = 0
        
        for _ in range(repeat_times):
            for i in range(0, len(all_subs), 2):
                # Process Q
                q_subs = all_subs[i] if i < len(all_subs) else []
                for sub in q_subs:
                    start = current_time + sub["start"]
                    end = current_time + sub["end"]
                    vtt.captions.append(webvtt.Caption(
                        self._format_time(start),
                        self._format_time(end),
                        sub["text"]
                    ))
                current_time += (q_subs[-1]["end"] if q_subs else 0) + pause_q
                
                # Process A
                a_subs = all_subs[i+1] if i+1 < len(all_subs) else []
                for sub in a_subs:
                    start = current_time + sub["start"]
                    end = current_time + sub["end"]
                    vtt.captions.append(webvtt.Caption(
                        self._format_time(start),
                        self._format_time(end),
                        sub["text"]
                    ))
                current_time += (a_subs[-1]["end"] if a_subs else 0) + pause_a
        
        srt_path = audio_path.replace('.mp3', '.srt')
        vtt.save(srt_path)
        return srt_path

# ==================== GRADIO INTERFACE ====================
def update_voice_dropdown(language, tab_name, char_num=None):
    processor = BaseTTSProcessor()
    voice_options = [v for v in processor.voice_map.keys() if v.startswith(language)]
    default_voice = voice_options[0] if voice_options else None
    
    if tab_name == "single":
        return gr.Dropdown(choices=voice_options, value=default_voice)
    elif tab_name == "multi":
        if char_num == 1:
            return gr.Dropdown(choices=voice_options, value=default_voice)
        elif char_num == 2:
            return gr.Dropdown(choices=voice_options, value=default_voice)
        elif char_num == 3:
            return gr.Dropdown(choices=voice_options, value=default_voice)
    elif tab_name == "dialogue":
        if char_num == "q":
            return gr.Dropdown(choices=voice_options, value=default_voice)
        elif char_num == "a":
            return gr.Dropdown(choices=voice_options, value=default_voice)

def toggle_srt_download(audio_path, message):
    if audio_path and os.path.exists(audio_path.replace('.mp3', '.srt')):
        return gr.Button(visible=True), gr.Button(visible=True)
    return gr.Button(visible=False), gr.Button(visible=False)

def show_subtitles(audio_output):
    """Xử lý mọi trường hợp đầu vào không hợp lệ"""
    # Nếu là số nguyên (sample rate), bỏ qua
    if isinstance(audio_output, (int, float)):
        return "⏳ Đang xử lý audio..."
        
    # Xử lý các trường hợp còn lại như trước
    if audio_output is None:
        return "⏳ Chưa có audio được tạo"
        
    if isinstance(audio_output, (tuple, list)) and len(audio_output) > 0:
        audio_path = audio_output[0]
    elif isinstance(audio_output, str):
        audio_path = audio_output
    else:
        return "⚠️ Định dạng đầu vào không hỗ trợ"

    if not isinstance(audio_path, str) or not audio_path.endswith('.mp3'):
        return f"⚠️ Đường dẫn audio không hợp lệ: {audio_path}"

    srt_path = audio_path.replace('.mp3', '.srt')
    if not os.path.exists(srt_path):
        return "⚠️ Không tìm thấy file phụ đề"

    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"❌ Lỗi đọc phụ đề: {str(e)}"
	
def toggle_srt_display(audio_path):
    if not audio_path:
        return gr.Button(visible=False), gr.Textbox(visible=False)
    
    srt_path = audio_path.replace('.mp3', '.srt')
    if os.path.exists(srt_path):
        return gr.Button(visible=True), gr.Textbox(visible=True)
    return gr.Button(visible=False), gr.Textbox(visible=False)

def load_subtitles(audio_path):
    if not audio_path:
        return ""
    
    srt_path = audio_path.replace('.mp3', '.srt')
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return "Không thể đọc file phụ đề"	

with gr.Blocks(title="TTS Story Generator") as app:
    gr.Markdown("<h1 style='text-align: center'>📖 TTS Story Generator</h1>")
    
    with gr.Tabs() as tabs:
        # ========== TAB 1: SINGLE CHARACTER ==========
        with gr.Tab("1 Nhân vật"):
            single_processor = StoryTTSProcessor()
            settings = single_processor.settings.get("single_char", {})
            
            with gr.Row():
                with gr.Column():
                    content = gr.Textbox(label="Nội dung truyện", lines=10, placeholder="Nhập nội dung truyện (mỗi dòng là một đoạn)...")
                    language = gr.Dropdown(
                        label="Ngôn ngữ",
                        choices=list(TTSConfig.LANGUAGES.keys()),
                        value=settings.get("language", "Tiếng Việt")
                    )
                    voice = gr.Dropdown(
                        label="Giọng đọc",
                        choices=[v for v in single_processor.voice_map.keys() if v.startswith(settings.get("language", "Tiếng Việt"))],
                        value=settings.get("voice", "Tiếng Việt - HoaiMy (Nữ)")
                    )
                    
                    rate = gr.Slider(label="Tốc độ (%)", minimum=-30, maximum=30, step=1, value=settings.get("rate", 0))
                    pitch = gr.Slider(label="Cao độ (Hz)", minimum=-30, maximum=30, step=1, value=settings.get("pitch", 0))
                    volume = gr.Slider(label="Âm lượng (%)", minimum=50, maximum=150, step=1, value=settings.get("volume", 100))
                    pause = gr.Slider(label="Khoảng nghỉ (ms)", minimum=100, maximum=2000, step=50, value=settings.get("pause", 500))
                    save_settings = gr.Checkbox(label="Lưu cài đặt", value=False)
                    submit_btn = gr.Button("🎤 Tạo truyện audio", variant="primary")
                
                with gr.Column():
                    output_audio = gr.Audio(label="Audio đã tạo", interactive=False)
                    output_text = gr.Textbox(label="Trạng thái", interactive=False)
                    
                    with gr.Row():
                        download_srt = gr.Button("📥 Tải phụ đề (.srt)", visible=False)
                        clear_btn = gr.Button("🧹 Xóa phụ đề", visible=False)
                    
                    subtitles_display = gr.Textbox(
                        label="Nội dung phụ đề",
                        interactive=False,
                        visible=True,
                        lines=10,
                        max_lines=20,
                        elem_classes=["subtitle-box"]
                    )				
            
            language.change(
                lambda lang: update_voice_dropdown(lang, "single"),
                inputs=language,
                outputs=voice
            )
            
            submit_btn.click(
                single_processor.process_story,
                inputs=[content, voice, rate, pitch, volume, pause, save_settings],
                outputs=[output_audio, download_srt, output_text]
            )
            
            output_audio.change(
                lambda audio_output: (
                    gr.Button(visible=is_valid_audio_path(audio_output)),
                    gr.Button(visible=is_valid_audio_path(audio_output))
                ),
                inputs=output_audio,
                outputs=[download_srt, clear_btn]
            ).then(
                show_subtitles,
                inputs=output_audio,
                outputs=subtitles_display
            )
            
            clear_btn.click(
                lambda: ("", False, False),
                outputs=[subtitles_display, download_srt, clear_btn]
            )

        # ========== TAB 2: MULTI CHARACTER ==========
        with gr.Tab("Đa nhân vật"):
            multi_processor = MultiCharacterTTSProcessor()
            settings = multi_processor.settings.get("multi_char", {})
            
            with gr.Row():
                with gr.Column():
                    content = gr.Textbox(label="Nội dung câu chuyện", lines=10, 
                                        placeholder="CHAR1: Lời thoại nhân vật 1\nCHAR2: Lời thoại nhân vật 2\nCHAR3: Lời thoại nhân vật 3\nNARRATOR: Lời dẫn truyện")
                    
                    with gr.Accordion("⚙️ Cài đặt giọng nói nhân vật", open=True):
                        with gr.Row():
                            char1_language = gr.Dropdown(
                                label="Ngôn ngữ NV1",
                                choices=sorted(list(TTSConfig.LANGUAGES.keys())),
                                value=settings.get("language_char1", "Tiếng Việt")
                            )
                            char1_voice = gr.Dropdown(
                                label="Giọng NV1",
                                choices=[v for v in multi_processor.voice_map.keys() if v.startswith(settings.get("language_char1", "Tiếng Việt"))],
                                value=settings.get("voice_char1", "Tiếng Việt - HoaiMy (Nữ)")
                            )
                        
                        with gr.Row():
                            char2_language = gr.Dropdown(
                                label="Ngôn ngữ NV2",
                                choices=sorted(list(TTSConfig.LANGUAGES.keys())),
                                value=settings.get("language_char2", "Tiếng Việt")
                            )
                            char2_voice = gr.Dropdown(
                                label="Giọng NV2",
                                choices=[v for v in multi_processor.voice_map.keys() if v.startswith(settings.get("language_char2", "Tiếng Việt"))],
                                value=settings.get("voice_char2", "Tiếng Việt - NamMinh (Nam)")
                            )
                        
                        with gr.Row():
                            char3_language = gr.Dropdown(
                                label="Ngôn ngữ NV3",
                                choices=sorted(list(TTSConfig.LANGUAGES.keys())),
                                value=settings.get("language_char3", "Tiếng Việt")
                            )
                            char3_voice = gr.Dropdown(
                                label="Giọng NV3",
                                choices=[v for v in multi_processor.voice_map.keys() if v.startswith(settings.get("language_char3", "Tiếng Việt"))],
                                value=settings.get("voice_char3", "Tiếng Việt - HoaiMy (Nữ)")
                            )
                    
                    with gr.Accordion("🔧 Điều chỉnh nhân vật 1", open=False):
                        char1_rate = gr.Slider(label="Tốc độ (%)", minimum=-30, maximum=30, step=1, value=settings.get("rate_char1", -20))
                        char1_pitch = gr.Slider(label="Cao độ (Hz)", minimum=-30, maximum=30, step=1, value=settings.get("pitch_char1", 0))
                        char1_volume = gr.Slider(label="Âm lượng (%)", minimum=50, maximum=150, step=1, value=settings.get("volume_char1", 100))
                    
                    with gr.Accordion("🔧 Điều chỉnh nhân vật 2", open=False):
                        char2_rate = gr.Slider(label="Tốc độ (%)", minimum=-30, maximum=30, step=1, value=settings.get("rate_char2", -25))
                        char2_pitch = gr.Slider(label="Cao độ (Hz)", minimum=-30, maximum=30, step=1, value=settings.get("pitch_char2", 0))
                        char2_volume = gr.Slider(label="Âm lượng (%)", minimum=50, maximum=150, step=1, value=settings.get("volume_char2", 100))
                    
                    with gr.Accordion("🔧 Điều chỉnh nhân vật 3", open=False):
                        char3_rate = gr.Slider(label="Tốc độ (%)", minimum=-30, maximum=30, step=1, value=settings.get("rate_char3", -15))
                        char3_pitch = gr.Slider(label="Cao độ (Hz)", minimum=-30, maximum=30, step=1, value=settings.get("pitch_char3", 0))
                        char3_volume = gr.Slider(label="Âm lượng (%)", minimum=50, maximum=150, step=1, value=settings.get("volume_char3", 100))
                    
                    with gr.Accordion("🔄 Cài đặt chung", open=False):
                        repeat_times = gr.Slider(label="Số lần lặp", minimum=1, maximum=5, step=1, value=settings.get("repeat_times", 1))
                        pause_between = gr.Slider(label="Khoảng nghỉ (ms)", minimum=100, maximum=2000, step=50, value=settings.get("pause_between", 500))
                        output_format = gr.Dropdown(label="Định dạng đầu ra", choices=["MP3", "WAV"], value="MP3")
                        save_settings = gr.Checkbox(label="Lưu cài đặt", value=False)
                    
                    submit_btn = gr.Button("🎧 Tạo câu chuyện audio", variant="primary")
                
                with gr.Column():
                    output_audio = gr.Audio(label="Audio đã tạo", interactive=False)
                    output_text = gr.Textbox(label="Trạng thái", interactive=False)
                    
                    with gr.Row():
                        download_srt = gr.Button("📥 Tải phụ đề (.srt)", visible=False)
                        clear_btn = gr.Button("🧹 Xóa phụ đề", visible=False)
                    
                    subtitles_display = gr.Textbox(
                        label="Nội dung phụ đề",
                        interactive=False,
                        visible=True,
                        lines=10,
                        max_lines=20,
                        elem_classes=["subtitle-box"]
                    )
            
            # Update voice dropdowns
            char1_language.change(
                lambda lang: update_voice_dropdown(lang, "multi", 1),
                inputs=char1_language,
                outputs=char1_voice
            )
            
            char2_language.change(
                lambda lang: update_voice_dropdown(lang, "multi", 2),
                inputs=char2_language,
                outputs=char2_voice
            )
            
            char3_language.change(
                lambda lang: update_voice_dropdown(lang, "multi", 3),
                inputs=char3_language,
                outputs=char3_voice
            )
            
            submit_btn.click(
                multi_processor.process_story,
                inputs=[content, output_format,
                       char1_voice, char2_voice, char3_voice,
                       char1_rate, char2_rate, char3_rate,
                       char1_pitch, char2_pitch, char3_pitch,
                       char1_volume, char2_volume, char3_volume,
                       repeat_times, pause_between, save_settings],
                outputs=[output_audio, download_srt, output_text]
            )
            
            output_audio.change(
                lambda audio_output: (
                    gr.Button(visible=is_valid_audio_path(audio_output)),
                    gr.Button(visible=is_valid_audio_path(audio_output))
                ),
                inputs=output_audio,
                outputs=[download_srt, clear_btn]
            ).then(
                show_subtitles,
                inputs=output_audio,
                outputs=subtitles_display
            )
            
            download_srt.click(
                lambda audio_path: audio_path.replace('.mp3', '.srt') if audio_path else None,
                inputs=output_audio,
                outputs=gr.File(label="Tải phụ đề")
            )

        # ========== TAB 3: Q&A DIALOGUE ==========
        with gr.Tab("Hỏi & Đáp"):
            dialogue_processor = DialogueTTSProcessor()
            settings = dialogue_processor.settings.get("dialogue", {})
            
            with gr.Row():
                with gr.Column():
                    content = gr.Textbox(label="Nội dung hội thoại", lines=10, 
                                       placeholder="Q: Câu hỏi\nA: Câu trả lời\nQ: Câu hỏi tiếp theo\nA: Câu trả lời tiếp theo")
                    
                    with gr.Accordion("⚙️ Cài đặt giọng nói", open=True):
                        with gr.Row():
                            language_q = gr.Dropdown(
                                label="Ngôn ngữ câu hỏi",
                                choices=sorted(list(TTSConfig.LANGUAGES.keys())),
                                value=settings.get("language_q", "Tiếng Việt")
                            )
                            voice_q = gr.Dropdown(
                                label="Giọng câu hỏi",
                                choices=[v for v in dialogue_processor.voice_map.keys() if v.startswith(settings.get("language_q", "Tiếng Việt"))],
                                value=settings.get("voice_q", "Tiếng Việt - HoaiMy (Nữ)")
                            )
                        
                        with gr.Row():
                            language_a = gr.Dropdown(
                                label="Ngôn ngữ câu trả lời",
                                choices=sorted(list(TTSConfig.LANGUAGES.keys())),
                                value=settings.get("language_a", "Tiếng Việt")
                            )
                            voice_a = gr.Dropdown(
                                label="Giọng câu trả lời",
                                choices=[v for v in dialogue_processor.voice_map.keys() if v.startswith(settings.get("language_a", "Tiếng Việt"))],
                                value=settings.get("voice_a", "Tiếng Việt - NamMinh (Nam)")
                            )
                    
                    with gr.Accordion("🔧 Điều chỉnh giọng câu hỏi", open=False):
                        rate_q = gr.Slider(label="Tốc độ (%)", minimum=-30, maximum=30, step=1, value=settings.get("rate_q", -20))
                        pitch_q = gr.Slider(label="Cao độ (Hz)", minimum=-30, maximum=30, step=1, value=settings.get("pitch_q", 0))
                        volume_q = gr.Slider(label="Âm lượng (%)", minimum=80, maximum=110, step=1, value=settings.get("volume_q", 100))
                    
                    with gr.Accordion("🔧 Điều chỉnh giọng câu trả lời", open=False):
                        rate_a = gr.Slider(label="Tốc độ (%)", minimum=-30, maximum=30, step=1, value=settings.get("rate_a", -25))
                        pitch_a = gr.Slider(label="Cao độ (Hz)", minimum=-30, maximum=30, step=1, value=settings.get("pitch_a", 0))
                        volume_a = gr.Slider(label="Âm lượng (%)", minimum=80, maximum=110, step=1, value=settings.get("volume_a", 100))
                    
                    with gr.Accordion("🔄 Cài đặt lặp lại", open=False):
                        repeat_times = gr.Slider(label="Số lần lặp", minimum=1, maximum=5, step=1, value=settings.get("repeat_times", 2))
                        pause_q = gr.Slider(label="Khoảng nghỉ câu hỏi (ms)", minimum=100, maximum=1000, step=50, value=settings.get("pause_q", 200))
                        pause_a = gr.Slider(label="Khoảng nghỉ câu trả lời (ms)", minimum=100, maximum=2000, step=50, value=settings.get("pause_a", 500))
                        output_format = gr.Dropdown(label="Định dạng đầu ra", choices=["MP3", "WAV"], value="MP3")
                        save_settings = gr.Checkbox(label="Lưu cài đặt", value=False)
                    
                    submit_btn = gr.Button("🎧 Tạo audio hội thoại", variant="primary")
                
                with gr.Column():
                    output_audio = gr.Audio(label="Audio đã tạo", interactive=False)
                    output_text = gr.Textbox(label="Trạng thái", interactive=False)
                    
                    with gr.Row():
                        download_srt = gr.Button("📥 Tải phụ đề (.srt)", visible=False)
                        clear_btn = gr.Button("🧹 Xóa phụ đề", visible=False)
                    
                    subtitles_display = gr.Textbox(
                        label="Nội dung phụ đề",
                        interactive=False,
                        visible=True,
                        lines=10,
                        max_lines=20,
                        elem_classes=["subtitle-box"]
                    )
            
            # Update voice dropdowns
            language_q.change(
                lambda lang: update_voice_dropdown(lang, "dialogue", "q"),
                inputs=language_q,
                outputs=voice_q
            )
            
            language_a.change(
                lambda lang: update_voice_dropdown(lang, "dialogue", "a"),
                inputs=language_a,
                outputs=voice_a
            )
            
            submit_btn.click(
                dialogue_processor.process_dialogues,
                inputs=[content, output_format,
                       language_q, voice_q, rate_q, pitch_q, volume_q,
                       language_a, voice_a, rate_a, pitch_a, volume_a,
                       repeat_times, pause_q, pause_a, save_settings],
                outputs=[output_audio, download_srt, output_text]
            )
            
            output_audio.change(
                lambda audio_output: (
                    gr.Button(visible=is_valid_audio_path(audio_output)),
                    gr.Button(visible=is_valid_audio_path(audio_output))
                ),
                inputs=output_audio,
                outputs=[download_srt, clear_btn]
            ).then(
                show_subtitles,
                inputs=output_audio,
                outputs=subtitles_display
            )
            
            download_srt.click(
                lambda audio_path: audio_path.replace('.mp3', '.srt') if audio_path else None,
                inputs=output_audio,
                outputs=gr.File(label="Tải phụ đề")
            )

if __name__ == "__main__":
    app.launch()
