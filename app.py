# app.py
import asyncio
import json
import os
import random
import re
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
import webvtt
import natsort
import uvicorn
import glob
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor

# ==================== SYSTEM CONFIGURATION ====================
# ==================== SYSTEM CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "tts_settings.json"
    
    LANGUAGES = {
        "Vietnamese": [
            {"name": "vi-VN-HoaiMyNeural", "gender": "👩Female", "display": "Hoài My"},
            {"name": "vi-VN-NamMinhNeural", "gender": "🤵Male", "display": "Nam Minh"}
        ],
        "English (US)": [
            {"name": "en-US-GuyNeural", "gender": "🤵Male", "display": "Guy (US)"},
            {"name": "en-US-JennyNeural", "gender": "👩Female", "display": "Jenny (US)"},
            {"name": "en-US-AvaNeural", "gender": "👩Female", "display": "Ava (US)"},
            {"name": "en-US-AndrewNeural", "gender": "🤵Male", "display": "Andrew (US)"},
            {"name": "en-US-EmmaNeural", "gender": "👩Female", "display": "Emma (US)"},
            {"name": "en-US-BrianNeural", "gender": "🤵Male", "display": "Brian (US)"},
            {"name": "en-US-AnaNeural", "gender": "👩Female", "display": "Ana (US)"},
            {"name": "en-US-AndrewMultilingualNeural", "gender": "🤵Male", "display": "Andrew (US • Multi)"},
            {"name": "en-US-AriaNeural", "gender": "👩Female", "display": "Aria (US)"},
            {"name": "en-US-AvaMultilingualNeural", "gender": "👩Female", "display": "Ava (US • Multi)"},
            {"name": "en-US-BrianMultilingualNeural", "gender": "🤵Male", "display": "Brian (US • Multi)"},
            {"name": "en-US-ChristopherNeural", "gender": "🤵Male", "display": "Christopher (US)"},
            {"name": "en-US-EmmaMultilingualNeural", "gender": "👩Female", "display": "Emma (US • Multi)"},
            {"name": "en-US-EricNeural", "gender": "🤵Male", "display": "Eric (US)"},
            {"name": "en-US-MichelleNeural", "gender": "👩Female", "display": "Michelle (US)"},
            {"name": "en-US-RogerNeural", "gender": "🤵Male", "display": "Roger (US)"},
            {"name": "en-US-SteffanNeural", "gender": "🤵Male", "display": "Steffan (US)"}
        ],
        
        "English (UK)": [
            {"name": "en-GB-LibbyNeural", "gender": "👩Female", "display": "Libby (UK)"},
            {"name": "en-GB-MiaNeural", "gender": "👩Female", "display": "Mia (UK)"},
            {"name": "en-GB-RyanNeural", "gender": "🤵Male", "display": "Ryan (UK)"},
            {"name": "en-GB-MaisieNeural", "gender": "👩Female", "display": "Maisie (UK)"},
            {"name": "en-GB-SoniaNeural", "gender": "👩Female", "display": "Sonia (UK)"},
            {"name": "en-GB-ThomasNeural", "gender": "🤵Male", "display": "Thomas (UK)"}
        ],

        "English (Australia)": [
            {"name": "en-AU-NatashaNeural", "gender": "👩Female", "display": "Natasha (AU)"},
            {"name": "en-AU-WilliamNeural", "gender": "🤵Male", "display": "William (AU)"},
            {"name": "en-AU-TinaNeural", "gender": "👩Female", "display": "Tina (AU)"},
            {"name": "en-AU-KenNeural", "gender": "🤵Male", "display": "Ken (AU)"}
        ],

        "English (Canada)": [
            {"name": "en-CA-ClaraNeural", "gender": "👩Female", "display": "Clara (CA)"},
            {"name": "en-CA-LiamNeural", "gender": "🤵Male", "display": "Liam (CA)"}
        ],

        "English (India)": [
            {"name": "en-IN-NeerjaNeural", "gender": "👩Female", "display": "Neerja (IN)"},
            {"name": "en-IN-PrabhatNeural", "gender": "🤵Male", "display": "Prabhat (IN)"}
        ],

        "Mandarin Chinese (zh-CN)": [
            {"name": "zh-CN-XiaoxiaoNeural", "gender": "👩Female", "display": "晓晓"},
            {"name": "zh-CN-YunxiNeural", "gender": "🤵Male", "display": "云希"},
            {"name": "zh-CN-YunjianNeural", "gender": "🤵Male", "display": "云健"},
            {"name": "zh-CN-XiaoyiNeural", "gender": "👩Female", "display": "晓伊"},
            {"name": "zh-CN-XiaomoNeural", "gender": "👩Female", "display": "晓墨"},
            {"name": "zh-CN-XiaoxuanNeural", "gender": "👩Female", "display": "晓萱"},
            {"name": "zh-CN-XiaohanNeural", "gender": "👩Female", "display": "晓涵"},
            {"name": "zh-CN-XiaoruiNeural", "gender": "👩Female", "display": "晓瑞"}
        ],

        "Cantonese (zh-HK)": [
            {"name": "zh-HK-HiuGaaiNeural", "gender": "👩Female", "display": "曉佳"},
            {"name": "zh-HK-HiuMaanNeural", "gender": "👩Female", "display": "曉曼"},
            {"name": "zh-HK-WanLungNeural", "gender": "🤵Male", "display": "雲龍"}
        ],

        "Taiwanese (zh-TW)": [
            {"name": "zh-TW-HsiaoChenNeural", "gender": "👩Female", "display": "曉臻"},
            {"name": "zh-TW-YunJheNeural", "gender": "🤵Male", "display": "雲哲"},
            {"name": "zh-TW-HsiaoYuNeural", "gender": "👩Female", "display": "曉雨"}
        ],

        "Japanese": [
            {"name": "ja-JP-NanamiNeural", "gender": "👩Female", "display": "七海"},
            {"name": "ja-JP-KeitaNeural", "gender": "🤵Male", "display": "圭太"},
            {"name": "ja-JP-DaichiNeural", "gender": "🤵Male", "display": "大地"},
            {"name": "ja-JP-ShioriNeural", "gender": "👩Female", "display": "詩織"},
            {"name": "ja-JP-AoiNeural", "gender": "👩Female", "display": "葵"},
            {"name": "ja-JP-MayuNeural", "gender": "👩Female", "display": "繭"},
            {"name": "ja-JP-NaokiNeural", "gender": "🤵Male", "display": "直樹"}
        ],

        "Korean": [
            {"name": "ko-KR-SunHiNeural", "gender": "👩Female", "display": "선희"},
            {"name": "ko-KR-InJoonNeural", "gender": "🤵Male", "display": "인준"},
            {"name": "ko-KR-BongJinNeural", "gender": "🤵Male", "display": "봉진"},
            {"name": "ko-KR-GookMinNeural", "gender": "🤵Male", "display": "국민"},
            {"name": "ko-KR-JiMinNeural", "gender": "👩Female", "display": "지민"},
            {"name": "ko-KR-SeoHyeonNeural", "gender": "👩Female", "display": "서현"},
            {"name": "ko-KR-SoonBokNeural", "gender": "👩Female", "display": "순복"}
        ],

        "French (France)": [
            {"name": "fr-FR-DeniseNeural", "gender": "👩Female", "display": "Denise"},
            {"name": "fr-FR-HenriNeural", "gender": "🤵Male", "display": "Henri"},
            {"name": "fr-FR-AlainNeural", "gender": "🤵Male", "display": "Alain"},
            {"name": "fr-FR-JacquelineNeural", "gender": "👩Female", "display": "Jacqueline"},
            {"name": "fr-FR-ClaudeNeural", "gender": "🤵Male", "display": "Claude"},
            {"name": "fr-FR-CelesteNeural", "gender": "👩Female", "display": "Celeste"},
            {"name": "fr-FR-EloiseNeural", "gender": "👩Female", "display": "Eloise"}
        ],

        "French (Canada)": [
            {"name": "fr-CA-SylvieNeural", "gender": "👩Female", "display": "Sylvie"},
            {"name": "fr-CA-AntoineNeural", "gender": "🤵Male", "display": "Antoine"},
            {"name": "fr-CA-JeanNeural", "gender": "🤵Male", "display": "Jean"}
        ],

        "Spanish (Spain)": [
            {"name": "es-ES-AlvaroNeural", "gender": "🤵Male", "display": "Álvaro"},
            {"name": "es-ES-ElviraNeural", "gender": "👩Female", "display": "Elvira"},
            {"name": "es-ES-AbrilNeural", "gender": "👩Female", "display": "Abril"},
            {"name": "es-ES-ManuelNeural", "gender": "🤵Male", "display": "Manuel"},
            {"name": "es-ES-TrianaNeural", "gender": "👩Female", "display": "Triana"},
            {"name": "es-ES-LiaNeural", "gender": "👩Female", "display": "Lia"}
        ],

        "Spanish (Mexico)": [
            {"name": "es-MX-DaliaNeural", "gender": "👩Female", "display": "Dalia"},
            {"name": "es-MX-JorgeNeural", "gender": "🤵Male", "display": "Jorge"},
            {"name": "es-MX-BeatrizNeural", "gender": "👩Female", "display": "Beatriz"},
            {"name": "es-MX-CandelaNeural", "gender": "👩Female", "display": "Candela"},
            {"name": "es-MX-CarlotaNeural", "gender": "👩Female", "display": "Carlota"},
            {"name": "es-MX-CecilioNeural", "gender": "🤵Male", "display": "Cecilio"}
        ],

        "Spanish (Colombia)": [
            {"name": "es-CO-SalomeNeural", "gender": "👩Female", "display": "Salome"},
            {"name": "es-CO-GonzaloNeural", "gender": "🤵Male", "display": "Gonzalo"}
        ],

        "German": [
            {"name": "de-DE-KatjaNeural", "gender": "👩Female", "display": "Katja"},
            {"name": "de-DE-ConradNeural", "gender": "🤵Male", "display": "Conrad"},
            {"name": "de-DE-AmalaNeural", "gender": "👩Female", "display": "Amala"},
            {"name": "de-DE-BerndNeural", "gender": "🤵Male", "display": "Bernd"},
            {"name": "de-DE-ChristophNeural", "gender": "🤵Male", "display": "Christoph"},
            {"name": "de-DE-LouisaNeural", "gender": "👩Female", "display": "Louisa"},
            {"name": "de-DE-MajaNeural", "gender": "👩Female", "display": "Maja"}
        ],

        "Italian": [
            {"name": "it-IT-IsabellaNeural", "gender": "👩Female", "display": "Isabella"},
            {"name": "it-IT-DiegoNeural", "gender": "🤵Male", "display": "Diego"},
            {"name": "it-IT-BenignoNeural", "gender": "🤵Male", "display": "Benigno"},
            {"name": "it-IT-PalmiraNeural", "gender": "👩Female", "display": "Palmira"},
            {"name": "it-IT-CalimeroNeural", "gender": "🤵Male", "display": "Calimero"},
            {"name": "it-IT-CataldoNeural", "gender": "🤵Male", "display": "Cataldo"},
            {"name": "it-IT-ElsaNeural", "gender": "👩Female", "display": "Elsa"}
        ],

        "Portuguese (Brazil)": [
            {"name": "pt-BR-FranciscaNeural", "gender": "👩Female", "display": "Francisca"},
            {"name": "pt-BR-AntonioNeural", "gender": "🤵Male", "display": "Antônio"},
            {"name": "pt-BR-BrendaNeural", "gender": "👩Female", "display": "Brenda"},
            {"name": "pt-BR-DonatoNeural", "gender": "🤵Male", "display": "Donato"},
            {"name": "pt-BR-ElzaNeural", "gender": "👩Female", "display": "Elza"},
            {"name": "pt-BR-FabioNeural", "gender": "🤵Male", "display": "Fabio"}
        ],

        "Portuguese (Portugal)": [
            {"name": "pt-PT-DuarteNeural", "gender": "🤵Male", "display": "Duarte"},
            {"name": "pt-PT-RaquelNeural", "gender": "👩Female", "display": "Raquel"},
            {"name": "pt-PT-FernandaNeural", "gender": "👩Female", "display": "Fernanda"}
        ],

        "Russian": [
            {"name": "ru-RU-SvetlanaNeural", "gender": "👩Female", "display": "Светлана"},
            {"name": "ru-RU-DmitryNeural", "gender": "🤵Male", "display": "Дмитрий"},
            {"name": "ru-RU-DariyaNeural", "gender": "👩Female", "display": "Дария"},
            {"name": "ru-RU-AlexanderNeural", "gender": "🤵Male", "display": "Александр"}
        ],

        "Arabic (Saudi Arabia)": [
            {"name": "ar-SA-ZariyahNeural", "gender": "👩Female", "display": "زارية"},
            {"name": "ar-SA-HamedNeural", "gender": "🤵Male", "display": "حامد"}
        ],

        "Arabic (Egypt)": [
            {"name": "ar-EG-SalmaNeural", "gender": "👩Female", "display": "سلمى"},
            {"name": "ar-EG-ShakirNeural", "gender": "🤵Male", "display": "شاكر"}
        ],

        "Arabic (UAE)": [
            {"name": "ar-AE-FatimaNeural", "gender": "👩Female", "display": "فاطمة"},
            {"name": "ar-AE-HamdanNeural", "gender": "🤵Male", "display": "حمدان"}
        ],

        "Dutch": [
            {"name": "nl-NL-ColetteNeural", "gender": "👩Female", "display": "Colette"},
            {"name": "nl-NL-FennaNeural", "gender": "👩Female", "display": "Fenna"},
            {"name": "nl-NL-MaartenNeural", "gender": "🤵Male", "display": "Maarten"},
            {"name": "nl-BE-ArnaudNeural", "gender": "🤵Male", "display": "Arnaud"},
            {"name": "nl-BE-DenaNeural", "gender": "👩Female", "display": "Dena"}
        ],

        "Polish": [
            {"name": "pl-PL-AgnieszkaNeural", "gender": "👩Female", "display": "Agnieszka"},
            {"name": "pl-PL-MarekNeural", "gender": "🤵Male", "display": "Marek"},
            {"name": "pl-PL-ZofiaNeural", "gender": "👩Female", "display": "Zofia"}
        ],

        "Turkish": [
            {"name": "tr-TR-AhmetNeural", "gender": "🤵Male", "display": "Ahmet"},
            {"name": "tr-TR-EmelNeural", "gender": "👩Female", "display": "Emel"},
            {"name": "tr-TR-FatmaNeural", "gender": "👩Female", "display": "Fatma"}
        ],

        "Thai": [
            {"name": "th-TH-PremwadeeNeural", "gender": "👩Female", "display": "เปรมวดี"},
            {"name": "th-TH-NiwatNeural", "gender": "🤵Male", "display": "นิวัฒน์"},
            {"name": "th-TH-AcharaNeural", "gender": "👩Female", "display": "อัจฉรา"}
        ],

        "Hindi": [
            {"name": "hi-IN-MadhurNeural", "gender": "🤵Male", "display": "मधुर"},
            {"name": "hi-IN-SwaraNeural", "gender": "👩Female", "display": "स्वरा"},
            {"name": "hi-IN-KiranNeural", "gender": "👩Female", "display": "किरण"}
        ],

        "Swedish": [
            {"name": "sv-SE-HilleviNeural", "gender": "👩Female", "display": "Hillevi"},
            {"name": "sv-SE-MattiasNeural", "gender": "🤵Male", "display": "Mattias"},
            {"name": "sv-SE-SofieNeural", "gender": "👩Female", "display": "Sofie"}
        ],

        "Norwegian": [
            {"name": "nb-NO-PernilleNeural", "gender": "👩Female", "display": "Pernille"},
            {"name": "nb-NO-FinnNeural", "gender": "🤵Male", "display": "Finn"},
            {"name": "nb-NO-IsleneNeural", "gender": "👩Female", "display": "Islene"}
        ],

        "Danish": [
            {"name": "da-DK-ChristelNeural", "gender": "👩Female", "display": "Christel"},
            {"name": "da-DK-JeppeNeural", "gender": "🤵Male", "display": "Jeppe"}
        ],

        "Finnish": [
            {"name": "fi-FI-NooraNeural", "gender": "👩Female", "display": "Noora"},
            {"name": "fi-FI-SelmaNeural", "gender": "👩Female", "display": "Selma"},
            {"name": "fi-FI-HarriNeural", "gender": "🤵Male", "display": "Harri"}
        ],

        "Czech": [
            {"name": "cs-CZ-VlastaNeural", "gender": "👩Female", "display": "Vlasta"},
            {"name": "cs-CZ-AntoninNeural", "gender": "🤵Male", "display": "Antonín"}
        ],

        "Greek": [
            {"name": "el-GR-AthinaNeural", "gender": "👩Female", "display": "Αθηνά"},
            {"name": "el-GR-NestorasNeural", "gender": "🤵Male", "display": "Νέστορας"}
        ],

        "Hebrew": [
            {"name": "he-IL-HilaNeural", "gender": "👩Female", "display": "הילה"},
            {"name": "he-IL-AvriNeural", "gender": "🤵Male", "display": "אברי"}
        ],

        "Indonesian": [
            {"name": "id-ID-GadisNeural", "gender": "👩Female", "display": "Gadis"},
            {"name": "id-ID-ArdiNeural", "gender": "🤵Male", "display": "Ardi"}
        ],

        "Malay": [
            {"name": "ms-MY-YasminNeural", "gender": "👩Female", "display": "Yasmin"},
            {"name": "ms-MY-OsmanNeural", "gender": "🤵Male", "display": "Osman"}
        ],

        "Filipino": [
            {"name": "fil-PH-BlessicaNeural", "gender": "👩Female", "display": "Blessica"},
            {"name": "fil-PH-AngeloNeural", "gender": "🤵Male", "display": "Angelo"}
        ],

        "Ukrainian": [
            {"name": "uk-UA-PolinaNeural", "gender": "👩Female", "display": "Поліна"},
            {"name": "uk-UA-OstapNeural", "gender": "🤵Male", "display": "Остап"}
        ],

        "Romanian": [
            {"name": "ro-RO-AlinaNeural", "gender": "👩Female", "display": "Alina"},
            {"name": "ro-RO-EmilNeural", "gender": "🤵Male", "display": "Emil"}
        ],

        "Hungarian": [
            {"name": "hu-HU-NoemiNeural", "gender": "👩Female", "display": "Noémi"},
            {"name": "hu-HU-TamasNeural", "gender": "🤵Male", "display": "Tamás"}
        ],

        "Bulgarian": [
            {"name": "bg-BG-KalinaNeural", "gender": "👩Female", "display": "Калина"},
            {"name": "bg-BG-BorislavNeural", "gender": "🤵Male", "display": "Борислав"}
        ],

        "Croatian": [
            {"name": "hr-HR-GabrijelaNeural", "gender": "👩Female", "display": "Gabrijela"},
            {"name": "hr-HR-SreckoNeural", "gender": "🤵Male", "display": "Srećko"}
        ],

        "Slovak": [
            {"name": "sk-SK-ViktoriaNeural", "gender": "👩Female", "display": "Viktória"},
            {"name": "sk-SK-LukasNeural", "gender": "🤵Male", "display": "Lukáš"}
        ],

        "Slovenian": [
            {"name": "sl-SI-PetraNeural", "gender": "👩Female", "display": "Petra"},
            {"name": "sl-SI-RokNeural", "gender": "🤵Male", "display": "Rok"}
        ],

        "Serbian": [
            {"name": "sr-RS-NicholasNeural", "gender": "🤵Male", "display": "Nicholas"},
            {"name": "sr-RS-SophieNeural", "gender": "👩Female", "display": "Sophie"}
        ],

        "Catalan": [
            {"name": "ca-ES-JoanaNeural", "gender": "👩Female", "display": "Joana"},
            {"name": "ca-ES-AlbaNeural", "gender": "👩Female", "display": "Alba"},
            {"name": "ca-ES-EnricNeural", "gender": "🤵Male", "display": "Enric"}
        ],

        "Estonian": [
            {"name": "et-EE-AnuNeural", "gender": "👩Female", "display": "Anu"},
            {"name": "et-EE-KertNeural", "gender": "🤵Male", "display": "Kert"}
        ],

        "Latvian": [
            {"name": "lv-LV-EveritaNeural", "gender": "👩Female", "display": "Everita"},
            {"name": "lv-LV-NilsNeural", "gender": "🤵Male", "display": "Nils"}
        ],

        "Lithuanian": [
            {"name": "lt-LT-OnaNeural", "gender": "👩Female", "display": "Ona"},
            {"name": "lt-LT-LeonasNeural", "gender": "🤵Male", "display": "Leonas"}
        ],

        "Maltese": [
            {"name": "mt-MT-GraceNeural", "gender": "👩Female", "display": "Grace"},
            {"name": "mt-MT-JosephNeural", "gender": "🤵Male", "display": "Joseph"}
        ],

        "Welsh": [
            {"name": "cy-GB-NiaNeural", "gender": "👩Female", "display": "Nia"},
            {"name": "cy-GB-AledNeural", "gender": "🤵Male", "display": "Aled"}
        ],

        "Icelandic": [
            {"name": "is-IS-GudrunNeural", "gender": "👩Female", "display": "Guðrún"},
            {"name": "is-IS-GunnarNeural", "gender": "🤵Male", "display": "Gunnar"}
        ],

        "Irish": [
            {"name": "ga-IE-OrlaNeural", "gender": "👩Female", "display": "Orla"},
            {"name": "ga-IE-ColmNeural", "gender": "🤵Male", "display": "Colm"}
        ],

        "Albanian": [
            {"name": "sq-AL-AnilaNeural", "gender": "👩Female", "display": "Anila"},
            {"name": "sq-AL-IlirNeural", "gender": "🤵Male", "display": "Ilir"}
        ],

        "Armenian": [
            {"name": "hy-AM-AnahitNeural", "gender": "👩Female", "display": "Անահիտ"},
            {"name": "hy-AM-HaykNeural", "gender": "🤵Male", "display": "Հայկ"}
        ],

        "Azerbaijani": [
            {"name": "az-AZ-BanuNeural", "gender": "👩Female", "display": "Banu"},
            {"name": "az-AZ-BabekNeural", "gender": "🤵Male", "display": "Babək"}
        ],

        "Bengali": [
            {"name": "bn-BD-NabanitaNeural", "gender": "👩Female", "display": "নবনীতা"},
            {"name": "bn-BD-PradeepNeural", "gender": "🤵Male", "display": "প্রদীপ"}
        ],

        "Georgian": [
            {"name": "ka-GE-EkaNeural", "gender": "👩Female", "display": "ეკა"},
            {"name": "ka-GE-GiorgiNeural", "gender": "🤵Male", "display": "გიორგი"}
        ],

        "Kazakh": [
            {"name": "kk-KZ-AigulNeural", "gender": "👩Female", "display": "Айгүл"},
            {"name": "kk-KZ-DauletNeural", "gender": "🤵Male", "display": "Дәулет"}
        ],

        "Khmer": [
            {"name": "km-KH-SreymomNeural", "gender": "👩Female", "display": "ស្រីមុំ"},
            {"name": "km-KH-PisethNeural", "gender": "🤵Male", "display": "ពិសិដ្ឋ"}
        ],

        "Lao": [
            {"name": "lo-LA-KeomanyNeural", "gender": "👩Female", "display": "ແກ້ວມະນີ"},
            {"name": "lo-LA-ChanthavongNeural", "gender": "🤵Male", "display": "ຈັນທະວົງ"}
        ],

        "Mongolian": [
            {"name": "mn-MN-YesuiNeural", "gender": "👩Female", "display": "Есүй"},
            {"name": "mn-MN-BataaNeural", "gender": "🤵Male", "display": "Батаа"}
        ],

        "Nepali": [
            {"name": "ne-NP-HemkalaNeural", "gender": "👩Female", "display": "हेमकला"},
            {"name": "ne-NP-SagarNeural", "gender": "🤵Male", "display": "सागर"}
        ],

        "Sinhala": [
            {"name": "si-LK-ThiliniNeural", "gender": "👩Female", "display": "තිලිනි"},
            {"name": "si-LK-SameeraNeural", "gender": "🤵Male", "display": "සමීර"}
        ],

        "Tamil": [
            {"name": "ta-IN-PallaviNeural", "gender": "👩Female", "display": "பல்லவி"},
            {"name": "ta-IN-ValluvarNeural", "gender": "🤵Male", "display": "வள்ளுவர்"}
        ],

        "Telugu": [
            {"name": "te-IN-ShrutiNeural", "gender": "👩Female", "display": "శ్రుతి"},
            {"name": "te-IN-MohanNeural", "gender": "🤵Male", "display": "మోహన్"}
        ],

        "Urdu": [
            {"name": "ur-PK-UzmaNeural", "gender": "👩Female", "display": "عظمیٰ"},
            {"name": "ur-PK-AsadNeural", "gender": "🤵Male", "display": "اسد"}
        ],

        "Persian": [
            {"name": "fa-IR-DilaraNeural", "gender": "👩Female", "display": "دلارا"},
            {"name": "fa-IR-FaridNeural", "gender": "🤵Male", "display": "فرید"}
        ],

        "Afrikaans": [
            {"name": "af-ZA-AdriNeural", "gender": "👩Female", "display": "Adri"},
            {"name": "af-ZA-WillemNeural", "gender": "🤵Male", "display": "Willem"}
        ],

        "Swahili": [
            {"name": "sw-KE-ZuriNeural", "gender": "👩Female", "display": "Zuri"},
            {"name": "sw-KE-RafikiNeural", "gender": "🤵Male", "display": "Rafiki"}
        ],

        "Yoruba": [
            {"name": "yo-NG-AdeolaNeural", "gender": "👩Female", "display": "Adeola"},
            {"name": "yo-NG-AremuNeural", "gender": "🤵Male", "display": "Aremu"}
        ],

        "Zulu": [
            {"name": "zu-ZA-ThandoNeural", "gender": "👩Female", "display": "Thando"},
            {"name": "zu-ZA-ThembaNeural", "gender": "🤵Male", "display": "Themba"}
        ],

        "Hausa": [
            {"name": "ha-NG-AishaNeural", "gender": "👩Female", "display": "Aisha"},
            {"name": "ha-NG-AbdullahiNeural", "gender": "🤵Male", "display": "Abdullahi"}
        ],

        "Igbo": [
            {"name": "ig-NG-EbeleNeural", "gender": "👩Female", "display": "Ebele"},
            {"name": "ig-NG-ChineduNeural", "gender": "🤵Male", "display": "Chinedu"}
        ],

        "Somali": [
            {"name": "so-SO-UbaxNeural", "gender": "👩Female", "display": "Ubax"},
            {"name": "so-SO-MuuseNeural", "gender": "🤵Male", "display": "Muuse"}
        ]
    }
    
    OUTPUT_FORMATS = ["mp3", "wav"]
    
    # Default pause settings (in milliseconds)
    DEFAULT_PAUSE_SETTINGS = {
        ".": 500,
        "!": 600,
        "?": 600,
        ",": 300,
        ";": 400,
        ":": 350,
        "default_pause": 250,
        "time_colon_pause": 50
    }

