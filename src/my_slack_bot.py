from selenium import webdriver
from selenium.webdriver.common.by import By
from timezonefinder import TimezoneFinder
from datetime import date, timedelta
from dotenv import load_dotenv

import requests
import json
import googlemaps
import textwrap
import schedule
import time
import os


############## Define Your API KEY ##############
load_dotenv()
GMAP_API_KEY = os.environ.get('GMAP_API_KEY')
SLACK_URL = os.environ.get('SLACK_URL')


############## 현지 위/경도 및 표준시간대 반환 ##############
def get_time_zone(searching_zone):
    
    gmaps = googlemaps.Client(key=GMAP_API_KEY)

    # searching_zone = input("Time Zone 식별명을 알고 싶은 도시를 입력해주세요:")
    zone = gmaps.geocode(searching_zone)

    lat = zone[0]['geometry']['location']['lat']
    lng = zone[0]['geometry']['location']['lng']

    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lng=lng, lat=lat)
    return lat, lng, timezone_str



############## 현지의 위/경도를 기준으로 날씨 정보를 반환 ##############
def get_weather_info(lat, lng):
    # weather code 번역 반환
    def get_weather_description(code):
        weather_code_dict = {
            0: '맑음',
            1: '대체로 맑음',
            2: '부분 흐림',
            3: '흐림',
            45: '안개',
            48: '서리 낀 안개',
            51: '약한 이슬비',
            53: '적당한 이슬비',
            55: '강한 이슬비',
            56: '약하게 얼어붙은 이슬비',
            57: '강하게 얼어붙은 이슬비',
            61: '약한 비',
            63: '적당한 비',
            65: '강한 비',
            66: '약하게 얼어붙은 비',
            67: '강하게 얼어붙은 비',
            71: '약한 눈',
            73: '적당한 눈',
            75: '강한 눈',
            77: '진눈깨비',
            80: '약한 소나기',
            81: '적당한 소나기',
            82: '강한 소나기',
            85: '약한 눈보라',
            86: '강한 눈보라',
            95: '천둥번개',
            96: '약한 우박, 천둥번개',
            99: '강한 우박, 천둥번개'
        }
        return weather_code_dict.get(code, "Invalid code")
    BASE_URL = "https://api.open-meteo.com/v1/forecast?"
    OPTION = "&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=GMT"

    GEO_INFO = f"latitude={lat}&longitude={lng}"

    final_url = BASE_URL + GEO_INFO + OPTION
    
    res = requests.get(final_url)
    data = json.loads(res.text)
    
    weather_code = get_weather_description(data['daily']['weathercode'][0])
    temperature_max = data['daily']['temperature_2m_max'][0]
    temperature_min = data['daily']['temperature_2m_min'][0]

    return weather_code, temperature_max, temperature_min



############## 해당하는 도시의 위/경도, 표준시간대를 찾고 현지 시간대와 날씨 반환 ##############
def get_world_clock(city="서울"):
    lat, lng, timezone_str = get_time_zone(city)
    city_url = f"https://www.timeapi.io/api/Time/current/zone?timeZone={timezone_str}"

    city_json = requests.get(city_url)
    data = json.loads(city_json.text)

    weather_code, temperature_max, temperature_min = get_weather_info(lat, lng)

    res = textwrap.dedent(
        f"""
        [{city}]
        오늘 날짜: {data['year']}년 {data['month']}월 {data['day']}일
        현재 시각: {'오후' if data['hour']//12  else '오전'} {data['hour']%12}시 {data['minute']}분 {data['seconds']}초
        현재 날씨: {weather_code} / 최고 {temperature_max} ℃  / 최저 {temperature_min} ℃
        """
        )
    if city=="서울":
        week = data['dayOfWeek']
        week_to_korean = {
                'Monday': '월요일',
                'Tuseday': '화요일',
                'Wednesday': '수요일',
                'Thursday': '목요일',
                'Friday': '금요일',
                'Saturday': '토요일',
                'Sunday': '일요일',
            }
        day_of_week = week_to_korean[week]
        return day_of_week, res
    return res



