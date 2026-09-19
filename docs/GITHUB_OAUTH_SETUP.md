# GitHub OAuth setup

Create a GitHub OAuth App. Use `http://localhost:5173` as Homepage URL and `http://localhost:8080/login/oauth2/code/github` as callback. Configure `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env`. Request `read:user user:email`; registration must match a verified provider email to the invitation.

