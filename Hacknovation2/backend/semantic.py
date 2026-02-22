from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_model = SentenceTransformer("all-MiniLM-L6-v2")

def semantic_score(a: str, b: str) -> float:
    emb = _model.encode([a, b])
    sim = cosine_similarity([emb[0]], [emb[1]])[0][0]
    return float(sim)