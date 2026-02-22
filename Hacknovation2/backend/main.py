from fastapi import FastAPI
from pydantic import BaseModel
from semantic import semantic_score
from keywords import keyword_coverage
from context import context_score
from fusion import fuse_scores
from fastapi import UploadFile, File
import csv, json, io
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Hybrid Answer Evaluator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    question_id: str
    model_answer: str
    student_answer: str


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    sem = semantic_score(req.model_answer, req.student_answer)
    kw_score, matched, missing = keyword_coverage(req.model_answer, req.student_answer)
    ctx_score, issues, error_type = context_score(req.model_answer, req.student_answer)

    final_score, verdict = fuse_scores(sem, kw_score, ctx_score)

    feedback = "Good attempt."
    if verdict == "Partially Correct":
        feedback = "You captured some ideas, but missed key concepts."
    elif verdict == "Incorrect":
        feedback = "The core concept is incorrect. Review the fundamentals."

    return {
        "question_id": req.question_id,
        "semantic_score": round(sem, 3),
        "keyword_score": round(kw_score, 3),
        "context_score": round(ctx_score, 3),
        "final_score": final_score,
        "verdict": verdict,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "context_issues": issues,
        "error_type": error_type,
        "feedback": feedback
    }


@app.post("/analyze-batch")
async def analyze_batch(model_file: UploadFile = File(...), student_file: UploadFile = File(...)):
    def parse_model_file(content: bytes, filename: str):
        rows = {}
        if filename.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="ignore")))
            for r in reader:
                rows[r.get("question_id", "").strip()] = r.get("model_answer", "").strip()
        elif filename.endswith(".json"):
            data = json.loads(content.decode("utf-8", errors="ignore"))
            for r in data:
                rows[str(r.get("question_id", "")).strip()] = str(r.get("model_answer", "")).strip()
        return rows

    def parse_student_file(content: bytes, filename: str):
        rows = {}
        if filename.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="ignore")))
            for r in reader:
                rows[r.get("question_id", "").strip()] = r.get("student_answer", "").strip()
        elif filename.endswith(".json"):
            data = json.loads(content.decode("utf-8", errors="ignore"))
            for r in data:
                rows[str(r.get("question_id", "")).strip()] = str(r.get("student_answer", "")).strip()
        return rows

    m_content = await model_file.read()
    s_content = await student_file.read()

    model_map = parse_model_file(m_content, model_file.filename.lower())
    student_map = parse_student_file(s_content, student_file.filename.lower())

    results = []
    for qid, model_ans in model_map.items():
        student_ans = student_map.get(qid, "")
        if not student_ans:
            continue

        sem = semantic_score(model_ans, student_ans)
        kw_score, matched, missing = keyword_coverage(model_ans, student_ans)
        ctx_score, issues, error_type = context_score(model_ans, student_ans)
        final_score, verdict = fuse_scores(sem, kw_score, ctx_score)

        results.append({
            "question_id": qid,
            "final_percent": int(round(final_score * 100)),
            "semantic_score": round(sem, 3),
            "keyword_score": round(kw_score, 3),
            "context_score": round(ctx_score, 3),
            "verdict": verdict,
            "missing_keywords": missing,
            "context_issues": issues,
            "error_type": error_type
        })

    keyword_weak = semantic_weak = context_weak = 0
    error_type_counts = {}
    missed_concepts = {}
    low_score_qids = []

    for r in results:
        if r["keyword_score"] < 0.5:
            keyword_weak += 1
        if r["semantic_score"] < 0.6:
            semantic_weak += 1
        if r["context_score"] < 0.6:
            context_weak += 1
        et = r.get("error_type")
        if et:
            error_type_counts[et] = error_type_counts.get(et, 0) + 1
        for m in r.get("missing_keywords", []):
            missed_concepts[m] = missed_concepts.get(m, 0) + 1
        if r["final_percent"] < 60:
            low_score_qids.append(r["question_id"])

    primary = "Mixed"
    if keyword_weak >= semantic_weak and keyword_weak >= context_weak:
        primary = "Terminology / Key Concepts"
    elif semantic_weak >= keyword_weak and semantic_weak >= context_weak:
        primary = "Conceptual Understanding"
    elif context_weak >= keyword_weak and context_weak >= semantic_weak:
        primary = "Logical Consistency"

    top_missed = sorted(missed_concepts, key=missed_concepts.get, reverse=True)[:5]
    insights = []
    actions = []

    if primary == "Terminology / Key Concepts":
        insights.append("You often miss important keywords and technical terms.")
        actions.append("Maintain a glossary of key terms and revise definitions.")
    elif primary == "Conceptual Understanding":
        insights.append("Your answers show partial understanding of core concepts.")
        actions.append("Explain topics in your own words after studying.")
    elif primary == "Logical Consistency":
        insights.append("Some answers contain logical contradictions.")
        actions.append("Practice step-by-step reasoning and verify assumptions.")
    else:
        insights.append("You show mixed weaknesses across terminology, meaning, and logic.")
        actions.append("Revise fundamentals and practice structured answering.")

    if error_type_counts.get("Conceptual Misunderstanding", 0) > 0:
        insights.append("Conceptual misunderstandings appear frequently.")
        actions.append("Revisit core definitions with diagrams and examples.")

    if top_missed:
        insights.append(f"Commonly missed concepts: {', '.join(top_missed)}")
        actions.append("Create short notes for the missed concepts and revise daily.")

    if low_score_qids:
        insights.append(f"Lowest scoring questions: {', '.join(low_score_qids[:5])}")
        actions.append("Reattempt these questions after revision.")

    student_feedback = {
        "primary_weakness": primary,
        "common_missed_concepts": top_missed,
        "insights": insights,
        "action_plan": actions
    }

    return {
        "total_evaluated": len(results),
        "results": results,
        "student_feedback": student_feedback
    }


