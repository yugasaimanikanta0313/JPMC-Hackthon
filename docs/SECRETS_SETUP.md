# Secrets setup

Copy `.env.example` to `.env` and enter values only in the local `.env`; it is Git-ignored. Required for production: a random 32+ byte `JWT_SECRET`, Atlas `MONGODB_URI`, and a strong bootstrap password. Optional integrations use `GOOGLE_CLIENT_*`, `GITHUB_CLIENT_*`, `SMTP_*`, `AWS_*`, `GEMINI_*`, and `CLICKUP_*`. Never commit or log these values.

