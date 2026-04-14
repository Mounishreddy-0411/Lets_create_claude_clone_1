import os
import re
import requests
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(override=True)

app = Flask(__name__)
CORS(app)

# --- Configuration ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# Initialize Gemini Client
if GOOGLE_API_KEY == "your_gemini_key" or not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY is not set correctly in .env!")
    client = None
else:
    client = genai.Client(api_key=GOOGLE_API_KEY)

# --- Search Pipeline Triggers ---
SEARCH_TRIGGERS = [
    "news", "latest", "today", "current", "now", "live", "score", "result",
    "price", "stock", "crypto", "bitcoin", "weather", "forecast", "rain",
    "breaking", "2024", "2025", "2026", "who won", "what happened",
    "trending", "recently", "this week", "this month", "update",
    "match", "election", "war", "attack", "event", "release", "launch",
    "died", "death", "born", "age", "when did", "how much is",
    "vs", "versus", "winner", "champion", "standings", "table",
    "GDP", "population", "president", "prime minister", "CEO",
    "new movie", "new song", "album", "trailer", "review",
    "earthquake", "flood", "disaster", "crisis", "protest",
    "transfer", "signing", "injured", "suspended", "fired", "arrested"
]

def should_trigger_search(query):
    query_lower = query.lower()
    return any(trigger in query_lower for trigger in SEARCH_TRIGGERS)

# --- Tooling & Services ---

