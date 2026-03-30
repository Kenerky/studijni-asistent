import os
import sqlite3
import hashlib
import secrets
import json
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import uvicorn
from openai import OpenAI
import httpx

DB_PATH = "asistent.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS terms (id INTEGER PRIMARY KEY, user_id INTEGER, term TEXT, explanation TEXT)''')
    conn.commit()
    conn.close()

init_db()

app = FastAPI(title="Studijní asistent")

api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")

class UserAuth(BaseModel):
    username: str
    password: str

class Prompt(BaseModel):
    dotaz: str

class SavedTerm(BaseModel):
    term: str
    explanation: str

def get_user_id(token: str):
    if not token: return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM sessions WHERE token=?", (token,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/status")
def status():
    return {
        "time": datetime.now().isoformat(),
        "autor": "René Špánek & AI",
        "tema": "Studijní Asistent - výuka a testy"
    }

@app.post("/register")
def register(user: UserAuth):
    pwd_hash = hashlib.sha256(user.password.encode()).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user.username, pwd_hash))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Uživatel již existuje")
    conn.close()
    return {"msg": "Registrace úspěšná"}

@app.post("/login")
def login(user: UserAuth):
    pwd_hash = hashlib.sha256(user.password.encode()).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (user.username, pwd_hash))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail="Špatné jméno nebo heslo")
    
    token = secrets.token_hex(16)
    c.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row[0]))
    conn.commit()
    conn.close()
    return {"token": token}

@app.post("/ai")
def ai_explain(prompt: Prompt):
    system_instruction = (
        f"Jsi přísný výkladový slovník. Uživatel zadal vstup: '{prompt.dotaz}'. "
        "Pokud je to odborný pojem, vysvětli ho stručně a jasně. "
        "Jinak odpověz POUZE: 'Zadejte prosím pouze konkrétní pojem k vysvětlení.'"
    )
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, http_client=httpx.Client(verify=False))
        odpoved = client.chat.completions.create(
            model="gemma3:27b",
            messages=[{"role": "user", "content": system_instruction}]
        )
        return {"odpoved": odpoved.choices[0].message.content, "term": prompt.dotaz}
    except Exception as e:
        return {"error": str(e)}

@app.post("/save_term")
def save_term(term_data: SavedTerm, authorization: str = Header(None)):
    user_id = get_user_id(authorization)
    if not user_id: raise HTTPException(status_code=401, detail="Neautorizováno")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO terms (user_id, term, explanation) VALUES (?, ?, ?)", (user_id, term_data.term, term_data.explanation))
    conn.commit()
    conn.close()
    return {"msg": "Uloženo"}

@app.get("/generate_test")
def generate_test(authorization: str = Header(None)):
    user_id = get_user_id(authorization)
    if not user_id: raise HTTPException(status_code=401, detail="Neautorizováno")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT term, explanation FROM terms WHERE user_id=? ORDER BY RANDOM() LIMIT 10", (user_id,))
    terms = c.fetchall()
    conn.close()

    if not terms:
        return {"error": "Nemáš uložené žádné pojmy pro test."}

    terms_list = ", ".join([t[0] for t in terms])
    system_instruction = (
        f"Jsi učitel. Vytvoř test pro studenta na tyto pojmy: {terms_list}. "
        "Vrať POUZE validní JSON pole, kde každý objekt má strukturu: "
        '{"otazka": "text", "odpovedi": {"A": "...", "B": "...", "C": "...", "D": "..."}, "spravna": "A"}. '
        "Nevracej žádný markdown, žádný text okolo, jen čistý JSON."
    )

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, http_client=httpx.Client(verify=False))
        odpoved = client.chat.completions.create(
            model="gemma3:27b",
            messages=[{"role": "user", "content": system_instruction}]
        )
        
        raw_json = odpoved.choices[0].message.content.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
        
        test_data = json.loads(raw_json.strip())
        return {"test": test_data}
    except Exception as e:
        return {"error": "Nepodařilo se vygenerovat test. Zkuste to znovu.", "details": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)