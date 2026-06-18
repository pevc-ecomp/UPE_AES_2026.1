from fastapi import FastAPI
from app.schemas import SearchStringJudgeRequest, ArticleClassificationJudgeRequest
from app.judges import judge_search_string, judge_article_classification

app = FastAPI(
    title="AI as Judge for Systematic Reviews",
    description="Local LLM judge for search strings and article classification decisions in systematic literature reviews.",
    version="1.0.0",
)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "AI as Judge API is running",
        "docs": "/docs",
    }


@app.post("/judge/string")
def judge_string(data: SearchStringJudgeRequest):
    result = judge_search_string(data)
    return result


@app.post("/judge/articles")
def judge_articles(data: ArticleClassificationJudgeRequest):
    result = judge_article_classification(data)
    return result
