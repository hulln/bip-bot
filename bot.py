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
        
        # Use multiple Hugging Face models and prompts for better success rate
        models_and_prompts = [
            ("microsoft/DialoGPT-medium", "Write a thoughtful observation about modern life:"),
            ("EleutherAI/gpt-neo-125m", "Thoughtful insight about technology and human nature:"),
            ("distilgpt2", "Brief philosophical observation about life:"),
            ("microsoft/DialoGPT-small", "Wise thought about modern society:"),
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
                        "max_new_tokens": 50,
                        "temperature": 0.8,
                        "do_sample": True,
                        "top_p": 0.9
                    }
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                
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
                        
                        if generated and 5 <= len(generated.split()) <= 30:
                            print(f"Successfully generated with {model}: {generated}")
                            return generated
                
                elif response.status_code == 503:
                    print(f"Model {model} is loading, trying next...")
                    time.sleep(2)
                    continue
                else:
                    print(f"Model {model} returned status {response.status_code}")
                    
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"LLM generation error: {e}")
        return None

def generate_unique():
    seen = load_seen()
    
    # Try LLM generation multiple times - no fallback to curated content
    for attempt in range(10):
        try:
            cand = run_llm()
            if cand and 8 <= len(cand.split()) <= 35:
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
    
    # If all LLM attempts fail, don't post anything
    raise Exception("LLM generation completely failed after 10 attempts")

def post_to_bluesky(content: str):
    from atproto import Client
    c = Client(); c.login(HANDLE, APP_PASSWORD); c.send_post(content)

if __name__ == "__main__":
    thought = generate_unique()
    post = f"Bip. {thought}"
    post_to_bluesky(post)
    print(post)
