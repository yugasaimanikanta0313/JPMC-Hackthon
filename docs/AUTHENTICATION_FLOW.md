# Authentication flow

An administrator creates a single-use, expiring invitation containing the authoritative role and optional project. Email/password or OAuth proves identity; it never selects a role. After email/invitation matching, the backend creates the user, membership, marks the invitation accepted, and issues short-lived access plus rotating refresh tokens. Logout revokes the refresh session. The first administrator is created once from environment configuration.

