# SMTP setup

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_PASSWORD`. Use an app password or transactional provider credential. Without SMTP, invitation and reset endpoints should return a safe status while local development logs only a delivery reference, never raw tokens.

