from __future__ import annotations

import json
import time

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from duke_harness.config import Settings
from duke_harness.identity.oidc import OIDCAuthenticator


def test_oidc_maps_authoritative_identity_claims() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"keys": [public_jwk]}))
    settings = Settings(
        environment="test",
        auth_mode="oidc",
        oidc_issuer="https://sso.internal/realms/duke",
        oidc_audience="duke-agent-fabric",
        oidc_jwks_url="https://sso.internal/realms/duke/protocol/openid-connect/certs",
    )
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": settings.oidc_issuer,
            "aud": settings.oidc_audience,
            "sub": "user-123",
            "iat": now,
            "exp": now + 300,
            "tenant_id": "tenant-a",
            "department": "legal",
            "clearance": "confidential",
            "realm_access": {"roles": ["user", "security_approver"]},
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    authenticator = OIDCAuthenticator(settings, transport=transport)
    try:
        principal = authenticator.authenticate(token)
        assert principal.tenant_id == "tenant-a"
        assert principal.user_id == "user-123"
        assert principal.department == "legal"
        assert principal.clearance == "confidential"
        assert "security_approver" in principal.roles
    finally:
        authenticator.close()
