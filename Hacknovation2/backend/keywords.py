import re

def extract_keywords(text: str):
    text = text.lower()
    words = re.findall(r"[a-zA-Z]+", text)
    stopwords = {"the","is","a","an","of","to","and","in","on","for","with","as","by","or","that","this","it"}
    return list({w for w in words if w not in stopwords and len(w) > 2})

def keyword_coverage(model_answer: str, student_answer: str):
    m_kw = set(extract_keywords(model_answer))
    s_kw = set(extract_keywords(student_answer))
    if not m_kw:
        return 0.0, [], []
    matched = sorted(list(m_kw & s_kw))
    missing = sorted(list(m_kw - s_kw))
    score = len(matched) / len(m_kw)
    return score, matched, missing