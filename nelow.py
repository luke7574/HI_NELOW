from openai import OpenAI
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import re
import os
import json

# 🔐 환경변수에서 API 키 불러오기
load_dotenv()

# 🧾 로그인 계정 정보
LOGIN_ID = os.getenv('ID')
LOGIN_PW = os.getenv('PASSWORD')

# 1. 페이지 정의
dom_elements = [
    {"name": "누수음 듣기", "href": "/leak-master", "selector": 'a[href="/leak-master"]'},
    {"name": "누수음 로거", "href": "/water-leak-logger", "selector": 'a[href="/water-leak-logger"]'},
    {"name": "누수음 모니터링", "href": "/leak-monitoring", "selector": 'a[href="/leak-monitoring"]'},
]

# 지역 매핑 불러오기
def load_region_value_map():
    with open("region_value_map.json", "r", encoding="utf-8") as f:
        return json.load(f)

# 프롬프트 생성
def build_prompt(user_input, dom_elements):
    dom_list = "\n".join([
        f"{i+1}. '{el['name']}' → <a href=\"{el['href']}\"> (selector: {el['selector']})"
        for i, el in enumerate(dom_elements)
    ])
    index_hint = """
[참고사항]
- "첫번째" → ROOM_INDEX: 1
- "두번째" → ROOM_INDEX: 2
- "세번째" → ROOM_INDEX: 3
- "네번째" → ROOM_INDEX: 4
- "다섯번째" → ROOM_INDEX: 5
- "여섯번째" → ROOM_INDEX: 6
- "일곱번째" → ROOM_INDEX: 7
- "여덟번째" → ROOM_INDEX: 8
- "아홉번째" → ROOM_INDEX: 9
- "열번째" → ROOM_INDEX: 10
- "열한번째" → ROOM_INDEX: 11
- "열두번째" → ROOM_INDEX: 12
- "열세번째" → ROOM_INDEX: 13
- "열네번째" → ROOM_INDEX: 14
- "열다섯번째" → ROOM_INDEX: 15
- "열여섯번째" → ROOM_INDEX: 16
- "열일곱번째" → ROOM_INDEX: 17
- "열여덟번째" → ROOM_INDEX: 18
- "열아홉번째" → ROOM_INDEX: 19
- "스무번째" → ROOM_INDEX: 20

(한국어 순서 표현(예: '열다섯번째')은 해당 숫자로 변환하여 ROOM_INDEX로 추출하세요.)
""".strip()

    return f'''
[사용자 명령]
"{user_input}"

[웹 요소 목록]
{dom_list}

{index_hint}

당신은 사용자 명령을 분석하여 적절한 selector와 지역 이름 또는 작업방 순번을 추론해야 합니다.
출력 형식:
REGION: 지역명\nACTION: click("selector")\nHREF: /"href"\nROOM_INDEX: n (선택적)
'''.strip()

# LLM 호출
def query_llm(prompt, api_key):
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# LLM 응답 파싱
def extract_selector_and_region(response):
    selector_match = re.search(r'click\("(.+?)"\)', response)
    region_match = re.search(r'REGION:\s*(\S+)', response)
    href_match = re.search(r'HREF:\s*(\S+)', response)
    index_match = re.search(r'ROOM_INDEX:\s*(\d+)', response)

    selector = selector_match.group(1) if selector_match else None
    region = region_match.group(1) if region_match else None
    href = href_match.group(1) if href_match else None
    index = int(index_match.group(1)) if index_match else None
    return selector, region, href, index

# href 찾기
def selector_to_href(selector):
    normalized = selector.strip().replace('"', "'")
    for el in dom_elements:
        if el["selector"].strip().replace('"', "'") == normalized:
            return el["href"]
    return None

# 로그인 및 세션 유지
def create_logged_in_session(base_url):
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])
    context = browser.new_context(no_viewport=True)
    page = context.new_page()
    page.goto(base_url)
    page.fill('input[type="text"]', LOGIN_ID)
    page.fill('input[type="password"]', LOGIN_PW)
    page.press('input[type="password"]', 'Enter')
    page.wait_for_selector("#sidebar", timeout=10000)
    print("✅ 로그인 성공")
    return playwright, browser, context, page

