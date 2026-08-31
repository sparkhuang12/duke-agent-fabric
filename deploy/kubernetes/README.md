# Kubernetes deployment

This overlay runs three API replicas with a PodDisruptionBudget, HPA, non-root/read-only containers and default-deny networking.

1. Mirror the application and dependency images into the approved internal registry.
2. Replace the image and internal endpoints in `deployment.yaml` and `configmap.yaml`.
3. Apply `deploy/mysql/001-schema.sql` with a separate database migration identity, then issue a DML-only application credential.
4. Create `duke-agent-fabric-secrets` through the platform secret manager; `secret.example.yaml` is not part of Kustomize.
5. Label the ingress and MySQL/Redis/OPA/Keycloak/model-gateway pods with the network roles used by `networkpolicy.yaml`. For managed services, replace that rule with reviewed private CIDRs.
6. Apply with `kubectl apply -k deploy/kubernetes` and expose the Service only through the OIDC-aware internal ingress.

MySQL and Redis are deliberately external to this overlay. Production clusters should use an operator or managed HA services with private endpoints, TLS, backups and tested failover.