# ==================== TASK MANAGER ====================
class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.executor = ThreadPoolExecutor(max_workers=2)  # Giảm workers cho Render
    
    def create_task(self, task_id: str, task_type: str):
        self.tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "progress": 0,
            "message": "Task created",
            "result": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        return task_id
    
    def update_task(self, task_id: str, status: str = None, progress: int = None, 
                   message: str = None, result: dict = None):
        if task_id in self.tasks:
            if status:
                self.tasks[task_id]["status"] = status
            if progress is not None:
                self.tasks[task_id]["progress"] = progress
            if message:
                self.tasks[task_id]["message"] = message
            if result:
                self.tasks[task_id]["result"] = result
            self.tasks[task_id]["updated_at"] = datetime.now()
    
    def get_task(self, task_id: str):
        return self.tasks.get(task_id)
    
    def cleanup_old_tasks(self, hours_old: int = 1):
        """Cleanup tasks older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours_old)
        to_delete = []
        
        for task_id, task_data in self.tasks.items():
            if task_data["created_at"] < cutoff_time:
                to_delete.append(task_id)
        
        for task_id in to_delete:
            del self.tasks[task_id]

# ==================== TEXT PROCESSOR ====================
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
        """Process emails with correct English pronunciation"""
        def convert_email(match):
            full_email = match.group(0)
            processed = (full_email
                        .replace('@', ' at ')
                        .replace('.', ' dot ')
                        .replace('-', ' dash ')
                        .replace('_', ' underscore ')
                        .replace('+', ' plus ')
                        .replace('/', ' slash ')
                        .replace('=', ' equals '))
            return processed

        email_pattern = r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b'
        return re.sub(email_pattern, convert_email, text)

    @staticmethod
    def _process_websites(text: str) -> str:
        """Process websites with correct English pronunciation"""
        def convert_website(match):
            url = match.group(1)
            return (url.replace('.', ' dot ')
                     .replace('-', ' dash ')
                     .replace('_', ' underscore ')
                     .replace('/', ' slash ')
                     .replace('?', ' question mark ')
                     .replace('=', ' equals ')
                     .replace('&', ' ampersand '))

        website_pattern = r'\b(?![\w.-]*@)((?:https?://)?(?:www\.)?[\w.-]+\.[a-z]{2,}(?:[/?=&#][\w.-]*)*)\b'
        return re.sub(website_pattern, convert_website, text, flags=re.IGNORECASE)

    @staticmethod
    def _process_temperatures(text: str) -> str:
        """Process temperatures and cardinal directions"""
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
                '': 'degrees'
            }
            unit_text = unit_map.get(unit, f'degrees {unit}')
            
            return f"{temp_text} {unit_text}"
        
        text = re.sub(
            r'(-?\d+)°([NSEWCFnsewcf]?)',
            lambda m: temp_to_words(m.group(1), m.group(2)),
            text,
            flags=re.IGNORECASE
        )
        
        text = re.sub(r'°', ' degrees ', text)
        return text

    @staticmethod
    def _process_measurements(text: str) -> str:
        """Xử lý đơn vị đo lường"""
        units_map = {
            'km/h': 'kilometers per hour',
            'mph': 'miles per hour',
            'kg': 'kilograms',
            'g': 'grams',
            'cm': 'centimeters',
            'm': 'meter',
            'mm': 'millimeters',
            'L': 'liter',
            'l': 'liter',
            'ml': 'milliliter',
            'mL': 'milliliter',
            'h': 'hour',
            'min': 'minute',
            's': 'second'
        }
    
        plural_units = {'L', 'l', 'mL', 'ml'}
    
        def measurement_to_words(value, unit):
            try:
                unit_lower = unit.lower()
                unit_text = units_map.get(unit, units_map.get(unit_lower, unit))
    
                if '.' in value:
                    integer, decimal = value.split('.')
                    value_text = (
                        f"{TextProcessor._number_to_words(integer)} "
                        f"point {' '.join(TextProcessor._digit_to_word(d) for d in decimal)}"
                    )
                else:
                    value_text = TextProcessor._number_to_words(value)
    
                if float(value) != 1 and unit in units_map and unit not in plural_units:
                    unit_text += 's'
    
                return f"{value_text} {unit_text}"
            except:
                return f"{value}{unit}"
    
        text = re.sub(
            r'(-?\d+\.?\d*)\s*({})s?\b'.format('|'.join(re.escape(key) for key in units_map.keys())),
            lambda m: measurement_to_words(m.group(1), m.group(2)),
            text,
            flags=re.IGNORECASE
        )
        return text
    
    @staticmethod
    def _process_currency(text: str) -> str:
        """Xử lý tiền tệ"""
        currency_map = {
            '$': 'dollars',
            '€': 'euros',
            '£': 'pounds',
            '¥': 'yen',
            '₩': 'won',
            '₽': 'rubles'
        }
    
        def currency_to_words(value, symbol):
            if value.endswith('.'):
                value = value[:-1]
                return f"{TextProcessor._number_to_words(value)} {currency_map.get(symbol, '')}."
    
            if '.' in value:
                integer_part, decimal_part = value.split('.')
                decimal_part = decimal_part.ljust(2, '0')
                return (
                    f"{TextProcessor._number_to_words(integer_part)} {currency_map.get(symbol, '')} "
                    f"and {TextProcessor._number_to_words(decimal_part)} cents"
                )
    
            return f"{TextProcessor._number_to_words(value)} {currency_map.get(symbol, '')}"
    
        text = re.sub(
            r'([$€£¥₩₽])(\d+(?:\.\d+)?)(?=\s|$|\.|,|;)',
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
            '-': 'minus',
            '×': 'times',
            '*': 'times',
            '÷': 'divided by',
            '/': 'divided by',
            '=': 'equals',
            '>': 'is greater than',
            '<': 'is less than'
        }
    
        text = re.sub(
            r'(\d+)\s*-\s*(\d+)(?!\s*[=+×*÷/><])',
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} to {TextProcessor._number_to_words(m.group(2))}",
            text
        )
    
        text = re.sub(
            r'(\d+)\s*-\s*(\d+)(?=\s*[=+×*÷/><])',
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} minus {TextProcessor._number_to_words(m.group(2))}",
            text
        )
    
        text = re.sub(
            r'(\d+)\s*([+×*÷/=><])\s*(\d+)',
            lambda m: (f"{TextProcessor._number_to_words(m.group(1))} "
                      f"{math_map.get(m.group(2), m.group(2))} "
                      f"{TextProcessor._number_to_words(m.group(3))}"),
            text
        )
    
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

        text = re.sub(
            r'@(\w+)',
            lambda m: f"at {m.group(1)}",
            text
        )

        text = re.sub(
            r'#(\d+)',
            lambda m: f"number {TextProcessor._number_to_words(m.group(1))}",
            text
        )

        for symbol, replacement in symbol_map.items():
            text = text.replace(symbol, f' {replacement} ')

        return text

    @staticmethod
    def _process_times(text: str) -> str:
        """Xử lý thời gian"""
        text = re.sub(
            r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM|am|pm)?\b',
            lambda m: TextProcessor._time_to_words(m.group(1), m.group(2), m.group(3), m.group(4)),
            text
        )
        return text
    
    @staticmethod
    def _time_to_words(hour: str, minute: str, second: str = None, period: str = None) -> str:
        hour_int = int(hour)
        minute_int = int(minute)
        
        period_text = f" {period.upper()}" if period else ""
        hour_12 = hour_int % 12
        hour_text = "twelve" if hour_12 == 0 else TextProcessor._number_to_words(str(hour_12))
        
        minute_text = " \u200Bo'clock\u200B " if minute_int == 0 else \
                     f"oh {TextProcessor._number_to_words(minute)}" if minute_int < 10 else \
                     TextProcessor._number_to_words(minute)
        
        second_text = ""
        if second and int(second) > 0:
            second_text = f" and {TextProcessor._number_to_words(second)} seconds"
        
        if minute_int == 0 and not second_text:
            return f"{hour_text}{minute_text}{period_text}"
        else:
            return f"{hour_text} {minute_text}{second_text}{period_text}"

    @staticmethod
    def _process_years(text: str) -> str:
        """Xử lý các năm"""
        text = re.sub(
            r'\b(1[0-9]{3}|2[0-9]{3})\b',
            lambda m: TextProcessor._year_to_words(m.group(1)),
            text
        )
    
        text = re.sub(
            r'\b([0-9]{2})\b',
            lambda m: TextProcessor._two_digit_year_to_words(m.group(1)),
            text
        )
    
        return text

    @staticmethod
    def _year_to_words(year: str) -> str:
        if len(year) != 4:
            return year
    
        if year.startswith('20'):
            return f"twenty {TextProcessor._two_digit_year_to_words(year[2:])}"
    
        return TextProcessor._number_to_words(year)

    @staticmethod
    def _two_digit_year_to_words(num: str) -> str:
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
        """Xử lý số điện thoại"""
        phone_pattern = r'\b(\d{3})[-. ]?(\d{3})[-. ]?(\d{4})\b'
    
        def phone_to_words(match):
            groups = match.groups()
            parts = []
            for part in groups:
                digits = ' '.join([TextProcessor._digit_to_word(d) for d in part])
                parts.append(digits)
            return ', '.join(parts)
    
        return re.sub(phone_pattern, phone_to_words, text)

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
                
            found_prefix = None
            for prefix in prefixes:
                if line.lower().startswith(prefix.lower() + ':'):
                    found_prefix = prefix
                    break
                    
            if found_prefix:
                if current:
                    processed_content = TextProcessor._process_special_cases(current[1])
                    dialogues.append((current[0], processed_content))
                
                speaker = found_prefix
                content = line[len(found_prefix)+1:].strip()
                current = (speaker, content)
            elif current:
                current = (current[0], current[1] + ' ' + line)
                
        if current:
            processed_content = TextProcessor._process_special_cases(current[1])
            dialogues.append((current[0], processed_content))
            
        return dialogues

# ==================== AUDIO CACHE MANAGER ====================
class AudioCacheManager:
    def __init__(self):
        self.cache_dir = "audio_cache"
        self.max_cache_size = 50  # Giảm cache size cho Render
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_cache_key(self, text: str, voice_id: str, rate: int, pitch: int, volume: int) -> str:
        """Tạo cache key từ các tham số"""
        import hashlib
        key_string = f"{text}_{voice_id}_{rate}_{pitch}_{volume}"
        return hashlib.md5(key_string.encode()).hexdigest()[:12]  # Giới hạn độ dài
    
    def get_cached_audio(self, cache_key: str) -> Optional[str]:
        """Lấy file audio từ cache nếu tồn tại"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        if os.path.exists(cache_file):
            # Kiểm tra thời gian cache (không quá 1 ngày)
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 86400:  # 24 giờ
                return cache_file
        return None
    
    def save_to_cache(self, cache_key: str, audio_file: str):
        """Lưu audio vào cache"""
        try:
            # Giới hạn số file trong cache
            cache_files = os.listdir(self.cache_dir)
            if len(cache_files) >= self.max_cache_size:
                # Xóa file cũ nhất
                oldest_file = min(
                    [os.path.join(self.cache_dir, f) for f in cache_files],
                    key=os.path.getmtime
                )
                try:
                    os.remove(oldest_file)
                except:
                    pass
            
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
            shutil.copy(audio_file, cache_file)
            return cache_file
        except Exception as e:
            print(f"Error saving to cache: {e}")
            return None
    
    def clear_cache(self):
        """Xóa toàn bộ cache"""
        try:
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.cache_manager = AudioCacheManager()
        self.load_settings()
        self.initialize_directories()
    
    def initialize_directories(self):
        """Khởi tạo các thư mục cần thiết"""
        directories = ["outputs", "temp", "audio_cache", "static", "templates"]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def load_settings(self):
        if os.path.exists(TTSConfig.SETTINGS_FILE):
            with open(TTSConfig.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        else:
            self.settings = {
                "single_voice": {
                    "language": "Tiếng Việt",
                    "voice": "vi-VN-HoaiMyNeural",
                    "rate": 0,
                    "pitch": 0,
                    "volume": 100,
                    "pause": 500
                },
                "multi_voice": {
                    "char1": {
                        "language": "Tiếng Việt",
                        "voice": "vi-VN-HoaiMyNeural", 
                        "rate": 0, 
                        "pitch": 0, 
                        "volume": 100
                    },
                    "char2": {
                        "language": "Tiếng Việt",
                        "voice": "vi-VN-NamMinhNeural", 
                        "rate": -10, 
                        "pitch": 0, 
                        "volume": 100
                    },
                    "pause": 500,
                    "repeat": 1
                },
                "qa_voice": {
                    "question": {
                        "language": "Tiếng Việt",
                        "voice": "vi-VN-HoaiMyNeural", 
                        "rate": 0, 
                        "pitch": 0, 
                        "volume": 100
                    },
                    "answer": {
                        "language": "Tiếng Việt",
                        "voice": "vi-VN-NamMinhNeural", 
                        "rate": -10, 
                        "pitch": 0, 
                        "volume": 100
                    },
                    "pause_q": 200,
                    "pause_a": 500,
                    "repeat": 2
                }
            }
            self.save_settings()
    
    def save_settings(self):
        with open(TTSConfig.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, pitch: int = 0, volume: int = 100, task_id: str = None):
        """Generate speech using edge-tts with cache optimization"""
        try:
            # Kiểm tra cache trước
            cache_key = self.cache_manager.get_cache_key(text, voice_id, rate, pitch, volume)
            cached_file = self.cache_manager.get_cached_audio(cache_key)
            
            if cached_file:
                # Tạo file tạm từ cache
                temp_file = f"temp/cache_{uuid.uuid4().hex[:8]}.mp3"
                shutil.copy(cached_file, temp_file)
                return temp_file, []
            
            # Tạo unique ID để tránh cache
            unique_id = uuid.uuid4().hex[:8]
            
            # Format parameters
            rate_str = f"{rate}%" if rate != 0 else "+0%"
            pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
            
            # Tạo communicate object
            communicate = edge_tts.Communicate(
                text, 
                voice_id, 
                rate=rate_str, 
                pitch=pitch_str
            )
            
            audio_chunks = []
            subtitles = []
            
            # Stream audio data
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    subtitles.append({
                        "text": chunk["text"],
                        "start": chunk["offset"],
                        "end": chunk["offset"] + chunk["duration"]
                    })
            
            if not audio_chunks:
                return None, []
            
            # Lưu audio vào file tạm
            audio_data = b"".join(audio_chunks)
            temp_file = f"temp/audio_{unique_id}_{int(time.time())}.mp3"
            
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Xử lý audio
            try:
                audio = AudioSegment.from_file(temp_file)
                
                # Điều chỉnh volume
                volume_adjustment = min(max(volume - 100, -50), 10)
                audio = audio + volume_adjustment
                
                # Áp dụng các hiệu ứng audio cơ bản
                audio = normalize(audio)
                audio = compress_dynamic_range(audio, threshold=-20.0, ratio=4.0)
                
                # Xuất với chất lượng cao
                audio.export(temp_file, format="mp3", bitrate="256k")
                
                # Lưu vào cache
                self.cache_manager.save_to_cache(cache_key, temp_file)
                
                return temp_file, subtitles
            except Exception as e:
                print(f"Error processing audio: {e}")
                # Trả về file gốc nếu xử lý lỗi
                return temp_file, subtitles
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None, []
    
    def generate_srt(self, subtitles: List[dict], output_path: str):
        """Generate SRT file from subtitles"""
        if not subtitles:
            return None
        
        srt_path = output_path.replace('.mp3', '.srt')
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, start=1):
                    start = timedelta(milliseconds=sub["start"])
                    end = timedelta(milliseconds=sub["end"])
                    
                    start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                    end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                    
                    f.write(f"{i}\n{start_str} --> {end_str}\n{sub['text']}\n\n")
            return srt_path
        except Exception as e:
            print(f"Error generating SRT: {e}")
            return None
    
    async def process_single_voice(self, text: str, voice_id: str, rate: int, pitch: int, 
                                 volume: int, pause: int, output_format: str = "mp3", task_id: str = None):
        """Process text with single voice - Optimized version"""
        # Xóa cache và file cũ trước khi bắt đầu
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = f"outputs/single_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Xử lý text
        sentences = self.text_processor.split_sentences(text)
        
        # Giới hạn số lượng câu để xử lý nhanh hơn
        MAX_SENTENCES = 50  # Giảm cho Render
        if len(sentences) > MAX_SENTENCES:
            sentences = sentences[:MAX_SENTENCES]
            print(f"Processing {MAX_SENTENCES} sentences only for performance")
        
        # Tạo semaphore để giới hạn concurrent requests
        SEMAPHORE = asyncio.Semaphore(2)  # Giảm concurrent requests
        
        async def bounded_generate(sentence, index):
            async with SEMAPHORE:
                # Cập nhật progress nếu có task_id
                if task_id and task_manager:
                    progress = int((index / len(sentences)) * 90)
                    task_manager.update_task(task_id, progress=progress, 
                                           message=f"Processing sentence {index+1}/{len(sentences)}")
                
                return await self.generate_speech(sentence, voice_id, rate, pitch, volume)
        
        # Xử lý các câu theo batch
        audio_segments = []
        all_subtitles = []
        
        for i in range(0, len(sentences), 2):  # Batch size = 2 (giảm cho Render)
            batch = sentences[i:i+2]
            batch_tasks = [bounded_generate(s, i+j) for j, s in enumerate(batch)]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, tuple) and len(result) == 2:
                    temp_file, subs = result
                    if temp_file and os.path.exists(temp_file):
                        try:
                            audio = AudioSegment.from_file(temp_file)
                            audio_segments.append(audio)
                            
                            # Điều chỉnh thời gian cho subtitles
                            current_time = sum(len(a) for a in audio_segments[:-1])
                            for sub in subs:
                                if isinstance(sub, dict):
                                    sub["start"] += current_time
                                    sub["end"] += current_time
                                    all_subtitles.append(sub)
                            
                            # Xóa file tạm ngay
                            try:
                                os.remove(temp_file)
                            except:
                                pass
                        except Exception as e:
                            print(f"Error processing audio segment: {e}")
        
        if not audio_segments:
            return None, None
        
        # Kết hợp các audio segment với pause
        combined = AudioSegment.empty()
        current_time = 0
        
        for i, audio in enumerate(audio_segments):
            audio = audio.fade_in(50).fade_out(50)
            combined += audio
            current_time += len(audio)
            
            if i < len(audio_segments) - 1:
                combined += AudioSegment.silent(duration=pause)
                current_time += pause
        
        # Xuất file audio
        output_file = os.path.join(output_dir, f"single_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")  # Giảm bitrate
        
        # Tạo file subtitle
        srt_file = self.generate_srt(all_subtitles, output_file)
        
        # Cập nhật progress hoàn thành
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, 
                                   message="Audio generation completed")
        
        return output_file, srt_file
    
    async def process_multi_voice(self, text: str, voices_config: dict, pause: int, 
                                repeat: int, output_format: str = "mp3", task_id: str = None):
        """Process text with multiple voices"""
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = f"outputs/multi_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Phân tích dialogue
        dialogues = []
        current_char = None
        current_text = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            char_match = re.match(r'^(CHAR\d+|NARRATOR):\s*(.+)', line, re.IGNORECASE)
            if char_match:
                if current_char:
                    dialogues.append((current_char, ' '.join(current_text)))
                current_char = char_match.group(1).upper()
                current_text = [char_match.group(2)]
            elif current_char:
                current_text.append(line)
        
        if current_char:
            dialogues.append((current_char, ' '.join(current_text)))
        
        if not dialogues:
            return None, None
        
        # Giới hạn số dialogues
        MAX_DIALOGUES = 20
        if len(dialogues) > MAX_DIALOGUES:
            dialogues = dialogues[:MAX_DIALOGUES]
        
        # Tạo audio cho mỗi dialogue
        audio_segments = []
        all_subtitles = []
        
        for i, (char, dialogue_text) in enumerate(dialogues):
            if task_id and task_manager:
                progress = int((i / len(dialogues)) * 90)
                task_manager.update_task(task_id, progress=progress,
                                       message=f"Processing {char}: {i+1}/{len(dialogues)}")
            
            if char == "CHAR1":
                config = voices_config["char1"]
            elif char == "CHAR2":
                config = voices_config["char2"]
            else:  # NARRATOR or others
                config = voices_config["char1"]
            
            temp_file, subs = await self.generate_speech(
                dialogue_text, 
                config["voice"], 
                config["rate"], 
                config["pitch"], 
                config["volume"]
            )
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append((char, audio))
                
                for sub in subs:
                    sub["speaker"] = char
                    all_subtitles.append(sub)
                
                os.remove(temp_file)
        
        if not audio_segments:
            return None, None
        
        # Kết hợp với repetition
        combined = AudioSegment.empty()
        
        for rep in range(min(repeat, 2)):  # Giới hạn repeat
            if task_id and task_manager:
                task_manager.update_task(task_id, message=f"Combining repetition {rep+1}/{repeat}")
            
            for i, (char, audio) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            
            if rep < min(repeat, 2) - 1:
                combined += AudioSegment.silent(duration=pause * 2)
        
        # Xuất file
        output_file = os.path.join(output_dir, f"multi_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")
        
        # Tạo SRT với speaker labels
        if all_subtitles:
            srt_content = []
            for i, sub in enumerate(all_subtitles, start=1):
                start = timedelta(milliseconds=sub["start"])
                end = timedelta(milliseconds=sub["end"])
                
                start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                
                text = f"{sub['speaker']}: {sub['text']}"
                srt_content.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
            
            srt_file = os.path.join(output_dir, f"multi_voice.srt")
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
        else:
            srt_file = None
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, message="Multi-voice audio generated")
        
        return output_file, srt_file
    
    async def process_qa_dialogue(self, text: str, qa_config: dict, pause_q: int, 
                                pause_a: int, repeat: int, output_format: str = "mp3", task_id: str = None):
        """Process Q&A dialogue"""
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = f"outputs/qa_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Phân tích Q&A
        dialogues = []
        current_speaker = None
        current_text = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            speaker_match = re.match(r'^(Q|A):\s*(.+)', line, re.IGNORECASE)
            if speaker_match:
                if current_speaker:
                    dialogues.append((current_speaker, ' '.join(current_text)))
                current_speaker = speaker_match.group(1).upper()
                current_text = [speaker_match.group(2)]
            elif current_speaker:
                current_text.append(line)
        
        if current_speaker:
            dialogues.append((current_speaker, ' '.join(current_text)))
        
        if not dialogues:
            return None, None
        
        # Giới hạn số dialogues
        MAX_DIALOGUES = 10
        if len(dialogues) > MAX_DIALOGUES:
            dialogues = dialogues[:MAX_DIALOGUES]
        
        # Tạo audio
        audio_segments = []
        all_subtitles = []
        
        for i, (speaker, dialogue_text) in enumerate(dialogues):
            if task_id and task_manager:
                progress = int((i / len(dialogues)) * 90)
                task_manager.update_task(task_id, progress=progress,
                                       message=f"Processing {speaker}: {i+1}/{len(dialogues)}")
            
            if speaker == "Q":
                config = qa_config["question"]
                pause = pause_q
            else:
                config = qa_config["answer"]
                pause = pause_a
            
            temp_file, subs = await self.generate_speech(
                dialogue_text,
                config["voice"],
                config["rate"],
                config["pitch"],
                config["volume"]
            )
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append((speaker, audio, pause))
                
                for sub in subs:
                    sub["speaker"] = speaker
                    all_subtitles.append(sub)
                
                os.remove(temp_file)
        
        if not audio_segments:
            return None, None
        
        # Kết hợp với repetition
        combined = AudioSegment.empty()
        
        for rep in range(min(repeat, 2)):  # Giới hạn repeat
            if task_id and task_manager:
                task_manager.update_task(task_id, message=f"Combining repetition {rep+1}/{repeat}")
            
            for i, (speaker, audio, pause) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            
            if rep < min(repeat, 2) - 1:
                combined += AudioSegment.silent(duration=pause_a * 2)
        
        # Xuất file
        output_file = os.path.join(output_dir, f"qa_dialogue.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")
        
        # Tạo SRT
        if all_subtitles:
            srt_content = []
            for i, sub in enumerate(all_subtitles, start=1):
                start = timedelta(milliseconds=sub["start"])
                end = timedelta(milliseconds=sub["end"])
                
                start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                
                text = f"{sub['speaker']}: {sub['text']}"
                srt_content.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
            
            srt_file = os.path.join(output_dir, f"qa_dialogue.srt")
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
        else:
            srt_file = None
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, message="Q&A audio generated")
        
        return output_file, srt_file
    
    def cleanup_temp_files(self):
        """Dọn dẹp file tạm"""
        try:
            temp_files = glob.glob("temp/*.mp3")
            for file in temp_files:
                try:
                    if os.path.exists(file):
                        file_age = time.time() - os.path.getmtime(file)
                        if file_age > 3600:  # Xóa file cũ hơn 1 giờ
                            os.remove(file)
                except:
                    pass
        except Exception as e:
            print(f"Error cleaning temp files: {e}")
    
    def cleanup_old_outputs(self, hours_old: int = 24):
        """Dọn dẹp outputs cũ"""
        try:
            if os.path.exists("outputs"):
                now = time.time()
                for folder_name in os.listdir("outputs"):
                    folder_path = os.path.join("outputs", folder_name)
                    if os.path.isdir(folder_path):
                        folder_age = now - os.path.getmtime(folder_path)
                        if folder_age > hours_old * 3600:
                            try:
                                shutil.rmtree(folder_path)
                            except:
                                pass
        except Exception as e:
            print(f"Error cleaning old outputs: {e}")