# 지역 선택 함수
def ensure_region_selected(page, base_url, region_value):
    try:
        select_element = page.query_selector("select.item-select")
        if select_element and select_element.is_enabled():
            page.select_option("select.item-select", value=region_value)
            print("✅ 지역 선택 완료")
            return True

        print("⚠️ 지역 선택 요소 비활성화됨 → 초기화 시도")
        page.goto(base_url)
        page.wait_for_selector("select.item-select", timeout=5000)
        select_element = page.query_selector("select.item-select")
        if select_element and select_element.is_enabled():
            page.select_option("select.item-select", value=region_value)
            print("✅ 초기화 후 지역 재선택 완료")
            return True
        else:
            print("❌ 초기화 후에도 지역 선택 실패")
            return False
    except Exception as e:
        print(f"❌ 지역 선택 중 예외 발생: {e}")
        return False

# 누수음 듣기/로거 작업방 진입 함수
def enter_leak_room(page, room_keyword=None, room_index=None):
    # li_elements = page.query_selector_all("li")
    li_elements = page.query_selector_all("ul.ns-list > li")
    print(li_elements)
    if room_index is not None:
        try:
            li = li_elements[room_index]
            # print(f"il : {li}")
            name_el = li.query_selector("p")
            # print(f"name_el : {name_el}")
            number_el = li.query_selector(".num")
            # print(f"number_el : {number_el}")
            room_name = name_el.inner_text().strip() if name_el else "Unknown"
            print(f"room_name : {room_name}")
            chevron_button = li.query_selector('img[src*="chevron"]')
            if chevron_button:
                chevron_button.click()
                page.wait_for_timeout(1000)
                print(f"✅ 인덱스로 작업방 진입: '{room_name}'")
                return
        except Exception as e:
            print(f"❌ 인덱스로 작업방 진입 실패: {e}")
            return

    for li in li_elements:
        try:
            name_el = li.query_selector("p")
            number_el = li.query_selector(".num")
            if not name_el or not number_el:
                continue

            room_name = name_el.inner_text().strip()
            room_number = number_el.inner_text().strip()

            if room_keyword in room_name or room_keyword == room_number:
                chevron_button = li.query_selector('img[src*="chevron"]')
                if chevron_button:
                    chevron_button.click()
                    page.wait_for_timeout(1000)
                    print(f"✅ 작업방 진입: '{room_name}' ({room_number})")
                    return
                else:
                    print(f"⚠️ 버튼을 찾지 못했습니다: '{room_name}' ({room_number})")
        except Exception:
            continue

    print("❌ 해당 키워드와 일치하는 작업방을 찾을 수 없습니다.")

# 누수음 모니터링 작업방 진입 함수
def enter_monitoring_room(page, room_keyword=None, room_index=None):
    try:
        page.wait_for_selector("ul.monitoring-list > li.col", timeout=5000)
    except:
        print("❌ 작업방 목록이 로딩되지 않았습니다.")
        return

    li_elements = page.query_selector_all("ul.monitoring-list > li.col")
    print(f"🔍 총 작업방 수: {len(li_elements)}")
    if room_index is not None:
        try:
            li = li_elements[int(room_index)-1] # 모니터링은 index-1을 해줘야 알맞음 (NELOW UI상)
            name_el = li.query_selector("h3")
            room_name = name_el.inner_text().strip() if name_el else "Unknown"
            chevron_button = li.query_selector('img[src*="chevron"]')
            if chevron_button:
                chevron_button.click()
                page.wait_for_timeout(1000)
                print(f"✅ 인덱스로 모니터링 작업방 진입: '{room_name}'")
                return
        except Exception as e:
            print(f"❌ 인덱스로 작업방 진입 실패: {e}")
            return

    for li in li_elements:
        try:
            name_el = li.query_selector("h3")
            if not name_el:
                continue
            room_name = name_el.inner_text().strip()
            if room_keyword in room_name:
                chevron_button = li.query_selector('img[src*="chevron"]')
                if chevron_button:
                    chevron_button.click()
                    page.wait_for_timeout(1000)
                    print(f"✅ 모니터링 작업방 진입: '{room_name}'")
                    return
        except Exception:
            continue
    print("❌ 일치하는 모니터링 작업방을 찾을 수 없습니다.")

