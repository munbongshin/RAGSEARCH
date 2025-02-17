
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.probability import FreqDist
from heapq import nlargest

class TextSummarizer:
    stop_words = set(stopwords.words('english'))

    @classmethod
    def summarize(cls, text, num_sentences=5):
        if not isinstance(text, str):
            text = str(text)

        sentences = sent_tokenize(text)
        words = word_tokenize(text.lower())
        word_frequencies = FreqDist(word for word in words if word not in cls.stop_words)

        sentence_scores = {}
        for sentence in sentences:
            for word in word_tokenize(sentence.lower()):
                if word in word_frequencies:
                    if sentence not in sentence_scores:
                        sentence_scores[sentence] = word_frequencies[word]
                    else:
                        sentence_scores[sentence] += word_frequencies[word]

        summary_sentences = nlargest(num_sentences, sentence_scores, key=sentence_scores.get)
        summary = ' '.join(summary_sentences)
        return summary