# ==================== LIFESPAN MANAGER ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler thay thế cho on_event"""
    # Startup
    print("Starting up TTS Generator...")
    
    # Initialize TTS processor
    global tts_processor, task_manager
    tts_processor = TTSProcessor()
    task_manager = TaskManager()
    
    # Cleanup old files on startup
    tts_processor.cleanup_temp_files()
    tts_processor.cleanup_old_outputs(24)
    task_manager.cleanup_old_tasks(1)
    
    # Create template file if not exists
    create_template_file()
    
    yield
    
    # Shutdown
    print("Shutting down TTS Generator...")
    tts_processor.cleanup_temp_files()
    if hasattr(task_manager, 'executor'):
        task_manager.executor.shutdown(wait=False)

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(
    title="Professional TTS Generator", 
    version="2.0.0",
    lifespan=lifespan  # Sử dụng lifespan thay vì on_event
)

# Global instances (sẽ được khởi tạo trong lifespan)
tts_processor = None
task_manager = None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "languages": TTSConfig.LANGUAGES,
        "formats": TTSConfig.OUTPUT_FORMATS
    })

@app.get("/api/languages")
async def get_languages():
    """Get all available languages"""
    languages = list(TTSConfig.LANGUAGES.keys())
    return {"languages": languages}

@app.get("/api/voices")
async def get_voices(language: str = None):
    """Get available voices"""
    if language and language in TTSConfig.LANGUAGES:
        voices = TTSConfig.LANGUAGES[language]
    else:
        voices = []
        for lang_voices in TTSConfig.LANGUAGES.values():
            voices.extend(lang_voices)
    
    return {"voices": voices}

