# API summary

- `GET /api/health` - backend health
- `GET|POST /api/projects` - project collection
- `GET /health` - AI health/configuration status
- `POST /api/v1/ask` - project-scoped evidence query

Additional production resource groups follow `/api/auth`, `/api/invitations`, `/api/projects/{projectId}`, `/api/escalations`, and `/api/admin`. Errors use stable codes and never expose stack traces.

