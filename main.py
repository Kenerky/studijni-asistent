import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import uvicorn
from openai import OpenAI
import httpx

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "vychozi-tajny-klic")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")

app = FastAPI(title="Studijní asistent")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nelze ověřit přihlašovací údaje",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

class Prompt(BaseModel):
    dotaz: str

class UserCreate(BaseModel):
    username: str
    password: str

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Uživatel již existuje")
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    return {"message": "Uživatel úspěšně vytvořen"}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Nesprávné jméno nebo heslo")
    
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/status")
def status_endpoint():
    return {
        "time": datetime.now().isoformat(),
        "autor": "René Špánek",
        "tema": "Studijní Asistent - vysvětlení pojmů"
    }

@app.post("/ai")
def ai(prompt: Prompt, current_user: User = Depends(get_current_user)):
    system_instruction = (
        f"Jsi přísný výkladový slovník. Uživatel zadal vstup: '{prompt.dotaz}'. "
        "1. Pokud je to odborný pojem (např. 'DHCP', 'Relativita'), vysvětli ho stručně a jasně, v jednom dotazu může být i více pojmů. "
        "2. Může to být i věta nebo víceslovný pojem, pokud je to ale věta typu 'jak se máš' nebo se ve větě nenachází otázka na pojem, odpověz POUZE větou: "
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