@app.post("/api/generate/single")
async def generate_single_voice(
    text: str = Form(...),
    voice_id: str = Form(...),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3")
):
    """Generate single voice TTS with task system"""
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        if not voice_id:
            raise HTTPException(status_code=400, detail="Voice is required")
        
        # Tạo task ID
        task_id = f"single_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "single_voice")
        
        # Lưu settings
        tts_processor.settings["single_voice"] = {
            "voice": voice_id,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "pause": pause
        }
        tts_processor.save_settings()
        
        # Chạy trong background
        async def background_task():
            try:
                audio_file, srt_file = await tts_processor.process_single_voice(
                    text, voice_id, rate, pitch, volume, pause, output_format, task_id
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "message": "Audio generated successfully"
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Failed to generate audio"
                    }
                
                task_manager.update_task(task_id, status="completed", result=result)
                
            except Exception as e:
                task_manager.update_task(task_id, status="failed", 
                                       message=f"Error: {str(e)}")
        
        # Start background task
        asyncio.create_task(background_task())
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Audio generation started. Check task status."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/multi")
async def generate_multi_voice(
    text: str = Form(...),
    char1_language: str = Form(...),
    char1_voice: str = Form(...),
    char1_rate: int = Form(0),
    char1_pitch: int = Form(0),
    char1_volume: int = Form(100),
    char2_language: str = Form(...),
    char2_voice: str = Form(...),
    char2_rate: int = Form(-10),
    char2_pitch: int = Form(0),
    char2_volume: int = Form(100),
    pause: int = Form(500),
    repeat: int = Form(1),
    output_format: str = Form("mp3")
):
    """Generate multi-voice TTS"""
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Tạo task ID
        task_id = f"multi_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "multi_voice")
        
        voices_config = {
            "char1": {
                "language": char1_language,
                "voice": char1_voice,
                "rate": char1_rate,
                "pitch": char1_pitch,
                "volume": char1_volume
            },
            "char2": {
                "language": char2_language,
                "voice": char2_voice,
                "rate": char2_rate,
                "pitch": char2_pitch,
                "volume": char2_volume
            }
        }
        
        # Lưu settings
        tts_processor.settings["multi_voice"] = {
            "char1": voices_config["char1"],
            "char2": voices_config["char2"],
            "pause": pause,
            "repeat": repeat
        }
        tts_processor.save_settings()
        
        # Background task
        async def background_task():
            try:
                audio_file, srt_file = await tts_processor.process_multi_voice(
                    text, voices_config, pause, repeat, output_format, task_id
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "message": "Multi-voice audio generated successfully"
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Failed to generate audio"
                    }
                
                task_manager.update_task(task_id, status="completed", result=result)
                
            except Exception as e:
                task_manager.update_task(task_id, status="failed", 
                                       message=f"Error: {str(e)}")
        
        asyncio.create_task(background_task())
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Multi-voice audio generation started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/qa")
async def generate_qa_dialogue(
    text: str = Form(...),
    question_language: str = Form(...),
    question_voice: str = Form(...),
    question_rate: int = Form(0),
    question_pitch: int = Form(0),
    question_volume: int = Form(100),
    answer_language: str = Form(...),
    answer_voice: str = Form(...),
    answer_rate: int = Form(-10),
    answer_pitch: int = Form(0),
    answer_volume: int = Form(100),
    pause_q: int = Form(200),
    pause_a: int = Form(500),
    repeat: int = Form(2),
    output_format: str = Form("mp3")
):
    """Generate Q&A dialogue TTS"""
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Tạo task ID
        task_id = f"qa_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "qa_dialogue")
        
        qa_config = {
            "question": {
                "language": question_language,
                "voice": question_voice,
                "rate": question_rate,
                "pitch": question_pitch,
                "volume": question_volume
            },
            "answer": {
                "language": answer_language,
                "voice": answer_voice,
                "rate": answer_rate,
                "pitch": answer_pitch,
                "volume": answer_volume
            }
        }
        
        # Lưu settings
        tts_processor.settings["qa_voice"] = {
            "question": qa_config["question"],
            "answer": qa_config["answer"],
            "pause_q": pause_q,
            "pause_a": pause_a,
            "repeat": repeat
        }
        tts_processor.save_settings()
        
        # Background task
        async def background_task():
            try:
                audio_file, srt_file = await tts_processor.process_qa_dialogue(
                    text, qa_config, pause_q, pause_a, repeat, output_format, task_id
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "message": "Q&A dialogue audio generated successfully"
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Failed to generate audio"
                    }
                
                task_manager.update_task(task_id, status="completed", result=result)
                
            except Exception as e:
                task_manager.update_task(task_id, status="failed", 
                                       message=f"Error: {str(e)}")
        
        asyncio.create_task(background_task())
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Q&A audio generation started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "result": task.get("result"),
        "created_at": task["created_at"].isoformat(),
        "updated_at": task["updated_at"].isoformat()
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated files"""
    file_path = None
    
    # Tìm file trong outputs directory
    for root, dirs, files in os.walk("outputs"):
        if filename in files:
            file_path = os.path.join(root, filename)
            break
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/api/settings")
async def get_settings():
    """Get current settings"""
    return tts_processor.settings

@app.post("/api/cleanup")
async def cleanup_files():
    """Cleanup temporary and old files"""
    try:
        # Cleanup tasks
        task_manager.cleanup_old_tasks(1)
        
        # Cleanup files
        tts_processor.cleanup_temp_files()
        tts_processor.cleanup_old_outputs(1)  # 1 hour
        
        # Clear audio cache
        tts_processor.cache_manager.clear_cache()
        
        return {"success": True, "message": "Cleanup completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cleanup/all")
async def cleanup_all():
    """Cleanup all temporary files and cache completely"""
    try:
        # Xóa toàn bộ temp
        if os.path.exists("temp"):
            shutil.rmtree("temp")
            os.makedirs("temp")
        
        # Xóa toàn bộ outputs (giữ lại cấu trúc)
        if os.path.exists("outputs"):
            shutil.rmtree("outputs")
            os.makedirs("outputs")
        
        # Xóa toàn bộ cache
        tts_processor.cache_manager.clear_cache()
        
        # Xóa task cache
        task_manager.tasks.clear()
        
        return {
            "success": True, 
            "message": "All cache and temporary files cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ==================== HTML TEMPLATE CREATION ====================
# Trong hàm create_template_file(), thay đổi phần Multi-Voice tab:
def create_template_file():
    """Create HTML template file"""
    template_content = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
            --success-color: #4cc9f0;
            --light-bg: #f8f9fa;
            --dark-bg: #212529;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .main-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-top: 2rem;
            margin-bottom: 2rem;
            overflow: hidden;
        }
        
        .nav-tabs {
            border-bottom: 2px solid #dee2e6;
            background: var(--light-bg);
        }
        
        .nav-tabs .nav-link {
            border: none;
            border-radius: 0;
            padding: 1rem 2rem;
            font-weight: 600;
            color: #6c757d;
            transition: all 0.3s;
        }
        
        .nav-tabs .nav-link.active {
            background: white;
            color: var(--primary-color);
            border-bottom: 3px solid var(--primary-color);
        }
        
        .tab-content {
            padding: 2rem;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            border: none;
            padding: 0.75rem 2rem;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(67, 97, 238, 0.3);
        }
        
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        
        .loading-spinner {
            width: 50px;
            height: 50px;
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }
        
        .progress-container {
            margin: 1rem 0;
        }
        
        .task-status {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
            display: none;
        }
        
        .output-card {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 10px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        
        .voice-card {
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: #f8f9fa;
        }
        
        .character-tag {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        .char1-tag { background: #e3f2fd; color: #1976d2; }
        .char2-tag { background: #f3e5f5; color: #7b1fa2; }
        .q-tag { background: #e8f5e9; color: #388e3c; }
        .a-tag { background: #fff3e0; color: #f57c00; }
        
        @media (max-width: 768px) {
            .nav-tabs .nav-link {
                padding: 0.75rem 1rem;
                font-size: 0.9rem;
            }
            
            .tab-content {
                padding: 1rem;
            }
            
            .main-container {
                margin: 1rem;
                border-radius: 15px;
            }
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-microphone-alt me-2"></i>
                Professional TTS Generator v2.0
            </a>
            <button class="btn btn-light" onclick="cleanupAll()">
                <i class="fas fa-broom me-2"></i>Clean Cache
            </button>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container main-container">
        <!-- Tabs -->
        <ul class="nav nav-tabs" id="ttsTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="single-tab" data-bs-toggle="tab" data-bs-target="#single">
                    <i class="fas fa-user me-2"></i>Single Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="multi-tab" data-bs-toggle="tab" data-bs-target="#multi">
                    <i class="fas fa-users me-2"></i>Multi-Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="qa-tab" data-bs-toggle="tab" data-bs-target="#qa">
                    <i class="fas fa-comments me-2"></i>Q&A Dialogue
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tasks-tab" data-bs-toggle="tab" data-bs-target="#tasks">
                    <i class="fas fa-tasks me-2"></i>Tasks
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="ttsTabsContent">
            <!-- Single Voice Tab -->
            <div class="tab-pane fade show active" id="single">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Text Content</label>
                            <textarea class="form-control" id="singleText" rows="8" 
                                      placeholder="Enter your text here..."></textarea>
                            <small class="text-muted">Maximum 50 sentences for optimal performance</small>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="mb-3">
                            <label class="form-label">Language</label>
                            <select class="form-select" id="singleLanguage">
                                <option value="">Select Language</option>
                                {% for language in languages %}
                                <option value="{{ language }}">{{ language }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Voice</label>
                            <select class="form-select" id="singleVoice">
                                <option value="">Select Voice</option>
                            </select>
                        </div>
                        
                        <!-- Voice Settings -->
                        <div class="accordion mb-3">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#singleSettings">
                                        <i class="fas fa-sliders-h me-2"></i>Voice Settings
                                    </button>
                                </h2>
                                <div id="singleSettings" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Speed: <span id="singleRateValue">0%</span>
                                            </label>
                                            <input type="range" class="form-range" id="singleRate" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pitch: <span id="singlePitchValue">0Hz</span>
                                            </label>
                                            <input type="range" class="form-range" id="singlePitch" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Volume: <span id="singleVolumeValue">100%</span>
                                            </label>
                                            <input type="range" class="form-range" id="singleVolume" min="50" max="150" value="100">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pause Duration: <span id="singlePauseValue">500ms</span>
                                            </label>
                                            <input type="range" class="form-range" id="singlePause" min="100" max="2000" value="500">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">Output Format</label>
                                            <select class="form-select" id="singleFormat">
                                                {% for format in formats %}
                                                <option value="{{ format }}">{{ format|upper }}</option>
                                                {% endfor %}
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <button class="btn btn-primary w-100" onclick="generateSingle()">
                            <i class="fas fa-play-circle me-2"></i>Generate Audio
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="singleTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar" id="singleProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="singleProgressText">0%</div>
                            </div>
                            <div id="singleTaskMessage"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="singleOutput" style="display: none;">
                    <h5><i class="fas fa-music me-2"></i>Generated Audio</h5>
                    <div class="audio-player" id="singleAudioPlayer"></div>
                    <div class="mt-3">
                        <a href="#" class="btn btn-success me-2" id="singleDownloadAudio">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="singleDownloadSubtitle" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>

            <!-- Multi-Voice Tab -->
            <div class="tab-pane fade" id="multi">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Dialogue Content</label>
                            <textarea class="form-control" id="multiText" rows="8" 
                                      placeholder="CHAR1: Dialogue for character 1&#10;CHAR2: Dialogue for character 2&#10;NARRATOR: Narration text"></textarea>
                            <small class="text-muted">Use CHAR1:, CHAR2:, or NARRATOR: prefixes. Maximum 20 dialogues.</small>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <!-- Character 1 Settings -->
                        <div class="voice-card mb-3">
                            <h6><span class="character-tag char1-tag">CHARACTER 1</span></h6>
                            
                            <div class="mb-3">
                                <label class="form-label">Language</label>
                                <select class="form-select multiLanguage" data-char="1">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Voice</label>
                                <select class="form-select multiVoice" data-char="1">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-char="1" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="rate" data-char="1">0%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-char="1" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-char="1">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-char="1" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-char="1">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Character 2 Settings -->
                        <div class="voice-card mb-3">
                            <h6><span class="character-tag char2-tag">CHARACTER 2</span></h6>
                            
                            <div class="mb-3">
                                <label class="form-label">Language</label>
                                <select class="form-select multiLanguage" data-char="2">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Voice</label>
                                <select class="form-select multiVoice" data-char="2">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-char="2" min="-30" max="30" value="-10">
                                    <small class="d-block text-center"><span data-value="rate" data-char="2">-10%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-char="2" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-char="2">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-char="2" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-char="2">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- General Settings -->
                        <div class="mb-3">
                            <label class="form-label">
                                Pause Between Dialogues: <span id="multiPauseValue">500ms</span>
                            </label>
                            <input type="range" class="form-range" id="multiPause" min="100" max="2000" value="500">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">
                                Repeat Times: <span id="multiRepeatValue">1</span>
                            </label>
                            <input type="range" class="form-range" id="multiRepeat" min="1" max="5" value="1">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Output Format</label>
                            <select class="form-select" id="multiFormat">
                                {% for format in formats %}
                                <option value="{{ format }}">{{ format|upper }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <button class="btn btn-primary w-100" onclick="generateMulti()">
                            <i class="fas fa-users me-2"></i>Generate Multi-Voice Audio
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="multiTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar" id="multiProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="multiProgressText">0%</div>
                            </div>
                            <div id="multiTaskMessage"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="multiOutput" style="display: none;">
                    <h5><i class="fas fa-users me-2"></i>Generated Multi-Voice Audio</h5>
                    <div class="audio-player" id="multiAudioPlayer"></div>
                    <div class="mt-3">
                        <a href="#" class="btn btn-success me-2" id="multiDownloadAudio">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="multiDownloadSubtitle" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>

            <!-- Q&A Dialogue Tab -->
            <div class="tab-pane fade" id="qa">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Q&A Content</label>
                            <textarea class="form-control" id="qaText" rows="8" 
                                      placeholder="Q: Question text&#10;A: Answer text&#10;Q: Next question&#10;A: Next answer"></textarea>
                            <small class="text-muted">Use Q: for questions and A: for answers. Maximum 10 Q&A pairs.</small>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <!-- Question Settings -->
                        <div class="voice-card mb-3">
                            <h6><span class="character-tag q-tag">QUESTION</span></h6>
                            
                            <div class="mb-3">
                                <label class="form-label">Language</label>
                                <select class="form-select qaLanguage" data-type="question">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Voice</label>
                                <select class="form-select qaVoice" data-type="question">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-type="question" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="rate" data-type="question">0%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-type="question" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-type="question">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-type="question" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-type="question">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Answer Settings -->
                        <div class="voice-card mb-3">
                            <h6><span class="character-tag a-tag">ANSWER</span></h6>
                            
                            <div class="mb-3">
                                <label class="form-label">Language</label>
                                <select class="form-select qaLanguage" data-type="answer">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Voice</label>
                                <select class="form-select qaVoice" data-type="answer">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-type="answer" min="-30" max="30" value="-10">
                                    <small class="d-block text-center"><span data-value="rate" data-type="answer">-10%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-type="answer" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-type="answer">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-type="answer" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-type="answer">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Q&A Settings -->
                        <div class="mb-3">
                            <label class="form-label">
                                Pause After Question: <span id="qaPauseQValue">200ms</span>
                            </label>
                            <input type="range" class="form-range" id="qaPauseQ" min="100" max="1000" value="200">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">
                                Pause After Answer: <span id="qaPauseAValue">500ms</span>
                            </label>
                            <input type="range" class="form-range" id="qaPauseA" min="100" max="2000" value="500">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">
                                Repeat Times: <span id="qaRepeatValue">2</span>
                            </label>
                            <input type="range" class="form-range" id="qaRepeat" min="1" max="5" value="2">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Output Format</label>
                            <select class="form-select" id="qaFormat">
                                {% for format in formats %}
                                <option value="{{ format }}">{{ format|upper }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <button class="btn btn-primary w-100" onclick="generateQA()">
                            <i class="fas fa-comments me-2"></i>Generate Q&A Audio
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="qaTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar" id="qaProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="qaProgressText">0%</div>
                            </div>
                            <div id="qaTaskMessage"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="qaOutput" style="display: none;">
                    <h5><i class="fas fa-comments me-2"></i>Generated Q&A Audio</h5>
                    <div class="audio-player" id="qaAudioPlayer"></div>
                    <div class="mt-3">
                        <a href="#" class="btn btn-success me-2" id="qaDownloadAudio">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="qaDownloadSubtitle" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>

            <!-- Tasks Tab -->
            <div class="tab-pane fade" id="tasks">
                <h5><i class="fas fa-tasks me-2"></i>Active Tasks</h5>
                <div id="tasksList">
                    <div class="text-center text-muted py-4">
                        <i class="fas fa-clock fa-2x mb-3"></i>
                        <p>No active tasks</p>
                    </div>
                </div>
                <button class="btn btn-secondary mt-3" onclick="refreshTasks()">
                    <i class="fas fa-sync-alt me-2"></i>Refresh Tasks
                </button>
            </div>
        </div>
    </div>

    <!-- Loading Overlay -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container"></div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Global variables
        let currentTaskId = null;
        let taskCheckInterval = null;
        
        // Initialize
        document.addEventListener('DOMContentLoaded', async function() {
            // Load settings and voices
            await loadSettings();
            await loadVoices();
            
            // Initialize range displays
            initRangeDisplays();
            
            // Auto cleanup on load
            await cleanupOldFiles();
            
            // Initialize multi-voice and Q&A language selectors
            initMultiVoiceSelectors();
            initQASelectors();
        });
        
        // Load settings
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                
                // Apply single voice settings
                if (settings.single_voice) {
                    const sv = settings.single_voice;
                    document.getElementById('singleRate').value = sv.rate;
                    document.getElementById('singlePitch').value = sv.pitch;
                    document.getElementById('singleVolume').value = sv.volume;
                    document.getElementById('singlePause').value = sv.pause;
                    
                    // Trigger updates
                    ['singleRate', 'singlePitch', 'singleVolume', 'singlePause'].forEach(id => {
                        document.getElementById(id).dispatchEvent(new Event('input'));
                    });
                }
                
                // Apply multi-voice settings
                if (settings.multi_voice) {
                    const mv = settings.multi_voice;
                    
                    // Character 1 settings
                    if (mv.char1) {
                        document.querySelector('.multiLanguage[data-char="1"]').value = mv.char1.language || 'Tiếng Việt';
                        document.querySelector('[data-setting="rate"][data-char="1"]').value = mv.char1.rate;
                        document.querySelector('[data-setting="pitch"][data-char="1"]').value = mv.char1.pitch;
                        document.querySelector('[data-setting="volume"][data-char="1"]').value = mv.char1.volume;
                    }
                    
                    // Character 2 settings
                    if (mv.char2) {
                        document.querySelector('.multiLanguage[data-char="2"]').value = mv.char2.language || 'Tiếng Việt';
                        document.querySelector('[data-setting="rate"][data-char="2"]').value = mv.char2.rate;
                        document.querySelector('[data-setting="pitch"][data-char="2"]').value = mv.char2.pitch;
                        document.querySelector('[data-setting="volume"][data-char="2"]').value = mv.char2.volume;
                    }
                    
                    document.getElementById('multiPause').value = mv.pause;
                    document.getElementById('multiRepeat').value = mv.repeat;
                    
                    // Trigger updates
                    document.getElementById('multiPause').dispatchEvent(new Event('input'));
                    document.getElementById('multiRepeat').dispatchEvent(new Event('input'));
                }
                
                // Apply Q&A settings
                if (settings.qa_voice) {
                    const qv = settings.qa_voice;
                    
                    // Question settings
                    if (qv.question) {
                        document.querySelector('.qaLanguage[data-type="question"]').value = qv.question.language || 'Tiếng Việt';
                        document.querySelector('[data-setting="rate"][data-type="question"]').value = qv.question.rate;
                        document.querySelector('[data-setting="pitch"][data-type="question"]').value = qv.question.pitch;
                        document.querySelector('[data-setting="volume"][data-type="question"]').value = qv.question.volume;
                    }
                    
                    // Answer settings
                    if (qv.answer) {
                        document.querySelector('.qaLanguage[data-type="answer"]').value = qv.answer.language || 'Tiếng Việt';
                        document.querySelector('[data-setting="rate"][data-type="answer"]').value = qv.answer.rate;
                        document.querySelector('[data-setting="pitch"][data-type="answer"]').value = qv.answer.pitch;
                        document.querySelector('[data-setting="volume"][data-type="answer"]').value = qv.answer.volume;
                    }
                    
                    document.getElementById('qaPauseQ').value = qv.pause_q;
                    document.getElementById('qaPauseA').value = qv.pause_a;
                    document.getElementById('qaRepeat').value = qv.repeat;
                    
                    // Trigger updates
                    document.getElementById('qaPauseQ').dispatchEvent(new Event('input'));
                    document.getElementById('qaPauseA').dispatchEvent(new Event('input'));
                    document.getElementById('qaRepeat').dispatchEvent(new Event('input'));
                }
                
                // Set default language for all selectors
                const defaultLanguage = 'Tiếng Việt';
                document.getElementById('singleLanguage').value = defaultLanguage;
                document.querySelectorAll('.multiLanguage').forEach(select => select.value = defaultLanguage);
                document.querySelectorAll('.qaLanguage').forEach(select => select.value = defaultLanguage);
                
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        }
        
        // Load voices for single voice
        async function loadVoices() {
            try {
                const language = document.getElementById('singleLanguage').value || 'Tiếng Việt';
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.getElementById('singleVoice');
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Set default Vietnamese voice
                const viVoice = data.voices.find(v => v.name === 'vi-VN-HoaiMyNeural');
                if (viVoice) {
                    voiceSelect.value = viVoice.name;
                }
            } catch (error) {
                console.error('Error loading voices:', error);
            }
        }
        
        // Initialize multi-voice selectors
        async function initMultiVoiceSelectors() {
            // Set up language change handlers for multi-voice
            document.querySelectorAll('.multiLanguage').forEach(select => {
                select.addEventListener('change', async function() {
                    const char = this.dataset.char;
                    const language = this.value;
                    
                    if (language) {
                        await loadMultiVoices(char, language);
                    }
                });
                
                // Load initial voices
                const language = select.value || 'Tiếng Việt';
                loadMultiVoices(select.dataset.char, language);
            });
        }
        
        // Load voices for multi-voice characters
        async function loadMultiVoices(char, language) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.querySelector(`.multiVoice[data-char="${char}"]`);
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Set default voice based on character
                let defaultVoice = 'vi-VN-HoaiMyNeural';
                if (char === '2') {
                    defaultVoice = 'vi-VN-NamMinhNeural';
                }
                
                const defaultVoiceOption = data.voices.find(v => v.name === defaultVoice);
                if (defaultVoiceOption) {
                    voiceSelect.value = defaultVoice;
                }
            } catch (error) {
                console.error(`Error loading voices for character ${char}:`, error);
            }
        }
        
        // Initialize Q&A selectors
        async function initQASelectors() {
            // Set up language change handlers for Q&A
            document.querySelectorAll('.qaLanguage').forEach(select => {
                select.addEventListener('change', async function() {
                    const type = this.dataset.type;
                    const language = this.value;
                    
                    if (language) {
                        await loadQAVoices(type, language);
                    }
                });
                
                // Load initial voices
                const language = select.value || 'Tiếng Việt';
                loadQAVoices(select.dataset.type, language);
            });
        }
        
        // Load voices for Q&A
        async function loadQAVoices(type, language) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.querySelector(`.qaVoice[data-type="${type}"]`);
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Set default voice based on type
                let defaultVoice = 'vi-VN-HoaiMyNeural';
                if (type === 'answer') {
                    defaultVoice = 'vi-VN-NamMinhNeural';
                }
                
                const defaultVoiceOption = data.voices.find(v => v.name === defaultVoice);
                if (defaultVoiceOption) {
                    voiceSelect.value = defaultVoice;
                }
            } catch (error) {
                console.error(`Error loading voices for ${type}:`, error);
            }
        }
        
        // Initialize range displays
        function initRangeDisplays() {
            // Single voice ranges
            const singleRanges = [
                { id: 'singleRate', display: 'singleRateValue', suffix: '%' },
                { id: 'singlePitch', display: 'singlePitchValue', suffix: 'Hz' },
                { id: 'singleVolume', display: 'singleVolumeValue', suffix: '%' },
                { id: 'singlePause', display: 'singlePauseValue', suffix: 'ms' }
            ];
            
            singleRanges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
            
            // Multi-voice ranges
            const multiRanges = [
                { id: 'multiPause', display: 'multiPauseValue', suffix: 'ms' },
                { id: 'multiRepeat', display: 'multiRepeatValue', suffix: 'x' }
            ];
            
            multiRanges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
            
            // Q&A ranges
            const qaRanges = [
                { id: 'qaPauseQ', display: 'qaPauseQValue', suffix: 'ms' },
                { id: 'qaPauseA', display: 'qaPauseAValue', suffix: 'ms' },
                { id: 'qaRepeat', display: 'qaRepeatValue', suffix: 'x' }
            ];
            
            qaRanges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
            
            // Multi-voice character ranges
            document.querySelectorAll('[data-value][data-char]').forEach(span => {
                const char = span.dataset.char;
                const setting = span.dataset.value;
                const input = document.querySelector(`[data-setting="${setting}"][data-char="${char}"]`);
                
                if (input && span) {
                    const suffix = setting === 'rate' ? '%' : setting === 'pitch' ? 'Hz' : '%';
                    span.textContent = input.value + suffix;
                    
                    input.addEventListener('input', () => {
                        span.textContent = input.value + suffix;
                    });
                }
            });
            
            // Q&A ranges
            document.querySelectorAll('[data-value][data-type]').forEach(span => {
                const type = span.dataset.type;
                const setting = span.dataset.value;
                const input = document.querySelector(`[data-setting="${setting}"][data-type="${type}"]`);
                
                if (input && span) {
                    const suffix = setting === 'rate' ? '%' : setting === 'pitch' ? 'Hz' : '%';
                    span.textContent = input.value + suffix;
                    
                    input.addEventListener('input', () => {
                        span.textContent = input.value + suffix;
                    });
                }
            });
        }
        
        // Language change handler for single voice
        document.getElementById('singleLanguage').addEventListener('change', async function() {
            const language = this.value;
            if (language) {
                try {
                    const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                    const data = await response.json();
                    
                    const voiceSelect = document.getElementById('singleVoice');
                    voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                    
                    data.voices.forEach(voice => {
                        const option = document.createElement('option');
                        option.value = voice.name;
                        option.textContent = `${voice.display} (${voice.gender})`;
                        voiceSelect.appendChild(option);
                    });
                    
                    // Auto-select first voice
                    if (data.voices.length > 0) {
                        voiceSelect.value = data.voices[0].name;
                    }
                } catch (error) {
                    console.error('Error loading voices:', error);
                    showToast('Error loading voices for selected language', 'error');
                }
            }
        });
        
        // Generate single voice audio
        async function generateSingle() {
            const text = document.getElementById('singleText').value.trim();
            const voice = document.getElementById('singleVoice').value;
            const language = document.getElementById('singleLanguage').value;
            
            if (!text) {
                showToast('Please enter text', 'error');
                return;
            }
            
            if (!language) {
                showToast('Please select a language', 'error');
                return;
            }
            
            if (!voice) {
                showToast('Please select a voice', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', voice);
            formData.append('rate', document.getElementById('singleRate').value);
            formData.append('pitch', document.getElementById('singlePitch').value);
            formData.append('volume', document.getElementById('singleVolume').value);
            formData.append('pause', document.getElementById('singlePause').value);
            formData.append('output_format', document.getElementById('singleFormat').value);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('single', result.task_id);
                    showToast('Audio generation started');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        }
        
        // Generate multi-voice audio
        async function generateMulti() {
            const text = document.getElementById('multiText').value.trim();
            
            if (!text) {
                showToast('Please enter dialogue text', 'error');
                return;
            }
            
            // Get character 1 settings
            const char1Language = document.querySelector('.multiLanguage[data-char="1"]').value;
            const char1Voice = document.querySelector('.multiVoice[data-char="1"]').value;
            
            if (!char1Language) {
                showToast('Please select language for Character 1', 'error');
                return;
            }
            
            if (!char1Voice) {
                showToast('Please select voice for Character 1', 'error');
                return;
            }
            
            // Get character 2 settings
            const char2Language = document.querySelector('.multiLanguage[data-char="2"]').value;
            const char2Voice = document.querySelector('.multiVoice[data-char="2"]').value;
            
            if (!char2Language) {
                showToast('Please select language for Character 2', 'error');
                return;
            }
            
            if (!char2Voice) {
                showToast('Please select voice for Character 2', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('char1_language', char1Language);
            formData.append('char1_voice', char1Voice);
            formData.append('char1_rate', document.querySelector('[data-setting="rate"][data-char="1"]').value);
            formData.append('char1_pitch', document.querySelector('[data-setting="pitch"][data-char="1"]').value);
            formData.append('char1_volume', document.querySelector('[data-setting="volume"][data-char="1"]').value);
            formData.append('char2_language', char2Language);
            formData.append('char2_voice', char2Voice);
            formData.append('char2_rate', document.querySelector('[data-setting="rate"][data-char="2"]').value);
            formData.append('char2_pitch', document.querySelector('[data-setting="pitch"][data-char="2"]').value);
            formData.append('char2_volume', document.querySelector('[data-setting="volume"][data-char="2"]').value);
            formData.append('pause', document.getElementById('multiPause').value);
            formData.append('repeat', document.getElementById('multiRepeat').value);
            formData.append('output_format', document.getElementById('multiFormat').value);
            
            try {
                const response = await fetch('/api/generate/multi', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('multi', result.task_id);
                    showToast('Multi-voice audio generation started');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        }
        
        // Generate Q&A audio
        async function generateQA() {
            const text = document.getElementById('qaText').value.trim();
            
            if (!text) {
                showToast('Please enter Q&A text', 'error');
                return;
            }
            
            // Get question settings
            const questionLanguage = document.querySelector('.qaLanguage[data-type="question"]').value;
            const questionVoice = document.querySelector('.qaVoice[data-type="question"]').value;
            
            if (!questionLanguage) {
                showToast('Please select language for Questions', 'error');
                return;
            }
            
            if (!questionVoice) {
                showToast('Please select voice for Questions', 'error');
                return;
            }
            
            // Get answer settings
            const answerLanguage = document.querySelector('.qaLanguage[data-type="answer"]').value;
            const answerVoice = document.querySelector('.qaVoice[data-type="answer"]').value;
            
            if (!answerLanguage) {
                showToast('Please select language for Answers', 'error');
                return;
            }
            
            if (!answerVoice) {
                showToast('Please select voice for Answers', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('question_language', questionLanguage);
            formData.append('question_voice', questionVoice);
            formData.append('question_rate', document.querySelector('[data-setting="rate"][data-type="question"]').value);
            formData.append('question_pitch', document.querySelector('[data-setting="pitch"][data-type="question"]').value);
            formData.append('question_volume', document.querySelector('[data-setting="volume"][data-type="question"]').value);
            formData.append('answer_language', answerLanguage);
            formData.append('answer_voice', answerVoice);
            formData.append('answer_rate', document.querySelector('[data-setting="rate"][data-type="answer"]').value);
            formData.append('answer_pitch', document.querySelector('[data-setting="pitch"][data-type="answer"]').value);
            formData.append('answer_volume', document.querySelector('[data-setting="volume"][data-type="answer"]').value);
            formData.append('pause_q', document.getElementById('qaPauseQ').value);
            formData.append('pause_a', document.getElementById('qaPauseA').value);
            formData.append('repeat', document.getElementById('qaRepeat').value);
            formData.append('output_format', document.getElementById('qaFormat').value);
            
            try {
                const response = await fetch('/api/generate/qa', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('qa', result.task_id);
                    showToast('Q&A audio generation started');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        }
        
        // Show task status and poll for updates
        function showTaskStatus(type, taskId) {
            const statusDiv = document.getElementById(`${type}TaskStatus`);
            const progressBar = document.getElementById(`${type}ProgressBar`);
            const progressText = document.getElementById(`${type}ProgressText`);
            const taskMessage = document.getElementById(`${type}TaskMessage`);
            
            statusDiv.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = '0%';
            taskMessage.textContent = 'Starting...';
            
            // Clear existing interval
            if (taskCheckInterval) {
                clearInterval(taskCheckInterval);
            }
            
            // Poll for task updates
            taskCheckInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/task/${taskId}`);
                    const task = await response.json();
                    
                    progressBar.style.width = `${task.progress}%`;
                    progressText.textContent = `${task.progress}%`;
                    taskMessage.textContent = task.message;
                    
                    if (task.status === 'completed') {
                        clearInterval(taskCheckInterval);
                        
                        if (task.result && task.result.success) {
                            showToast(task.result.message);
                            
                            // Show output
                            showOutput(type, task.result);
                        }
                        
                        // Hide status after 5 seconds
                        setTimeout(() => {
                            statusDiv.style.display = 'none';
                        }, 5000);
                    } else if (task.status === 'failed') {
                        clearInterval(taskCheckInterval);
                        showToast(task.message, 'error');
                        
                        // Hide status after 3 seconds
                        setTimeout(() => {
                            statusDiv.style.display = 'none';
                        }, 3000);
                    }
                } catch (error) {
                    console.error('Error checking task status:', error);
                }
            }, 2000); // Poll every 2 seconds
        }
        
        // Show output based on type
        function showOutput(type, result) {
            const outputDiv = document.getElementById(`${type}Output`);
            const audioPlayer = document.getElementById(`${type}AudioPlayer`);
            const downloadAudio = document.getElementById(`${type}DownloadAudio`);
            const downloadSubtitle = document.getElementById(`${type}DownloadSubtitle`);
            
            // Add timestamp to avoid cache
            const timestamp = new Date().getTime();
            const audioUrl = `${result.audio_url}?t=${timestamp}`;
            
            audioPlayer.innerHTML = `
                <audio controls class="w-100">
                    <source src="${audioUrl}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
            `;
            
            downloadAudio.href = result.audio_url;
            downloadAudio.download = `tts_${type}_audio.mp3`;
            
            if (result.srt_url) {
                downloadSubtitle.href = result.srt_url;
                downloadSubtitle.download = `tts_${type}_subtitle.srt`;
                downloadSubtitle.style.display = 'inline-block';
            } else {
                downloadSubtitle.style.display = 'none';
            }
            
            outputDiv.style.display = 'block';
            
            // Scroll to output
            outputDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Cleanup old files
        async function cleanupOldFiles() {
            try {
                await fetch('/api/cleanup', { method: 'POST' });
            } catch (error) {
                console.error('Error cleaning up:', error);
            }
        }
        
        // Cleanup all cache
        async function cleanupAll() {
            if (confirm('Are you sure you want to clear all cache and temporary files?')) {
                showLoading();
                try {
                    const response = await fetch('/api/cleanup/all', { method: 'POST' });
                    const result = await response.json();
                    
                    if (result.success) {
                        showToast('All cache cleared successfully');
                    } else {
                        showToast(result.message, 'error');
                    }
                } catch (error) {
                    console.error('Error cleaning up:', error);
                    showToast('Error clearing cache', 'error');
                } finally {
                    hideLoading();
                }
            }
        }
        
        // Refresh tasks list
        async function refreshTasks() {
            try {
                const tasksList = document.getElementById('tasksList');
                tasksList.innerHTML = '<div class="text-center"><div class="spinner-border"></div></div>';
                
                // In a real app, you would fetch tasks from an API
                setTimeout(() => {
                    tasksList.innerHTML = `
                        <div class="text-center text-muted py-4">
                            <i class="fas fa-clock fa-2x mb-3"></i>
                            <p>No active tasks</p>
                        </div>
                    `;
                    showToast('Task list refreshed');
                }, 1000);
            } catch (error) {
                console.error('Error refreshing tasks:', error);
            }
        }
        
        // Utility functions
        function showLoading() {
            document.getElementById('loadingOverlay').style.display = 'flex';
        }
        
        function hideLoading() {
            document.getElementById('loadingOverlay').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const toastContainer = document.querySelector('.toast-container');
            const toastId = 'toast-' + Date.now();
            
            const colorClass = type === 'error' ? 'danger' : 
                             type === 'warning' ? 'warning' : 'success';
            const icon = type === 'error' ? 'fa-exclamation-circle' : 
                        type === 'warning' ? 'fa-exclamation-triangle' : 'fa-check-circle';
            
            const toastHtml = `
                <div id="${toastId}" class="toast align-items-center text-white bg-${colorClass} border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas ${icon} me-2"></i>
                            ${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>
            `;
            
            toastContainer.insertAdjacentHTML('beforeend', toastHtml);
            const toastElement = document.getElementById(toastId);
            const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
            toast.show();
            
            toastElement.addEventListener('hidden.bs.toast', () => {
                toastElement.remove();
            });
        }
    </script>
</body>
</html>
"""
    
    template_path = "templates/index.html"
    os.makedirs("templates", exist_ok=True)
    
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print(f"Template created at: {template_path}")

