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
                {"role": "user", "content": "Write a brief, thoughtful observation about life, human nature, society, relationships, or any aspect of existence in 15-20 words:"}
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
        
        # Fallback to a simple local generation approach
        import random
        
        # Generate using simple templates with randomization - DIVERSE TOPICS
        subjects = [
            "Love", "Friendship", "Time", "Memory", "Dreams", "Fear", "Hope", "Loneliness", 
            "Laughter", "Silence", "Rain", "Music", "Books", "Art", "Nature", "Cities",
            "Children", "Parents", "Strangers", "Stories", "Secrets", "Trust", "Change",
            "Morning", "Night", "Seasons", "Travel", "Home", "Work", "Rest", "Learning",
            "Mistakes", "Success", "Failure", "Growth", "Patience", "Kindness", "Anger"
        ]
        
        verbs = [
            "teaches us", "reminds us", "shows us", "reveals", "whispers", "demands",
            "offers", "hides", "transforms", "carries", "builds", "breaks", "heals",
            "connects", "separates", "creates", "destroys", "nurtures", "challenges"
        ]
        
        insights = [
            "what we truly value", "who we really are", "the beauty in small moments",
            "that everything passes", "the power of presence", "how fragile we are",
            "how strong we can be", "that we're all connected", "the importance of now",
            "that less is often more", "how much we need each other", "the magic in ordinary days",
            "that courage isn't fearlessness", "how precious simplicity is", "the weight of words",
            "that vulnerability is strength", "how healing comes slowly", "the joy in giving",
            "that everyone has a story", "how beautiful imperfection is"
        ]
        
        subject = random.choice(subjects)
        verb = random.choice(verbs)
        insight = random.choice(insights)
        
        generated = f"{subject} {verb} {insight}."
        print(f"Locally generated: {generated}")
        return generated
        
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
