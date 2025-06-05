import whisper
import pyaudio
import wave
import time
import os
from nelow import process_command, create_logged_in_session, load_region_value_map 
from dotenv import load_dotenv
    
load_dotenv()


TRIGGER_KEYWORD = "하이"
AUDIO_FILE = "temp.wav"
RECORD_SECONDS = 3  # 감지 주기
RATE = 16000
CHUNK = 1024

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

# 메인 실행
if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = "https://kr.neverlosewater.com/"
    region_value_map = load_region_value_map()

    listen_for_trigger()  # 트리거 키워드 감지될 때까지 대기
    playwright, browser, context, page = create_logged_in_session(base_url)

    try:
        while True:
            # listen_for_trigger()  # 트리거 키워드 감지될 때까지 대기
            user_input = input("📥 명령어 입력 (exit 입력 시 종료): ")
            if user_input.lower() in ["exit", "quit"]:
                break
            process_command(page, base_url, user_input, api_key, region_value_map)
    finally:
        browser.close()
        playwright.stop()
        print("🧹 세션 종료")