# ==================== MAIN ENTRY POINT ====================
def create_requirements_txt():
    """Create requirements.txt file"""
    requirements = """fastapi==0.104.1
uvicorn[standard]==0.24.0
edge-tts==6.1.9
pydub==0.25.1
webvtt-py==0.4.6
natsort==8.4.0
python-multipart==0.0.6
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    print("requirements.txt created")

def create_runtime_txt():
    """Create runtime.txt for Python version"""
    runtime = "python-3.11.0"
    
    with open("runtime.txt", "w") as f:
        f.write(runtime)
    
    print("runtime.txt created")

def create_gunicorn_conf():
    """Create gunicorn configuration for Render"""
    gunicorn_conf = """# gunicorn_config.py
import multiprocessing

bind = "0.0.0.0:10000"
workers = 1  # Render sets WEB_CONCURRENCY
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
"""
    
    with open("gunicorn_config.py", "w") as f:
        f.write(gunicorn_conf)
    
    print("gunicorn_config.py created")

# ==================== RUN APPLICATION ====================
if __name__ == "__main__":
    # Create necessary files for deployment
    create_requirements_txt()
    create_runtime_txt()
    create_gunicorn_conf()
    
    # Get port from environment variable (for Render)
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("PROFESSIONAL TTS GENERATOR v2.0")
    print("=" * 60)
    print(f"Server starting on port: {port}")
    print(f"Open http://localhost:{port} in your browser")
    print("Optimized for Render deployment")
    print("=" * 60)
    
    # Run with uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False  # Disable reload for production
    )
