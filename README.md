# Barabari Intelligent Project Mentoring Platform

A project-scoped mentoring workspace that helps students interpret requirements, solve routine issues with evidence, and escalate uncertain or high-impact questions to mentors. Verified mentor resolutions return to the knowledge base.

## Quick start

1. Copy/configure `.env` (local-safe defaults already exist for development).
2. Start MongoDB: `docker compose up -d mongodb`.
3. Backend: `cd backend && mvn spring-boot:run`.
4. AI: `cd ai-service && python -m uvicorn app.main:app --reload --port 8000`.
5. Frontend: `cd frontend && npm install && npm run dev`.

Open http://localhost:5173. API docs are at http://localhost:8000/docs. See `docs/LOCAL_SETUP.md` for details.

## Security

Registration is invitation-only. Roles originate only from invitations. The bootstrap administrator is created idempotently if no admin exists. Change development credentials before deployment and never commit `.env`.