#-----------------------------------------------------------------------------------------------------------
# 강도값 정렬 상태 확인
def get_strength_sort_state(page):
    th = page.query_selector("th:has(span:text('Strength'))")
    if not th:
        return "unknown"

    aria_sort = th.get_attribute("aria-sort") or "none"
    class_attr = th.get_attribute("class") or ""

    # 명확한 상태 구분
    if "sorting-asc" in class_attr:
        return "asc"
    elif "sorting-desc" in class_attr:
        return "desc"
    elif aria_sort == "descending" and "sorting" not in class_attr:
        return "none"  # 기본 상태
    else:
        return "unknown"

# 강도값으로 정렬하기
def sort_strength_to_target_order(page, target="asc"):
    state = get_strength_sort_state(page)
    print(f"📊 현재 정렬 상태: {state}")

    click_count = 0
    if target == "asc":
        if state == "none":
            click_count = 1
        elif state == "desc":
            click_count = 2
        elif state == "asc":
            print("✅ 이미 오름차순입니다.")
            return
    elif target == "desc":
        if state == "none":
            click_count = 2
        elif state == "asc":
            click_count = 1
        elif state == "desc":
            print("✅ 이미 내림차순입니다.")
            return

    button = page.query_selector("th:has(span:text('Strength')) button")
    if not button:
        print("❌ 정렬 버튼을 찾을 수 없습니다.")
        return

    for _ in range(click_count):
        button.click()
        page.wait_for_timeout(500)

    print(f"✅ '{target}' 정렬 상태로 변경 완료 (클릭 {click_count}회)")
#-----------------------------------------------------------------------------------------------------------
# 주파수값 정렬 상태 확인
def get_frequency_sort_state(page):
    th = page.query_selector("th:has(span:text('Max Frequency'))") or \
         page.query_selector("th:has(span:text('Max(Hz)'))")
    if not th:
        return "unknown"

    aria_sort = th.get_attribute("aria-sort") or "none"
    class_attr = th.get_attribute("class") or ""

    # 명확한 상태 구분
    if "sorting-asc" in class_attr:
        return "asc"
    elif "sorting-desc" in class_attr:
        return "desc"
    elif aria_sort == "descending" and "sorting" not in class_attr:
        return "none"  # 기본 상태
    else:
        return "unknown"

# 주파수값으로 정렬하기
def sort_frequency_to_target_order(page, target="asc"):
    state = get_frequency_sort_state(page)
    print(f"📊 현재 정렬 상태: {state}")

    click_count = 0
    if target == "asc":
        if state == "none":
            click_count = 1
        elif state == "desc":
            click_count = 2
        elif state == "asc":
            print("✅ 이미 오름차순입니다.")
            return
    elif target == "desc":
        if state == "none":
            click_count = 2
        elif state == "asc":
            click_count = 1
        elif state == "desc":
            print("✅ 이미 내림차순입니다.")
            return

    button = page.query_selector("th:has(span:text('Max Frequency')) button") or \
             page.query_selector("th:has(span:text('Max(Hz)')) button")
    if not button:
        print("❌ 정렬 버튼을 찾을 수 없습니다.")
        return

    for _ in range(click_count):
        button.click()
        page.wait_for_timeout(500)

    print(f"✅ '{target}' 정렬 상태로 변경 완료 (클릭 {click_count}회)")
