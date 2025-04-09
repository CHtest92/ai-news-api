from flask import Flask, request, jsonify, Response
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from collections import defaultdict

app = Flask(__name__)
RSS_URL = "https://www.inoreader.com/stream/user/1003787482/tag/AI科技?type=rss"

PREFERRED_SOURCES = ["數位時代", "彭博", "路透"]
IMPORTANT_KEYWORDS = [
    "生成式", "openai", "chatgpt", "大模型", "llm", "ai創作", "ai轉譯",
    "copilot", "語音識別", "ai助手", "ai應用", "prompt", "gpt", "text-to"
]
SOURCE_LIMIT = 5
TOTAL_LIMIT = 15

OPENAPI_YAML = """
openapi: 3.1.0
info:
  title: AI News Briefing API
  version: 1.0.0
servers:
  - url: https://ai-news-api-9r4w.onrender.com
paths:
  /smart_news:
    get:
      summary: Get the latest 15 AI news articles within 12 hours, sorted by preferred sources and limited per source.
      operationId: getSmartNews
      responses:
        '200':
          description: A list of AI news articles
          content:
            application/json:
              schema:
                type: array
                maxItems: 15
                items:
                  type: object
                  properties:
                    title:
                      type: string
                    translated_title:
                      type: string
                    summary:
                      type: string
                    translated_summary:
                      type: string
                    link:
                      type: string
                    published:
                      type: string
                    source:
                      type: string
                    markdown_link:
                      type: string
"""

def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img"):
        img.decompose()
    return soup.get_text(separator="\n").strip()

def translate(text):
    try:
        return GoogleTranslator(source="auto", target="zh-tw").translate(text)
    except:
        return text

def get_published_time(entry):
    try:
        return datetime(*entry.published_parsed[:6])
    except:
        return datetime.utcnow()

def get_relevance_score(entry):
    content = (entry.title + entry.get("summary", "")).lower()
    return sum(1 for k in IMPORTANT_KEYWORDS if k in content)

@app.route("/smart_news")
def smart_news():
    feed = feedparser.parse(RSS_URL)
    now = datetime.utcnow()
    grouped_by_source = defaultdict(list)

    for entry in feed.entries:
        published = get_published_time(entry)
        if (now - published).total_seconds() <= 43200:
            summary = clean_html(entry.get("summary", ""))
            source = entry.get("source", {}).get("title", "Unknown")
            relevance = get_relevance_score(entry)
            grouped_by_source[source].append({
                "title": entry.title,
                "translated_title": translate(entry.title),
                "summary": summary,
                "translated_summary": translate(summary),
                "link": entry.link,
                "markdown_link": f"[點我看原文]({entry.link})",
                "published": published.date().isoformat(),
                "published_datetime": published,
                "source": source,
                "relevance": relevance
            })

    all_news = []
    for source in grouped_by_source:
        entries = sorted(grouped_by_source[source], key=lambda x: (-x["relevance"], -x["published_datetime"].timestamp()))
        all_news.extend(entries[:SOURCE_LIMIT])

    def sort_key(item):
        try:
            priority = PREFERRED_SOURCES.index(item["source"])
        except ValueError:
            priority = len(PREFERRED_SOURCES)
        return (priority, -item["relevance"], -item["published_datetime"].timestamp())

    sorted_news = sorted(all_news, key=sort_key)[:TOTAL_LIMIT]
    for news in sorted_news:
        del news["published_datetime"]
        del news["relevance"]

    return jsonify(sorted_news)

@app.route("/get_news_by_link")
def get_news_by_link():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        if entry.link == url:
            summary = clean_html(entry.get("summary", ""))
            return jsonify({
                "title": entry.title,
                "translated_title": translate(entry.title),
                "summary": summary,
                "content": summary,
                "published": get_published_time(entry).date().isoformat(),
                "source": entry.get("source", {}).get("title", "Unknown"),
                "link": entry.link
            })
    return jsonify({"error": "Article not found", "link": url}), 404

@app.route("/search_news")
def search_news():
    keyword = request.args.get("keyword", "")
    if not keyword:
        return jsonify({"error": "Missing keyword"}), 400
    feed = feedparser.parse(RSS_URL)
    results = []
    for entry in feed.entries:
        title = entry.title
        summary = clean_html(entry.get("summary", ""))
        if keyword.lower() in title.lower() or keyword.lower() in summary.lower():
            results.append({
                "title": title,
                "translated_title": translate(title),
                "summary": summary,
                "translated_summary": translate(summary),
                "link": entry.link,
                "published": get_published_time(entry).date().isoformat(),
                "source": entry.get("source", {}).get("title", "Unknown"),
                "markdown_link": f"[點我看原文]({entry.link})"
            })
        if len(results) >= 10:
            break
    return jsonify(results)

@app.route("/openapi.yaml")
def openapi_spec():
    return Response(OPENAPI_YAML, mimetype="text/yaml")

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Render 後端可能在睡覺中，請 30 秒後重試"}), 500

if __name__ == "__main__":
    app.run(debug=True)
