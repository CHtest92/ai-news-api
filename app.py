from flask import Flask, request, jsonify
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

app = Flask(__name__)
RSS_URL = "https://www.inoreader.com/stream/user/1003787482/tag/AI科技?type=rss"

PREFERRED_SOURCES = ["數位時代", "彭博", "路透"]
IMPORTANT_KEYWORDS = [
    "生成式", "openai", "chatgpt", "大模型", "llm", "ai創作", "ai轉譯",
    "copilot", "語音識別", "ai助手", "ai應用", "prompt", "gpt", "text-to"
]

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

def is_relevant(entry):
    fulltext = (entry.title + entry.get("summary", "")).lower()
    return any(k in fulltext for k in IMPORTANT_KEYWORDS)

@app.route("/smart_news")
def smart_news():
    feed = feedparser.parse(RSS_URL)
    now = datetime.utcnow()
    filtered = []
    for entry in feed.entries:
        published = get_published_time(entry)
        if (now - published).total_seconds() <= 43200 and is_relevant(entry):
            summary = clean_html(entry.get("summary", ""))
            source = entry.get("source", {}).get("title", "Unknown")
            filtered.append({
                "title": entry.title,
                "translated_title": translate(entry.title),
                "summary": summary,
                "translated_summary": translate(summary),
                "link": entry.link,
                "published": published.date().isoformat(),
                "published_datetime": published,
                "source": source
            })

    def sort_key(item):
        try:
            priority = PREFERRED_SOURCES.index(item["source"])
        except ValueError:
            priority = len(PREFERRED_SOURCES)
        return (priority, -item["published_datetime"].timestamp())

    sorted_news = sorted(filtered, key=sort_key)[:15]
    for news in sorted_news:
        del news["published_datetime"]

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
                "source": entry.get("source", {}).get("title", "Unknown")
            })
        if len(results) >= 10:
            break
    return jsonify(results)

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Render 後端可能在睡覺中，請 30 秒後重試"}), 500

if __name__ == "__main__":
    app.run(debug=True)