#-----------------------------------------------------------------------------------------------------------
# 누수음 실행하기
def play_leak_sound_by_index(page, sound_index: int):
    try:
        # 누수음 목록 공통 selector
        selector = "#vgt-table > tbody > tr"
        rows = page.query_selector_all(selector)

        if not rows:
            print("❌ 누수음 목록을 찾을 수 없습니다.")
            return

        if sound_index < 1 or sound_index > len(rows):
            print(f"❌ 유효하지 않은 인덱스입니다: {sound_index} (총 {len(rows)}개)")
            return

        # 대상 누수음 항목 클릭
        target_row = rows[sound_index - 1]
        target_row.click()
        print(f"🔊 {sound_index}번째 누수음 항목 클릭 완료")

        # 페이지 전환 또는 오디오 요소 로딩 대기
        page.wait_for_timeout(1000)  # 필요시 조정

        # 오디오 플레이어 재생
        audio_selector = "#waveform > audio"
        audio = page.query_selector(audio_selector)
        if audio:
            page.evaluate("audio => audio.play()", audio)
            print("▶️ 재생 시작 완료")
        else:
            print("❌ 재생 오디오 요소를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
#-----------------------------------------------------------------------------------------------------------
# 명령 실행
def process_command(page, base_url, user_input, api_key, region_value_map):
    prompt = build_prompt(user_input, dom_elements)
    response = query_llm(prompt, api_key)
    print(response)

    selector, region, href, index = extract_selector_and_region(response)
    print(f"🧾 분석 결과 → selector: {selector}, region: {region}, href: {href}, index: {index}")

    # ✅ fallback: 작업방 이름으로 수동 진입 시도
    if "작업방" in user_input:
        keyword = (
            user_input.replace("작업방", "")
            .replace("들어가줘", "")
            .replace("진입", "")
            .strip()
        )
        if "/leak-monitoring" in page.url:
            enter_monitoring_room(page, room_keyword=keyword)
        else:
            enter_leak_room(page, room_keyword=keyword)
        return

    # ✅ 누수음 재생 시도
    if "재생" in user_input or "들려줘" in user_input:
        play_leak_sound_by_index(page, sound_index=index)
        return

    # ✅ 작업방 인덱스로 진입 시도
    if index is not None:
        if "/leak-monitoring" in page.url:
            enter_monitoring_room(page, room_index=index)
        else:
            enter_leak_room(page, room_index=index)
        return

    # 강도값 정렬하기
    if "강도값" in user_input and "정렬" in user_input:
        if "오름차순" in user_input:
            sort_strength_to_target_order(page, target="asc")
            return
        else:
            sort_strength_to_target_order(page, target="desc")
            return

    # 주파수값 정렬하기
    if "주파수값" in user_input and "정렬" in user_input:
        if "오름차순" in user_input:
            sort_frequency_to_target_order(page, target="asc")
            return
        else:
            sort_frequency_to_target_order(page, target="desc")
            return

    # ✅ 페이지 탐색
    if not selector and not region and not href:
        for el in dom_elements:
            if el["name"].replace(" ", "") in user_input.replace(" ", ""):
                href = el["href"]
                page.goto(base_url.rstrip("/") + href)
                print(f"↩️ '{el['name']}' 페이지로 이동합니다.")
                return
        print("❌ selector 또는 지역명을 추출할 수 없습니다.")
        return

    if not href and selector:
        href = selector_to_href(selector)
        print(f"🔗 selector_to_href 변환 결과: {href}")
        if not href:
            print("❌ href 경로를 찾을 수 없습니다.")
            return

    region_value = None
    if region:
        region_value = region_value_map.get(region)
        print(f"🗺️ region_value = {region_value}")
        if not region_value:
            print(f"❌ 알 수 없는 지역명: {region} (region_value_map에 없음)")
            return

    if region_value and not ensure_region_selected(page, base_url, region_value):
        return

    try:
        full_url = base_url.rstrip("/") + href
        page.goto(full_url)
        page.evaluate("window.moveTo(0, 0); window.resizeTo(screen.availWidth, screen.availHeight)")
        print(f"➡️ 페이지 이동 완료: {full_url}")
    except Exception as e:
        print(f"⚠️ 페이지 이동 실패: {e}")


# 메인 실행
if __name__ == "__main__":
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = "https://kr.neverlosewater.com/"
    region_value_map = load_region_value_map()

    playwright, browser, context, page = create_logged_in_session(base_url)

    try:
        while True:
            user_input = input("📥 명령어 입력 (exit 입력 시 종료): ")
            if user_input.lower() in ["exit", "quit"]:
                break
            process_command(page, base_url, user_input, api_key, region_value_map)
    finally:
        browser.close()
        playwright.stop()
        print("🧹 세션 종료")
