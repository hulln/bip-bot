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
        import requests
        import time
        
        # Use models that are publicly available without auth
        models_and_prompts = [
            ("gpt2", "A thoughtful observation:"),
            ("distilgpt2", "Insight about life:"),
            ("EleutherAI/gpt-neo-125M", "Modern life reflection:"),
        ]
        
        for model, prompt in models_and_prompts:
            try:
                headers = {"Content-Type": "application/json"}
                if HF_TOKEN:
                    headers["Authorization"] = f"Bearer {HF_TOKEN}"
                
                url = f"https://api-inference.huggingface.co/models/{model}"
                
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": 30,
                        "temperature": 0.7,
                        "do_sample": True,
                        "top_p": 0.9,
                        "repetition_penalty": 1.1
                    }
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                print(f"Model {model} status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        generated = result[0].get("generated_text", "")
                        
                        # Extract only the new part after the prompt
                        if generated.startswith(prompt):
                            generated = generated[len(prompt):].strip()
                        
                        # Clean up the output
                        generated = re.sub(r'^[^A-Za-z]*', '', generated)  # Remove leading non-letters
                        generated = generated.split('.')[0].strip()  # Take only first sentence
                        if generated and not generated.endswith('.'):
                            generated += '.'
                        
                        # More lenient length check
                        if generated and 3 <= len(generated.split()) <= 25:
                            print(f"Successfully generated with {model}: {generated}")
                            return generated
                
                elif response.status_code == 503:
                    print(f"Model {model} is loading, trying next...")
                    time.sleep(3)
                    continue
                elif response.status_code == 401:
                    print(f"Model {model} requires authentication - need HF_TOKEN")
                    continue
                else:
                    print(f"Model {model} returned status {response.status_code}")
                    
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue
        
        # If all models fail, return None - no fallback
        print("All LLM models failed, no fallback")
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
