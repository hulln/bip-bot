import os, hashlib, random, subprocess, sys, re, pathlib

HANDLE = os.environ["BSKY_HANDLE"]
APP_PASSWORD = os.environ["BSKY_APP_PASSWORD"]
HF_TOKEN = os.environ.get("HF_TOKEN")  # Optional Hugging Face token for higher rate limits
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
    try:
        import requests
        
        # Use Hugging Face's free Inference API
        models = [
            "microsoft/DialoGPT-medium",
            "EleutherAI/gpt-neo-125m",
            "distilgpt2"
        ]
        
        for model in models:
            try:
                headers = {}
                if HF_TOKEN:
                    headers["Authorization"] = f"Bearer {HF_TOKEN}"
                
                url = f"https://api-inference.huggingface.co/models/{model}"
                
                prompt = "Napiši kratek, premišljen razmislek o sodobnem življenju, tehnologiji ali človeški naravi v slovenščini. En stavek:"
                
                response = requests.post(
                    url,
                    headers=headers,
                    json={"inputs": prompt, "parameters": {"max_new_tokens": 40, "temperature": 0.7}},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        generated = result[0].get("generated_text", "")
                        # Extract only the new part after the prompt
                        if generated.startswith(prompt):
                            generated = generated[len(prompt):].strip()
                        
                        # Clean up the output
                        generated = generated.split('.')[0] + '.'  # Take only first sentence
                        generated = re.sub(r'^[^A-Za-z]*', '', generated)  # Remove leading non-letters
                        
                        if generated and 8 <= len(generated.split()) <= 25:
                            return generated
                            
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"LLM generation error: {e}")
        return None

def generate_unique():
    seen = load_seen()
    
    # Try LLM generation first
    for attempt in range(3):
        try:
            cand = run_llm()
            if cand and 10 <= len(cand.split()) <= 30:
                h = dedupe_key(cand)
                if h not in seen:
                    save_seen(h)
                    return cand
        except Exception as e:
            print(f"LLM attempt {attempt + 1} failed: {e}")
            continue
    
    # Fallback to curated content if LLM fails
    curated_thoughts = [
        "Tehnologija nas povezuje v trenutku, vendar se pogosto počutimo bolj oddaljeni kot kdaj koli prej.",
        "Najgloblji pogovori se dogajajo v presledkih med besedami.",
        "Dokumentiramo vsak trenutek, pozabljamo pa ga dejansko živeti.",
        "Družbeni mediji so obljubili povezanost, prinesli pa so anksioznost nastopanja.",
        "Najtiši prostori pogosto skrivajo najglasnejše misli.",
        "Vsi iščemo pristnost v svetu filtrov.",
        "Vsako obvestilo je majhna prekinitev naše notranje tišine.",
        "Internet si zapomni vse, razen tistega, kar je resnično pomembno.",
        "Listamo skozi življenja drugih, ne razumemo pa svojega.",
        "Napredek ni vedno hitrejše gibanje; včasih je počasnejše.",
        "Najpomembnejši pogovori so tisti, ki jih imamo sami s sabo.",
        "Bolj povezani smo kot kadarkoli prej, osamljen pa je vsak.",
        "Vsak zaslon, v katerega gledamo, je ogledalo naših želja.",
        "Najboljše ideje pridejo, ko se ne trudimo jih imeti.",
        "Zgradili smo orodja za varčevanje s časom, pozabili pa, kaj z njim.",
    ]
    
    for thought in curated_thoughts:
        h = dedupe_key(thought)
        if h not in seen:
            save_seen(h)
            return thought
    
    # If all thoughts used, pick random one
    thought = random.choice(curated_thoughts)
    save_seen(dedupe_key(thought))
    return thought

def post_to_bluesky(content: str):
    from atproto import Client
    c = Client(); c.login(HANDLE, APP_PASSWORD); c.send_post(content)

if __name__ == "__main__":
    thought = generate_unique()
    post = f"Bip. {thought}"
    post_to_bluesky(post)
    print(post)
