import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
from datetime import datetime

app = FastAPI(title="Studijní asistent")
api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")

class Prompt(BaseModel):
    dotaz: str

@app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/ping")
def ping():
    return "pong"

@app.get("/status")
def status():
    return {
        "time": datetime.now().isoformat(),
        "autor": "René Špánek",
        "tema": "Studijní Asistent - vysvětlení pojmů"
    }

@app.post("/ai")
def ai(prompt: Prompt):
    system_instruction = (
        f"Jsi přísný výkladový slovník. Uživatel zadal vstup: '{prompt.dotaz}'. "
        "1. Pokud je to odborný pojem (např. 'DHCP', 'Relativita'), vysvětli ho velmi stručně a jasně. "
        "2. Pokud je to celá věta, pozdrav, nebo otázka typu 'jak se máš', odpověz POUZE větou: "
        "'Zadejte prosím pouze konkrétní pojem k vysvětlení.'"
    )
    
    headers = {
        "authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gemma3:27b",
        "messages": [{"role":"user","content":system_instruction}]
    }

    try:
        response = requests.post(base_url, json=payload, headers=headers)
        data = response.json()
        return {"odpoved": data.get("response", str(data))}
    except Exception as e:
        return {"error": str(e)}