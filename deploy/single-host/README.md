# Protected single-host deployment

The root `compose.yaml` runs Duke, MySQL 8.4, Redis 8 and OPA on one protected host. Keycloak and the approved model gateway remain internal external dependencies so their lifecycle and GPU/identity requirements are not coupled to the application stack.

Copy `.env.example` to `.env`, set URL-safe database/Redis passwords, configure the internal Keycloak issuer/JWKS URL and an allow-listed self-hosted model gateway, then run `docker compose up --build -d`.

This mode is suitable for a protected pilot or small installation. It is not highly available: back up both named volumes, test restore, and move MySQL/Redis to replicated services before adopting an HA SLO.
