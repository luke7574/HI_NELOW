import whisper
import pyaudio
import wave
import time
import os
import keyboard
# from pynput import keyboard as kb
from nelow import process_command, create_logged_in_session, load_region_value_map 
from dotenv import load_dotenv
    
load_dotenv()


TRIGGER_KEYWORD = "하이"
AUDIO_FILE = "temp.wav"
RECORD_SECONDS = 3  # 감지 주기
RATE = 16000
CHUNK = 1024

#명령어 STT 설정
SILENCE_THRESHOLD = 500  # 무음 감지 임계값 (0~32768)
SILENCE_DURATION = 3  # 무음이 몇 초 이상 지속되면 녹음 종료
MAX_RECORD_SECONDS = 15  # 최대 녹음 시간

# Whisper 모델 로드
model = whisper.load_model("small")  # "tiny", "base", "small", "medium", "large"

# 오디오 녹음 함수
def record_audio(filename=AUDIO_FILE, record_seconds=RECORD_SECONDS):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("🎤 음성 감지 중...")

    frames = []
    for _ in range(0, int(RATE / CHUNK * record_seconds)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(filename, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

# STT로 텍스트 추출
def transcribe_audio(filename=AUDIO_FILE):
    result = model.transcribe(filename, language="ko")
    return result['text'].strip()

# 트리거 감지 루프
def listen_for_trigger():
    print("🟢 트리거 키워드 대기 중... (중단하려면 Ctrl+C)")
    while True:
        record_audio()
        text = transcribe_audio()
        print(f"🎧 인식 결과: '{text}'")

        if TRIGGER_KEYWORD in text:
            print("🚨 트리거 키워드 감지됨!")
            return

def record_until_silence(filename=AUDIO_FILE):
    print("🎙️ 명령어를 말해주세요. (묵음 3초 → 자동 종료)")

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []
    silence_count = 0
    max_frames = int(RATE / CHUNK * MAX_RECORD_SECONDS)

    for _ in range(max_frames):
        data = stream.read(CHUNK)
        frames.append(data)

        # 무음인지 체크
        audio_data = wave.struct.unpack("%dh" % (len(data) // 2), data)
        volume = max(audio_data)

        if volume < SILENCE_THRESHOLD:
            silence_count += 1
        else:
            silence_count = 0

        if silence_count > int(SILENCE_DURATION * (RATE / CHUNK)):
            print("🔇 묵음 감지 → 녹음 종료")
            break

    stream.stop_stream()
    stream.close()
    p.terminate()

    # WAV 저장
    wf = wave.open(filename, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

def transcribe_audio(filename=AUDIO_FILE):
    result = model.transcribe(filename, language="ko")
    text = result['text'].strip()
    print(f"📝 STT 인식: '{text}'")
    return text

# 메인 실행
if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = "https://kr.neverlosewater.com/"
    region_value_map = load_region_value_map()

    listen_for_trigger()  # 트리거 키워드 감지될 때까지 대기
    playwright, browser, context, page = create_logged_in_session(base_url)

    try:
        print("🔵 [스페이스바]를 눌러 명령어를 말하세요. [ESC]를 누르면 종료됩니다.")
        while True:
            if keyboard.is_pressed("esc"):
                print("🚪 ESC 키 감지 → 종료합니다.")
                break
            if keyboard.is_pressed("space"):
                time.sleep(0.2)  # 너무 빠른 중복 입력 방지
                record_until_silence()
                user_input = transcribe_audio()
                if user_input:
                    process_command(page, base_url, user_input, api_key, region_value_map)
                print("⏳ 다시 대기 중... [스페이스바]를 눌러 명령 시작")
            time.sleep(0.1)
    finally:
        browser.close()
        playwright.stop()
        print("🧹 세션 종료")