@app.post("/analyze-class")
async def analyze_class(
    model_file: UploadFile = File(...),
    students_file: UploadFile = File(...)
):
    """
    Expects:
      model_file  — CSV with columns: question_id, answer
      students_file — CSV with columns: student_id, Q1, Q2, Q3, ...
                      (question IDs as column headers)
    """
    model_bytes = await model_file.read()
    students_bytes = await students_file.read()

    # ---- Parse model answers: question_id -> answer ----
    model_answers = {}
    model_reader = csv.DictReader(io.StringIO(model_bytes.decode("utf-8", errors="ignore")))
    for row in model_reader:
        qid = row.get("question_id", "").strip()
        ans = row.get("answer", "").strip()
        if qid:
            model_answers[qid] = ans

    # ---- Parse students file ----
    students_reader = csv.DictReader(io.StringIO(students_bytes.decode("utf-8", errors="ignore")))
    # question IDs are all columns except student_id
    question_ids = [f for f in students_reader.fieldnames if f.strip() != "student_id"]

    class_sem, class_kw, class_ctx, class_final = [], [], [], []
    students_results = []

    # ---- Per-class aggregation for insights ----
    class_keyword_weak = class_semantic_weak = class_context_weak = 0
    class_missed_concepts = {}
    class_error_counts = {}
    total_questions_evaluated = 0

    for row in students_reader:
        student_id = row.get("student_id", "").strip()
        if not student_id:
            continue

        details = []
        sem_scores, kw_scores, ctx_scores, final_scores = [], [], [], []

        for qid in question_ids:
            qid = qid.strip()
            student_ans = row.get(qid, "").strip()
            model_ans = model_answers.get(qid, "")

            if not student_ans or not model_ans:
                continue

            sem = semantic_score(model_ans, student_ans)
            kw_score, matched, missing = keyword_coverage(model_ans, student_ans)
            ctx_score, issues, error_type = context_score(model_ans, student_ans)
            final_percent, verdict = fuse_scores(sem, kw_score, ctx_score)

            # Convert final_percent to int (fuse_scores returns a float 0-1 or percent?)
            # Keep consistent with /analyze-batch: multiply by 100 if it's 0-1
            if isinstance(final_percent, float) and final_percent <= 1.0:
                final_percent_int = int(round(final_percent * 100))
            else:
                final_percent_int = int(round(final_percent))

            details.append({
                "question_id": qid,
                "semantic_score": round(sem, 3),
                "keyword_score": round(kw_score, 3),
                "context_score": round(ctx_score, 3),
                "final_percent": final_percent_int,
                "verdict": verdict,
                "matched_keywords": matched,
                "missing_keywords": missing,
                "context_issues": issues,
                "error_type": error_type
            })

            sem_scores.append(sem)
            kw_scores.append(kw_score)
            ctx_scores.append(ctx_score)
            final_scores.append(final_percent_int)

            # Aggregate for class insights
            if kw_score < 0.5:
                class_keyword_weak += 1
            if sem < 0.6:
                class_semantic_weak += 1
            if ctx_score < 0.6:
                class_context_weak += 1
            if error_type:
                class_error_counts[error_type] = class_error_counts.get(error_type, 0) + 1
            for m in missing:
                class_missed_concepts[m] = class_missed_concepts.get(m, 0) + 1
            total_questions_evaluated += 1

        if not final_scores:
            continue

        avg_sem = round(sum(sem_scores) / len(sem_scores), 3)
        avg_kw = round(sum(kw_scores) / len(kw_scores), 3)
        avg_ctx = round(sum(ctx_scores) / len(ctx_scores), 3)
        avg_final = round(sum(final_scores) / len(final_scores))

        class_sem.append(avg_sem)
        class_kw.append(avg_kw)
        class_ctx.append(avg_ctx)
        class_final.append(avg_final)

        students_results.append({
            "student_id": student_id,
            "avg_semantic": avg_sem,
            "avg_keyword": avg_kw,
            "avg_context": avg_ctx,
            "avg_percent": avg_final,
            "verdict": "Mostly Correct" if avg_final >= 70 else "Partially Correct" if avg_final >= 40 else "Incorrect",
            "details": details
        })

    class_averages = {
        "semantic_avg": round(sum(class_sem) / len(class_sem), 3) if class_sem else 0,
        "keyword_avg": round(sum(class_kw) / len(class_kw), 3) if class_kw else 0,
        "context_avg": round(sum(class_ctx) / len(class_ctx), 3) if class_ctx else 0,
        "final_avg_percent": round(sum(class_final) / len(class_final)) if class_final else 0
    }

    # ---- Class-wide insights ----
    primary = "Mixed"
    if class_keyword_weak >= class_semantic_weak and class_keyword_weak >= class_context_weak:
        primary = "Terminology / Key Concepts"
    elif class_semantic_weak >= class_keyword_weak and class_semantic_weak >= class_context_weak:
        primary = "Conceptual Understanding"
    elif class_context_weak >= class_keyword_weak and class_context_weak >= class_semantic_weak:
        primary = "Logical Consistency"

    top_missed = sorted(class_missed_concepts, key=class_missed_concepts.get, reverse=True)[:5]

    insights = []
    actions = []

    if primary == "Terminology / Key Concepts":
        insights.append("The class frequently misses important keywords and technical terms.")
        actions.append("Conduct vocabulary drills and encourage students to maintain a glossary.")
    elif primary == "Conceptual Understanding":
        insights.append("Many students show only partial understanding of core concepts.")
        actions.append("Use concept maps and peer teaching to reinforce understanding.")
    elif primary == "Logical Consistency":
        insights.append("Several students produce logically inconsistent answers.")
        actions.append("Practice structured writing and step-by-step reasoning exercises.")
    else:
        insights.append("The class shows mixed weaknesses across terminology, meaning, and logic.")
        actions.append("Revise fundamentals and practice structured answering as a class.")

    if class_error_counts.get("Conceptual Misunderstanding", 0) > 0:
        insights.append("Conceptual misunderstandings are widespread across the class.")
        actions.append("Revisit core definitions using diagrams and real-world examples.")

    if top_missed:
        insights.append(f"Commonly missed concepts across class: {', '.join(top_missed)}")
        actions.append("Dedicate a revision session specifically to these missed concepts.")

    class_feedback = {
        "primary_weakness": primary,
        "common_missed_concepts": top_missed,
        "insights": insights,
        "action_plan": actions
    }

    return {
        "class_averages": class_averages,
        "class_feedback": class_feedback,
        "students": students_results
    }