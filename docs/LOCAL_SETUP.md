# Local setup

Prerequisites: Java 21, Maven 3.9+, Node 20+, Python 3.11+, Docker, Git, and optionally Ollama.

```powershell
docker compose up -d mongodb
cd backend; mvn spring-boot:run
cd ../ai-service; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
cd ../frontend; npm run dev
```

Open `http://localhost:5173`. Health endpoints: backend `/api/health`, AI `/health`. Stop with `docker compose down` and Ctrl+C in service terminals.

