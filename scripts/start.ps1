$ErrorActionPreference = 'Stop'
docker compose up -d mongodb
Start-Process powershell -ArgumentList '-NoExit','-Command','cd backend; mvn spring-boot:run'
Start-Process powershell -ArgumentList '-NoExit','-Command','cd ai-service; python -m uvicorn app.main:app --reload --port 8000'
Start-Process powershell -ArgumentList '-NoExit','-Command','cd frontend; npm run dev'

