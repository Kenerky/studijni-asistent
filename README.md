# Studijní Asistent 2.0

Moderní webová aplikace pro asistenci při studiu s využitím umělé inteligence. Aplikace umožňuje vysvětlování pojmů a generování interaktivních testů z naučených konceptů.

## Funkce

- **Vysvětlování pojmů**: Zadejte libovolný pojem a AI ho stručně vysvětlí
- **Interaktivní testy**: Generování testů z vašich naučených pojmů
- **Historie**: Sledování výsledků testů
- **Uživatelské účty**: Registrace a přihlášení pro osobní prostor
- **Responzivní design**: Funguje na počítači i mobilu

## Technologie

- **Backend**: FastAPI (Python)
- **Databáze**: PostgreSQL
- **AI**: OpenAI API (kompatibilní s lokálními modely)
- **Frontend**: HTML, CSS, JavaScript
- **Nasazení**: Docker & Docker Compose

## Spuštění

1. **Klonování repozitáře**:
   ```bash
   git clone https://github.com/Kenerky/studijni-asistent.git
   cd studijni-asistent
   ```

2. **Nastavení proměnných prostředí**:
   Vytvořte soubor `.env` nebo nastavte proměnné:
   ```env
   DATABASE_URL=postgresql://admin:heslo123@db:5432/studydb
   SECRET_KEY=vaše_tajné_klíč
   OPENAI_API_KEY=váš_openai_klíč
   OPENAI_BASE_URL=https://api.openai.com/v1  # nebo URL lokálního modelu
   ```

3. **Spuštění s Docker**:
   ```bash
   docker-compose up --build
   ```

4. **Přístup k aplikaci**:
   Otevřte http://localhost:5000 v prohlížeči

## Vývoj

Pro vývoj bez Dockeru:

1. Nainstalujte závislosti:
   ```bash
   pip install -r requirements.txt
   ```

2. Spusťte databázi s Docker:
   ```bash
   docker run -d --name postgres -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=heslo123 -e POSTGRES_DB=studydb -p 5432:5432 postgres:16-alpine
   ```

3. Spusťte aplikaci:
   ```bash
   python main.py
   ```
