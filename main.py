import os
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import uvicorn
from openai import OpenAI
import httpx

from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from passlib.context import CryptContext
from jose import JWTError, jwt

# Konfigurace
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://admin:heslo123@db:5432/studydb")
SECRET_KEY = os.environ.get("SECRET_KEY", "76d828d857dc94f28c1e5014481ff6a31facf82a18f35133c87b016f88f746a8")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")

app = FastAPI(title="Studijní asistent 2.0")

# Databáze
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    concepts = relationship("Concept", back_populates="owner")
    tests = relationship("TestResult", back_populates="owner")

class Concept(Base):
    __tablename__ = "concepts"
    id = Column(Integer, primary_key=True, index=True)
    term = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="concepts")

class TestResult(Base):
    __tablename__ = "test_results"
    id = Column(Integer, primary_key=True, index=True)
    score = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="tests")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# Auth
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise HTTPException(status_code=401, detail="Neplatný token")
    except JWTError: raise HTTPException(status_code=401, detail="Neplatný token")
    user = db.query(User).filter(User.username == username).first()
    if user is None: raise HTTPException(status_code=401, detail="Uživatel nenalezen")
    return user

# Schémata
class Prompt(BaseModel): dotaz: str
class UserCreate(BaseModel): username: str; password: str
class ScoreSubmit(BaseModel): score: str

# Endpointy
@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Uživatel již existuje")
    db.add(User(username=user.username, hashed_password=get_password_hash(user.password)))
    db.commit()
    return {"message": "Registrace úspěšná"}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Nesprávné jméno nebo heslo")
    return {"access_token": create_access_token(data={"sub": user.username}), "token_type": "bearer"}

@app.post("/ai")
def ai(prompt: Prompt, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    system_instruction = f"Jsi výkladový slovník. Vysvětli pojem: '{prompt.dotaz}'. Odpověz stručně. Pokud to není pojem, napiš: 'Zadejte prosím pouze konkrétní pojem.'"
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, http_client=httpx.Client(verify=False))
        res = client.chat.completions.create(model="gemma3:27b", messages=[{"role": "user", "content": system_instruction}])
        odpoved = res.choices[0].message.content
        if "Zadejte prosím" not in odpoved:
            db.add(Concept(term=prompt.dotaz, user_id=current_user.id))
            db.commit()
        return {"odpoved": odpoved}
    except Exception as e: return {"error": str(e)}

@app.get("/quiz/generate")
def generate_quiz(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    concepts_db = db.query(Concept).filter(Concept.user_id == current_user.id).all()
    terms = list(set([c.term for c in concepts_db]))[-5:]
    if len(terms) < 2: return {"error": "Hledejte aspoň 2 pojmy pro test."}
    
    instr = f"Vytvoř test ze slov: {', '.join(terms)}. Vrať JEN JSON: " + '[{"otazka": "text", "moznosti": ["A","B","C","D"], "spravna_index": 0}]'
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, http_client=httpx.Client(verify=False))
        raw = client.chat.completions.create(model="gemma3:27b", messages=[{"role": "user", "content": instr}]).choices[0].message.content
        return {"quiz": json.loads(raw.replace("```json", "").replace("```", ""))}
    except: return {"error": "Chyba generování."}

@app.post("/quiz/save")
def save_quiz(data: ScoreSubmit, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(TestResult(score=data.score, user_id=current_user.id))
    db.commit()
    return {"message": "Uloženo"}

@app.get("/quiz/history")
def get_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hist = db.query(TestResult).filter(TestResult.user_id == current_user.id).order_by(TestResult.created_at.desc()).all()
    return {"history": [{"score": h.score, "date": h.created_at.strftime("%d.%m %H:%M")} for h in hist]}

@app.get("/status")
def status_endpoint():
    return {"time": datetime.now().isoformat(), "autor": "René Špánek", "tema": "Studijní Asistent"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))