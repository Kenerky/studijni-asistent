import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import uvicorn
from openai import OpenAI
import httpx

app = FastAPI(title="Studijní asistent")

api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")

class Prompt(BaseModel):
    dotaz: str

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
        "1. Pokud je to odborný pojem (např. 'DHCP', 'Relativita'), vysvětli ho stručně a jasně, v jednom dotazu může být i více pojmů. "
        "2. Pokud je to celá věta, pozdrav, nebo otázka typu 'jak se máš', odpověz POUZE větou: "
        "'Zadejte prosím pouze konkrétní pojem k vysvětlení.'"
    )
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.Client(verify=False)
        )

        odpoved = client.chat.completions.create(
            model="gemma3:27b",
            messages=[{"role": "user", "content": system_instruction}]
        )
        
        return {"odpoved": odpoved.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)