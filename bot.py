import os, hashlib, random, subprocess, sys, re, pathlib

HANDLE = os.environ["BSKY_HANDLE"]
APP_PASSWORD = os.environ["BSKY_APP_PASSWORD"]
MODEL_ID = os.environ.get("MODEL_ID", "Qwen/Qwen2.5-0.5B-Instruct")
SEEN_FILE = "seen_thoughts.txt"

FALLBACK_THEMES = [
    ("megla", ["megla", "dolina", "tišina", "jutro", "rosna trava"]),
    ("kava", ["skodelica", "para", "budnost", "tresljaj", "grenkoba"]),
    ("mesto", ["avtobus", "robnik", "izložba", "semafor", "odsev"]),
    ("reka", ["tok", "breg", "kamni", "počitek", "globina"]),
    ("zima", ["sneg", "dih", "sled", "hlačne žepe", "mrak"]),
]
FALLBACK_TEMPLATES = [
    "Včasih {w1} utihne, da {w2} lahko pove, kar {w3} skriva.",
    "{w1} se ne mudi; {w2} prispe pravočasno, ko {w3} odneha.",
    "Ko {w1} odpove, {w2} najde pot skozi {w3}.",
    "{w1} je kompas, ki ga {w2} ne zna brati, a {w3} ga čuti.",
    "Med {w1} in {w2} je prostor, v katerem {w3} dozori.",
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
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import torch
mdl = "{MODEL_ID}"
tok = AutoTokenizer.from_pretrained(mdl)
model = AutoModelForCausalLM.from_pretrained(mdl, torch_dtype=torch.float32)
pipe = pipeline("text-generation", model=model, tokenizer=tok, device=-1)
SYSTEM = "Ustvari eno (1) kratko, izvirno modro misel v slovenščini. Brez emoji, brez #, brez narekovajev. 10–22 besed, sodoben ton, rahlo nepričakovano."
user = "Napiši eno misel."
full = f"<|im_start|>system\\n{{SYSTEM}}<|im_end|>\\n<|im_start|>user\\n{{user}}<|im_end|>\\n<|im_start|>assistant\\n"
out = pipe(full, max_new_tokens=60, do_sample=True, temperature=1.1, top_p=0.95, repetition_penalty=1.1)[0]["generated_text"]
print(out.split("<|im_end|>")[0].split("<|im_start|>assistant\\n")[-1].strip())
'''
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return clean_llm_output(res.stdout)

def generate_unique():
    seen = load_seen()
    text = ""
    for _ in range(6):
        try: cand = run_llm()
        except Exception: cand = fallback_generate()
        cand = clean_llm_output(cand)
        if not (10 <= len(cand.split()) <= 22): continue
        h = dedupe_key(cand)
        if h not in seen:
            save_seen(h); return cand
        text = cand
    if not text: text = fallback_generate()
    save_seen(dedupe_key(text))
    return text

def post_to_bluesky(content: str):
    from atproto import Client
    c = Client(); c.login(HANDLE, APP_PASSWORD); c.send_post(content)

if __name__ == "__main__":
    thought = generate_unique()
    post = f"Bip. {thought}"
    post_to_bluesky(post)
    print(post)
