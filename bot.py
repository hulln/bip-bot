import os, hashlib, random, subprocess, sys, re, pathlib

HANDLE = os.environ["BSKY_HANDLE"]
APP_PASSWORD = os.environ["BSKY_APP_PASSWORD"]
HF_TOKEN = os.environ.get("HF_TOKEN")  # Optional Hugging Face token for higher rate limits
SEEN_FILE = "seen_thoughts.txt"

def norm(t): return " ".join(t.split()).strip()
def dedupe_key(t): return hashlib.sha256(norm(t).lower().encode()).hexdigest()
def load_seen():
    p = pathlib.Path(SEEN_FILE)
    if not p.exists(): return set()
    return {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()}
def save_seen(h):
    with open(SEEN_FILE, "a", encoding="utf-8") as f: f.write(h + "\n")

def clean_llm_output(s: str) -> str:
    s = norm(s)
    s = re.sub(r'^(assistant|system|user)\s*[:：-]\s*', '', s, flags=re.I)
    s = s.replace("“","").replace("”","").replace('"',"").replace("#","")
    return s.split("\n")[0].strip()

def run_llm():
    try:
        # Try Groq first (free and fast)
        import requests
        
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        
        # Try without API key first (some endpoints are free)
        payload = {
            "model": "mixtral-8x7b-32768",
            "messages": [
                {"role": "user", "content": "Napiši kratko, premišljeno opazovanje o življenju, človeški naravi, družbi, odnosih ali kateremkoli vidiku obstoja v slovenščini. 15-20 besed:"}
            ],
            "max_tokens": 50,
            "temperature": 0.8
        }
        
        response = requests.post(groq_url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if content and 5 <= len(content.split()) <= 25:
                print(f"Groq generated: {content}")
                return content
        
        # NO FALLBACK - RETURN NONE
        print("Groq API failed, no fallback")
        return None
        
    except Exception as e:
        print(f"LLM generation error: {e}")
        return None

def generate_unique():
    seen = load_seen()
    
    # Try LLM generation multiple times - NO FALLBACKS
    for attempt in range(10):
        try:
            cand = run_llm()
            if cand and 3 <= len(cand.split()) <= 35:
                cand = clean_llm_output(cand)
                h = dedupe_key(cand)
                if h not in seen:
                    save_seen(h)
                    return cand
                else:
                    print(f"Generated content already seen, trying again (attempt {attempt + 1})")
        except Exception as e:
            print(f"LLM attempt {attempt + 1} failed: {e}")
            continue
    
    # If all LLM attempts fail, raise exception - DON'T POST ANYTHING
    raise Exception("LLM generation completely failed - no post will be made")

def post_to_bluesky(content: str):
    from atproto import Client
    c = Client(); c.login(HANDLE, APP_PASSWORD); c.send_post(content)

if __name__ == "__main__":
    thought = generate_unique()
    post = f"Bip. {thought}"
    post_to_bluesky(post)
    print(post)
