import asyncio
from playwright.async_api import async_playwright
from typing import Dict, List
import re

def clean_text(text: str) -> str:
    """텍스트 클리닝 함수"""
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    # 앞뒤 공백 제거
    return text.strip()

def is_meaningful_text(text: str, min_length: int = 10) -> bool:
    """의미있는 텍스트인지 판단하는 함수"""
    # 최소 길이 체크
    if len(text.strip()) < min_length:
        return False
    
    # 광고나 불필요한 텍스트 패턴 체크
    unwanted_patterns = [
        r'^copyright',
        r'^all rights reserved',
        r'^[0-9]+$',  # 숫자로만 이루어진 텍스트
        r'^광고$',
        r'^sponsored$'
    ]
    
    for pattern in unwanted_patterns:
        if re.search(pattern, text.lower()):
            return False
            
    return True

async def extract_text_from_page(url: str) -> Dict[str, any]:
    """
    웹페이지에서 다양한 방식으로 텍스트를 추출합니다.
    
    Args:
        url (str): 크롤링할 웹페이지의 URL
        
    Returns:
        Dict: 다양한 방식으로 추출된 텍스트 데이터를 포함하는 딕셔너리
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until='networkidle')
            
            # 1. 기본 정보 추출
            title = await page.title()
            body_text = await page.evaluate('document.body.innerText')
            
            # 2. 기존 방식의 paragraph 추출
            p_elements = await page.query_selector_all('p')
            paragraphs = []
            for p in p_elements:
                text = await p.inner_text()
                if text.strip():
                    paragraphs.append(text.strip())
            
            # 3. 개선된 방식의 텍스트 추출
            # 메인 콘텐츠 영역 추출 시도
            content_selectors = [
                'article',
                'main',
                '.content',
                '.article-content',
                '#content',
                '.post-content'
            ]
            
            main_content = None
            for selector in content_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        main_content = element
                        break
                except:
                    continue
            
            # 텍스트 추출 대상 요소들
            text_containers = []
            
            if main_content:
                # 메인 콘텐츠 영역이 있는 경우
                text_containers = await main_content.query_selector_all('p, h1, h2, h3, h4, h5, h6, article, section')
            else:
                # 메인 콘텐츠 영역을 찾지 못한 경우 전체 문서에서 추출
                text_containers = await page.query_selector_all('p, h1, h2, h3, h4, h5, h6, article, section')
            
            # 의미있는 텍스트 추출 및 정제
            meaningful_texts = []
            seen_texts = set()  # 중복 제거를 위한 집합
            
            for container in text_containers:
                text = await container.inner_text()
                text = clean_text(text)
                
                # 의미있는 텍스트이고 중복되지 않은 경우만 추가
                if text and is_meaningful_text(text) and text not in seen_texts:
                    meaningful_texts.append(text)
                    seen_texts.add(text)
            
            # 4. 결과 통합
            return {
                'url': url,
                'title': title,
                'body_text': body_text,           # 기존 방식 유지
                'paragraphs': paragraphs,         # 기존 방식 유지
                'meaningful_texts': meaningful_texts  # 새로운 방식 추가
            }
            
        finally:
            await browser.close()

async def main():
    urls = [
        "https://www.sisajournal.com/news/articleView.html?idxno=323604",
        "https://www.kistep.re.kr/reportAllDetail.es?mid=a10305010000&rpt_tp=831-005&rpt_no=RES0220250026"
    ]
    
    for url in urls:
        try:
            result = await extract_text_from_page(url)
            
            print(f"\n=== {result['url']} ===")
            print(f"Title: {result['title']}")
            
            print("\nBody Text (Original method):")
            print(result['body_text'])  # 처음 500자만 출력
            
            print("\nParagraphs (Original method):")
            for p in result['paragraphs']:  # 처음 5개 문단만 출력
                print(f"- {p}")
            
            print("\nMeaningful Texts (New method):")
            for text in result['meaningful_texts']:  # 처음 5개 텍스트만 출력
                print(f"- {text}")
                
        except Exception as e:
            print(f"Error crawling {url}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())