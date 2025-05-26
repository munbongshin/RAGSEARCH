import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re

def get_content_patterns() -> List[str]:
    """일반적인 콘텐츠 관련 클래스/ID 패턴"""
    return [
        # 기본 콘텐츠 패턴
        'content', 'contents', 'article', 'post',
        # 변형 패턴들
        'article-content', 'post-content', 'entry-content',
        'main-content', 'page-content', 'body-content',
        # 본문 관련
        'body-text', 'article-body', 'post-body', 'text-body',
        # 추가 일반적인 패턴
        'text', 'main', 'story', 'article-text', 'article_text'
    ]

def clean_text(text: str) -> str:
    """텍스트 클리닝 함수"""
    # URL과 링크 정보 제거
    text = re.sub(r'https?://\S+', '', text)  # URL 제거
    text = re.sub(r'출처\s*:\s*.*$', '', text, flags=re.MULTILINE)  # 출처 정보 제거
    text = re.sub(r'\([^)]*?(링크|http|www|\.com|\.kr)[^)]*?\)', '', text)  # 괄호 안의 링크 정보 제거
    
    # 불필요한 공백 제거
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분리하는 함수"""
    # 줄바꿈을 공백으로 변경
    text = re.sub(r'\n+', ' ', text)
    
    # 문장 분리를 위한 정규식 패턴
    # 마침표/물음표/느낌표 + 공백 + 대문자 또는 한글
    pattern = r'(?<=[.!?])\s+(?=[A-Z가-힣])'
    
    # 문장 분리
    sentences = re.split(pattern, text)
    
    # 빈 문장 제거하고 클리닝
    return [clean_text(sent) for sent in sentences if clean_text(sent)]

def is_valid_sentence(text: str) -> bool:
    """
    완성된 문장인지 확인하는 함수
    - 마침표, 물음표, 느낌표로 끝나는지 확인
    - 따옴표나 괄호가 올바르게 닫혀있는지 확인
    """
    text = text.strip()
    if not text:
        return False
        
    # 마침표, 물음표, 느낌표로 끝나는지 확인
    if not text[-1] in '.!?':
        return False
        
    # 따옴표 쌍이 맞는지 확인
    quotes_count = text.count('"') + text.count('"') + text.count('"')
    if quotes_count % 2 != 0:
        return False
        
    # 괄호 쌍이 맞는지 확인
    parentheses = []
    brackets_pairs = {'(': ')', '[': ']', '{': '}'}
    
    for char in text:
        if char in brackets_pairs.keys():
            parentheses.append(char)
        elif char in brackets_pairs.values():
            if not parentheses:
                return False
            if char != brackets_pairs[parentheses.pop()]:
                return False
    
    if parentheses:  # 닫히지 않은 괄호가 있는 경우
        return False
        
    return True

def get_continuous_sentences(text: str, min_length: int = 10) -> List[str]:
    """연속된 의미 있는 문장들을 추출하는 함수"""
    text = clean_text(text)
    sentences = split_into_sentences(text)
    
    # 의미 있는 문장만 필터링
    meaningful_sentences = []
    for sentence in sentences:
        cleaned_sentence = clean_text(sentence)
        # 최소 길이, 불필요한 패턴 체크, 문장 구조 체크
        if (len(cleaned_sentence) >= min_length and 
            not any(pattern in cleaned_sentence.lower() for pattern in [
                'copyright', 
                'all rights reserved',
                '기자',
                '편집자',
                '저작권자'
            ]) and 
            is_valid_sentence(cleaned_sentence)):
            meaningful_sentences.append(cleaned_sentence)
    
    return meaningful_sentences

def analyze_content_block(element) -> float:
    """HTML 요소의 콘텐츠 점수를 계산"""
    if not element:
        return 0
    
    text = element.get_text()
    words = len(text.split())
    tags = len(element.find_all())
    paragraphs = len(element.find_all('p'))
    links = len(element.find_all('a'))
    
    # 점수 계산
    score = words * 1.0  # 기본 점수는 단어 수
    if tags > 0:
        score *= (paragraphs / tags)  # 단락 비율 반영
    if links > 0 and words > 0:
        score *= (1 - (links / words))  # 링크 비율 반영
    
    return score

def extract_main_content(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """HTML에서 주요 콘텐츠 영역을 추출"""
    candidates = []
    
    # 1. 클래스/ID 기반 검색
    for pattern in get_content_patterns():
        elements = soup.find_all(class_=lambda x: x and pattern.lower() in x.lower())
        candidates.extend(elements)
        
        elements = soup.find_all(id=lambda x: x and pattern.lower() in x.lower())
        candidates.extend(elements)
    
    # 2. 태그 기반 검색
    main_tags = ['article', 'main', 'section','body-text']
    for tag in main_tags:
        elements = soup.find_all(tag)
        candidates.extend(elements)
    
    # 3. 점수 기반 선택
    best_element = None
    best_score = 0
    
    for element in candidates:
        score = analyze_content_block(element)
        if score > best_score:
            best_score = score
            best_element = element
    
    # 4. 대안 검색
    if not best_element or best_score < 100:  # 임계값 조정 가능
        # div 태그 중에서 가장 많은 텍스트를 포함한 요소 찾기
        for div in soup.find_all('div'):
            score = analyze_content_block(div)
            if score > best_score:
                best_score = score
                best_element = div
    
    return best_element

async def extract_text_from_page(url: str) -> Dict[str, any]:
    """웹페이지에서 텍스트를 추출하는 함수"""
    browser_config = BrowserConfig(
        headless=True,
        ignore_https_errors=True
    )
    
    run_config = CrawlerRunConfig(
        word_count_threshold=0,
        excluded_tags=['script', 'style', 'nav', 'footer', 'header'],
        exclude_external_links=True,
        process_iframes=False,
        remove_overlay_elements=True,
        cache_mode=CacheMode.DISABLED
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
        
        if result.success:
            soup = BeautifulSoup(result.html, 'html.parser')
            
            # 메인 콘텐츠 추출
            main_content = extract_main_content(soup)
            
            if main_content:
                text = clean_text(main_content.get_text())
                sentences = get_continuous_sentences(text)
                
                # 제목 추출 시도
                title = ""
                title_candidates = [
                    soup.find('h1'),
                    soup.find(class_=lambda x: x and 'title' in x.lower()),
                    soup.find(id=lambda x: x and 'title' in x.lower())
                ]
                
                for candidate in title_candidates:
                    if candidate:
                        title = clean_text(candidate.get_text())
                        if title:
                            break
                
                return {
                    'title': title,
                    'sentences': sentences
                }
            
        return {
            'title': '',
            'sentences': []
        }

async def main():
    urls = [
        "https://www.sisajournal.com/news/articleView.html?idxno=323604",
        "https://www.kistep.re.kr/reportAllDetail.es?mid=a10305010000&rpt_tp=831-005&rpt_no=RES0220250026",
        "https://docs.crawl4ai.com/api/parameters/"
        
    ]
    
    for url in urls:
        try:
            result = await extract_text_from_page(url)
            
            # 제목 출력
            if result['title']:
                print(f"\nTitle: {result['title']}")
                print("-" * 80)
            
            # 추출된 문장 출력
            print("\nExtracted Continuous Sentences:")
            for i, sentence in enumerate(result['sentences'], 1):
                print(f"{i}. {sentence}")
            print(f"\nTotal sentences found: {len(result['sentences'])}")
                
        except Exception as e:
            error_msg = str(e)
            if "Tracking Prevention" not in error_msg:
                print(f"Error: {error_msg}")

if __name__ == "__main__":
    asyncio.run(main())