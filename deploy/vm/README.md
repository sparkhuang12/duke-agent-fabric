# Private-cloud VM deployment

Install the project under `/opt/duke-agent-fabric`, create an unprivileged `duke` account, and place production settings in root-owned `/etc/duke-agent-fabric/duke.env` with mode `0600`.

The systemd unit binds the application to loopback. Terminate TLS at the supplied Nginx template or an existing internal load balancer. Use private MySQL 8.4, Redis 8, OPA, Keycloak and model-gateway endpoints; firewall all other egress.

Before the first service start, apply `deploy/mysql/001-schema.sql` with a migration identity and configure the service with a separate DML-only MySQL credential.

Enable the application and the daily one-year retention job:

```bash
systemctl enable --now duke-agent-fabric.service
systemctl enable --now duke-maintenance.timer
```
