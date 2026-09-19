# Google OAuth setup

Create a Google Cloud project and OAuth consent screen, then a Web application client. Add `http://localhost:8080/login/oauth2/code/google` as an authorized redirect URI and `http://localhost:5173` as an origin. Put the client ID and secret in `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`. Production URIs must use HTTPS.