############## 각국 도시 입력 시 해당 정보 반환 ##############
def get_world_info():
    day_of_week, city1 = get_world_clock()
    good_morning = f"*🥰좋은 아침입니다! 활기찬 {day_of_week}이 되길 바라겠습니다!*\n"

    city2 = get_world_clock("New York")
    city3 = get_world_clock("Calgary")
    return good_morning, city1, city2, city3



############## N뉴스 크롤링 ##############
def get_news():
    browser = webdriver.Chrome()
    browser.implicitly_wait(3)

    today = str(date.today()-timedelta(1)).replace('-','')

    url = f"https://news.naver.com/main/list.naver?mode=LS2D&sid2=283&sid1=105&mid=shm&date={today}"
    browser.get(url)
    browser.implicitly_wait(1)

    page = int(browser.find_element(By.CLASS_NAME, 'paging').text[-1])

    link_set = set()
    keywords = ['ai','AI','클라우드','LLM','LMM','보안', '모델', '데이터', '해킹']

    # 해당하는 키워드가 있는 기사의 링크를 list에 담음
    for i in range(1,page):
        # selenium은 클래스에 괄호 같은 특수문자를 허용하지 않음
        links = browser.find_elements(By.CSS_SELECTOR, '.nclicks\\(itn\\.2ndcont\\)') 
        sentences = browser.find_elements(By.CLASS_NAME, 'lede')
        
        # 뉴스가 중복 버그가 있음(다음 페이지에서 중복, etc)
        for title, cont in zip(links, sentences):
            for keyword in keywords:
                if keyword in title.text+cont.text:
                    link = title.get_attribute('href')
                    link_set.add(link)
                    break

        print(f"{i+1} 페이지 입니다.")
        xpath = f'//*[@id="main_content"]/div[3]/a[{i}]'
        browser.find_element(By.XPATH, xpath).click()
    
    news_data  = []
    for link in link_set:
        browser.get(link)
        browser.implicitly_wait(2)

        # 딜레이 등의 버그로 오류가 걸려도 진행되게끔 추가
        try:
            browser.find_element(By.XPATH, '//*[@id="_SUMMARY_BUTTON"]/a').click()
            browser.implicitly_wait(2)
            len_title = len(browser.find_element(By.CLASS_NAME, 'media_end_head_autosummary_layer_tit').text)
            summary = browser.find_element(By.CLASS_NAME, '_SUMMARY_CONTENT_BODY').text
        except:
            continue
        title = summary[:len_title]
        content = summary[len_title:]

        news = {
            '제목': title,
            '내용': "\n".join(f">{line}" for line in content.split('\n') if line),
            '링크': link
        }
        news_data .append(news)
        # break

    last_day = f"*🆕어제의 `{'/'.join(keywords[1:])}` 기사를 참고해보세요!*\n\n"
    text = "\n\n".join(textwrap.dedent(
        f"*_{idx+1}) {news['제목']}_*\n{news['내용']}\n{news['링크']}") for idx, news in enumerate(news_data))
    return last_day, text



############## 슬랙봇을 통해 메시지 전송 ##############
def send_to_slack():

    # 각국 도시 정보 전송
    good_morning, city1, city2, city3 = get_world_info()
    requests.post(SLACK_URL,
              data=json.dumps({
                  "text":good_morning + city1 + city2 +city3+'\n'
                  }),
              headers={'Content-type' : 'application/json'}
              )
    
    # N뉴스 크롤링 요약 기사 전송
    last_day, news = get_news()
    requests.post(SLACK_URL,
              data=json.dumps({
                  "text": last_day + news
                  }),
              headers={'Content-type' : 'application/json'}
              )



# ############## 매일 09:30에 슬랙봇 실행 ##############
# schedule.every().day.at("09:30").do(send_to_slack)

# while True:
#     schedule.run_pending()
#     time.sleep(60)

send_to_slack()
