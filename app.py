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
TOTAL_LIMIT = 15
MIN_RELEVANT_NEWS = 8

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
      summary: Get the latest 15 AI news articles within 12 hours, filtered and sorted.
      operationId: getSmartNews
      responses:
        "200":
          description: A list of AI news articles
          content:
            application/json:
              schema:
                type: array
                minItems: 8
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
  /smart_news_compact:
    get:
      summary: Get a simplified list of 15 AI news articles for GPT tools.
      operationId: getSmartNewsCompact
      responses:
        "200":
          description: A compact list of AI news articles
          content:
            application/json:
              schema:
                type: array
                minItems: 8
                maxItems: 15
                items:
                  type: object
                  properties:
                    translated_title:
                      type: string
                    translated_summary:
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

def get_entry_link(entry):
    if hasattr(entry, "link") and entry.link:
        return entry.link
    elif hasattr(entry, "links") and entry.links and isinstance(entry.links, list):
        return entry.links[0].get("href", "")
    elif hasattr(entry, "id"):
        return entry.id
    return ""

def get_filtered_news():
    feed = feedparser.parse(RSS_URL)
    now = datetime.utcnow()
    all_entries = []

    for entry in feed.entries:
        published = get_published_time(entry)
        if (now - published).total_seconds() <= 43200:
            summary = clean_html(entry.get("summary", ""))
            source = entry.get("source", {}).get("title", "Unknown")
            relevance = get_relevance_score(entry)
            link = get_entry_link(entry)
            if not link:
                continue
            link = link.replace("&amp;", "&")
            all_entries.append({
                "title": entry.title,
                "translated_title": translate(entry.title),
                "summary": summary,
                "translated_summary": translate(summary),
                "link": link,
                "markdown_link": f"[點我看原文]({link})",
                "published": published.date().isoformat(),
                "published_datetime": published,
                "source": source,
                "relevance": relevance
            })

    relevant_news = [n for n in all_entries if n["relevance"] > 0]
    fallback_news = [n for n in all_entries if n["relevance"] == 0]

    if len(relevant_news) < MIN_RELEVANT_NEWS:
        need = MIN_RELEVANT_NEWS - len(relevant_news)
        relevant_news += fallback_news[:need]
        fallback_news = fallback_news[need:]

    final_news = relevant_news + fallback_news
    final_news = final_news[:TOTAL_LIMIT]

    def sort_key(item):
        try:
            priority = PREFERRED_SOURCES.index(item["source"])
        except ValueError:
            priority = len(PREFERRED_SOURCES)
        return (priority, -item["relevance"], -item["published_datetime"].timestamp())

    sorted_news = sorted(final_news, key=sort_key)

    return sorted_news

@app.route("/smart_news")
def smart_news():
    news = get_filtered_news()
    for n in news:
        del n["published_datetime"]
        del n["relevance"]
    return jsonify(news)

@app.route("/smart_news_compact")
def smart_news_compact():
    news = get_filtered_news()
    compact = [{
        "translated_title": n["translated_title"],
        "translated_summary": n["translated_summary"],
        "published": n["published"],
        "source": n["source"],
        "markdown_link": n["markdown_link"]
    } for n in news]
    return jsonify(compact)

@app.route("/openapi.yaml")
def openapi_spec():
    return Response(OPENAPI_YAML, mimetype="text/yaml")

if __name__ == "__main__":
    app.run(debug=True)
