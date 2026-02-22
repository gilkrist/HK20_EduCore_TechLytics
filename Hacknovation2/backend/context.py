# Simple heuristic rules for demo (extend later)
CONTRADICTIONS = [
    ("lifo", "fifo"),
    ("first", "last"),
    ("last", "first"),
    ("hot", "cold"),
    ("cold", "hot"),
    ("big", "small"),
    ("small", "big"),
    ("fast", "slow"),
    ("slow", "fast"),
    ("early", "late"),
    ("late", "early"),
    ("up", "down"),
    ("down", "up"),
    ("open", "close"),
    ("close", "open"),
    ("in", "out"),
    ("out", "in"),
    ("start", "stop"),
    ("stop", "start"),
    ("yes", "no"),
    ("no", "yes"),
    ("true", "false"),
    ("false", "true"),
    ("day", "night"),
    ("night", "day"),
    ("happy", "sad"),
    ("sad", "happy"),
    ("push", "pull"),
    ("pull", "push"),
    ("give", "take"),
    ("take", "give"),
    ("buy", "sell"),
    ("sell", "buy"),
    ("win", "lose"),
    ("lose", "win"),
    ("on", "off"),
    ("off", "on"),
    ("add", "remove"),
    ("remove", "add"),
    ("enter", "exit"),
    ("exit", "enter"),
    ("full", "empty"),
    ("empty", "full")
]

def context_score(model_answer: str, student_answer: str):
    m = model_answer.lower()
    s = student_answer.lower()

    issues = []
    score = 1.0

    for a, b in CONTRADICTIONS:
        if a in m and b in s:
            issues.append(f"Contradiction detected: expected '{a}', found '{b}'")
            score -= 0.4

    score = max(0.0, min(1.0, score))
    error_type = "None"
    if issues:
        error_type = "Conceptual Misunderstanding"
    return score, issues, error_type