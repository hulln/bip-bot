import os, hashlib, random, subprocess, sys, re, pathlib

HANDLE = os.environ["BSKY_HANDLE"]
APP_PASSWORD = os.environ["BSKY_APP_PASSWORD"]
MODEL_ID = os.environ.get("MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")
SEEN_FILE = "seen_thoughts.txt"

FALLBACK_THEMES = [
    ("morning", ["coffee", "dawn", "quiet", "thoughts", "beginning"]),
    ("city", ["streets", "windows", "strangers", "lights", "movement"]),
    ("nature", ["trees", "wind", "shadows", "seasons", "growth"]),
    ("time", ["moments", "memory", "change", "patience", "rhythm"]),
    ("connection", ["words", "silence", "distance", "understanding", "presence"]),
]
FALLBACK_TEMPLATES = [
    "Sometimes {w1} teaches us more than {w2} ever could about {w3}.",
    "Between {w1} and {w2}, we discover what {w3} really means.",
    "The space where {w1} meets {w2} is where {w3} begins.",
    "{w1} reminds us that {w2} isn't always about {w3}.",
    "In every {w1}, there's a {w2} waiting to show us {w3}.",
]

def fallback_generate():
    theme, words = random.choice(FALLBACK_THEMES)
    w1, w2, w3 = random.sample(words, 3)
    return random.choice(FALLBACK_TEMPLATES).format(w1=w1, w2=w2, w3=w3)

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
    code = f'''
import sys
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    import torch
    
    mdl = "{MODEL_ID}"
    print(f"Loading model: {{mdl}}", file=sys.stderr)
    
    tok = AutoTokenizer.from_pretrained(mdl)
    model = AutoModelForCausalLM.from_pretrained(mdl, torch_dtype=torch.float32)
    pipe = pipeline("text-generation", model=model, tokenizer=tok, device=-1)
    
    prompt = "Write a thoughtful observation about life, technology, or human nature in 15-25 words:"
    
    print(f"Generating with prompt: {{prompt}}", file=sys.stderr)
    result = pipe(prompt, max_new_tokens=50, do_sample=True, temperature=0.8, pad_token_id=tok.eos_token_id)
    output = result[0]["generated_text"]
    
    # Extract only the generated part after the prompt
    generated = output[len(prompt):].strip()
    
    print(f"Raw output: {{output}}", file=sys.stderr)
    print(f"Generated part: {{generated}}", file=sys.stderr)
    
    if generated and len(generated.split()) >= 8:
        print(generated)
    else:
        print("Every moment teaches us something new about what it means to be human.")
        
except Exception as e:
    print(f"Error in LLM generation: {{e}}", file=sys.stderr)
    print("Every moment teaches us something new about what it means to be human.")
'''
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return clean_llm_output(res.stdout)

def generate_unique():
    seen = load_seen()
    
    # Try LLM generation multiple times
    for attempt in range(8):
        try: 
            cand = run_llm()
            cand = clean_llm_output(cand)
            print(f"LLM attempt {attempt + 1}: {cand}")
            
            if cand and 8 <= len(cand.split()) <= 30:
                h = dedupe_key(cand)
                if h not in seen:
                    save_seen(h)
                    return cand
        except Exception as e:
            print(f"LLM attempt {attempt + 1} failed: {e}")
            continue
    
    # Only use fallback if LLM completely fails
    print("LLM generation failed, using fallback")
    fallback = fallback_generate()
    save_seen(dedupe_key(fallback))
    return fallback

def post_to_bluesky(content: str):
    from atproto import Client
    c = Client(); c.login(HANDLE, APP_PASSWORD); c.send_post(content)

if __name__ == "__main__":
    thought = generate_unique()
    post = f"Bip. {thought}"
    post_to_bluesky(post)
    print(post)
