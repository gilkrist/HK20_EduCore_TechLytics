def fuse_scores(semantic, keyword, context):
    final = 0.5 * semantic + 0.3 * keyword + 0.2 * context

    if final >= 0.75:
        verdict = "Mostly Correct"
    elif final >= 0.45:
        verdict = "Partially Correct"
    else:
        verdict = "Incorrect"

    return round(final, 3), verdict