import re
import logging


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class QuoteExtractor:
    @staticmethod
    def extract_quoted_text(text):
        try:
            """
            주어진 텍스트에서 큰따옴표, 작은따옴표, 또는 대괄호로 둘러싸인 부분을 추출합니다.
            만약 매치되는 부분이 없다면 전체 텍스트를 반환합니다.
            
            :param text: 분석할 텍스트 문자열
            :return: 추출된 따옴표나 괄호 안의 텍스트 리스트, 또는 전체 텍스트
            """
            pattern = r'["\'[\]]([^"\'\[\]]*)["\'\]]'
            matches = re.findall(pattern, text)
            
            if matches:
                return matches
            else:
                return [text.strip()]  # 전체 텍스트를 리스트에 담아 반환
        except Exception as e:
            logger.error(f"Error in extract_quoted_text: {e}", exc_info=True)
            raise

    @staticmethod
    def extract_and_join(text, separator=' '):
        try:
            """
            주어진 텍스트에서 큰따옴표, 작은따옴표, 또는 대괄호로 둘러싸인 부분을 추출하고 지정된 구분자로 연결합니다.
            
            :param text: 분석할 텍스트 문자열
            :param separator: 추출된 텍스트를 연결할 때 사용할 구분자 (기본값: ', ')
            :return: 추출된 텍스트를 구분자로 연결한 문자열
            """
            extracted = QuoteExtractor.extract_quoted_text(text)
            return separator.join(extracted)
        except Exception as e:
            logger.error(f"Error in extract_quoted_text: {e}", exc_info=True)
            raise