def scrape_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strip script, style, nav, footer
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
            
        text = soup.get_text(separator=' ')
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:8000]
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def search_serper(query):
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": 10,
            "tbs": "qdr:d",
            "gl": "in",
            "hl": "en"
        }
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        results = []
        for item in data.get("organic", []):
            results.append({
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "url": item.get("link")
            })
        return results
    except Exception as e:
        print(f"Serper API Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def search_ddg(query):
    # Instant Answer API
    url = f"https://api.duckduckgo.com/?q={query}&format=json"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return None

def search_wikipedia(query):
    url = "https://en.wikipedia.org/w/rest.php/v1/search/page"
    params = {'q': query, 'limit': 3}
    headers = {'User-Agent': 'UniversalAI/1.0 (contact@example.com)'}
    try:
        response = requests.get(url, params=params, headers=headers)
        return response.json()
    except:
        return None

def get_weather(location):
    url = f"https://wttr.in/{location}?format=j1"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return None

# --- Gemini Interaction ---

def ask_gemini(prompt, context="", model_id="gemini-2.0-flash"):
    system_prompt = f"""RULE: Always use web results as primary source.
RULE: Never use training memory for live data.
RULE: Never guess or hallucinate any facts.
RULE: If search fails, say so then answer from knowledge.
You are an all-knowing AI assistant.
Today's date is {datetime.now().strftime('%Y-%m-%d')}.
You must ALWAYS provide a helpful, complete answer.
NEVER say you cannot help or cannot access data.
If web results are provided below, use them as your primary source.
If no web results, use your own knowledge confidently.
For math and coding, answer directly.
For live data like scores/prices, use web results only.
Always cite sources as [1], [2] when using web results.
Keep answers clear, accurate, and detailed.
Never guess live scores or prices without web results."""

    full_prompt = f"{system_prompt}\n\nCONTEXT FROM WEB:\n{context}\n\nUSER QUERY: {prompt}"
    
    if not client:
        return "ERROR: API Key is missing or invalid. Please update your .env file with a valid Gemini API Key from https://aistudio.google.com"

    # Fallback Chain for 2026 environment: 2.5-flash -> 2.0-flash -> 2.0-flash-lite -> 2.5-flash-lite
    model_fallback_list = [
        "gemini-2.5-flash", 
        "gemini-2.0-flash", 
        "gemini-2.0-flash-lite", 
        "gemini-2.5-flash-lite",
        "gemini-flash-lite-latest"
    ]
    
    # If the user specifically requested a different model (via route), put it at the start
    if model_id not in model_fallback_list:
        model_fallback_list.insert(0, model_id)
    else:
        # Prioritize the passed model_id
        model_fallback_list.remove(model_id)
        model_fallback_list.insert(0, model_id)

    last_error = ""
    for model in model_fallback_list:
        try:
            print(f"Attempting response with model: {model}...")
            response = client.models.generate_content(
                model=model,
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            last_error = str(e)
            print(f"Error with {model}: {last_error}")
            if "429" in last_error or "quota" in last_error.lower():
                continue # Try next model in chain
            else:
                break # Hard error, stop chain
    
    return f"Gemini API Error: {last_error}. This usually happens when your API key has zero quota or billing is not enabled. Please check https://aistudio.google.com and try switching to a Pay-as-you-go plan (which has a generous free tier)."

# --- Routes ---

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    query = data.get('query', '')
    history = data.get('history', [])
    
    search_context = ""
    source_type = "AI Knowledge"
    sources = []
    if should_trigger_search(query):
        # Cascading search
        results = search_serper(query)
        if results and len(results) > 0:
            source_type = "Web Search"
            # Scrape top 3
            scraped_data = []
            for item in results[:3]:
                link = item.get('url')
                title = item.get('title', link)
                snippet = item.get('snippet', '')
                sources.append({"title": title, "url": link, "snippet": snippet})
                
                content = scrape_url(link)
                if content:
                    scraped_data.append(f"Source: {link}\nContent: {content}")
            search_context = "\n\n".join(scraped_data)
        else:
            # Fallback to DDG
            ddg_res = search_ddg(query)
            if ddg_res and ddg_res.get('AbstractText'):
                source_type = "DuckDuckGo"
                link = ddg_res.get('AbstractURL')
                title = ddg_res.get('Heading', link)
                snippet = ddg_res.get('AbstractText', '')
                sources.append({"title": title, "url": link, "snippet": snippet})
                search_context = f"Summary: {snippet}\nSource: {link}"
            else:
                # Fallback to Wikipedia
                wiki_res = search_wikipedia(query)
                if wiki_res and wiki_res.get('pages'):
                    source_type = "Wikipedia"
                    for p in wiki_res.get('pages')[:3]:
                        link = f"https://en.wikipedia.org/wiki/{p.get('title').replace(' ', '_')}"
                        sources.append({
                            "title": p.get('title'),
                            "url": link,
                            "snippet": p.get('excerpt')
                        })
                    search_context = "\n".join([f"Page: {p.get('title')}\nExcerpt: {p.get('excerpt')}" for p in wiki_res.get('pages')])

    answer = ask_gemini(query, search_context)
    
    return jsonify({
        "answer": answer,
        "source": source_type,
        "model": "gemini-2.0-flash",
        "sources": sources[:3]
    })

@app.route('/search', methods=['POST'])
def force_search():
    data = request.json
    query = data.get('query', '')
    
    results = search_serper(query)
    scraped_data = []
    sources = []
    if results and len(results) > 0:
        for item in results[:3]:
            link = item.get('url')
            title = item.get('title', link)
            snippet = item.get('snippet', '')
            sources.append({"title": title, "url": link, "snippet": snippet})
            
            content = scrape_url(link)
            scraped_data.append(f"Source: {link}\nContent: {content}")
    
    search_context = "\n\n".join(scraped_data)
    answer = ask_gemini(query, search_context)
    
    return jsonify({
        "answer": answer,
        "source": "Forced Web Search",
        "model": "gemini-2.0-flash",
        "sources": sources[:3]
    })

@app.route('/weather', methods=['POST'])
def weather():
    data = request.json
    location = data.get('location', 'London')
    weather_data = get_weather(location)
    
    if weather_data:
        prompt = f"Explain the current weather in {location} based on this data: {json.dumps(weather_data['current_condition'][0])}"
        answer = ask_gemini(prompt, str(weather_data))
        return jsonify({"answer": answer, "source": "Weather API", "model": "gemini-2.0-flash"})
    return jsonify({"answer": "Could not fetch weather data.", "source": "Error", "model": "gemini-2.0-flash"})

@app.route('/image', methods=['POST'])
def analyze_image():
    # Placeholder for image path or bytes
    # In a real app, you'd handle file upload
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    img_data = file.read()
    
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                types.Part.from_bytes(data=img_data, mime_type=file.content_type),
                "Analyze this image in detail."
            ]
        )
        return jsonify({"answer": response.text, "source": "Gemini Vision", "model": "gemini-2.0-flash"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    query = data.get('query', '')
    answer = ask_gemini(f"Calculate or convert exactly: {query}")
    return jsonify({"answer": answer, "source": "Gemini Math", "model": "gemini-2.0-flash"})

@app.route('/code', methods=['POST'])
def code_help():
    data = request.json
    query = data.get('query', '')
    answer = ask_gemini(f"Help with this coding task: {query}")
    return jsonify({"answer": answer, "source": "Gemini Code", "model": "gemini-2.0-flash"})

if __name__ == '__main__':
    app.run(port=5000, debug=True)
