"""Run inside Authentik: docker compose exec -T server ak shell < scripts/configure-imperium.py."""
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from django.db import transaction
from authentik.core.models import Application, Group, User
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

with transaction.atomic():
    signing_key = next(
        key for key in CertificateKeyPair.objects.exclude(key_data="")
        if isinstance(key.private_key, RSAPrivateKey)
    )
    provider, _ = OAuth2Provider.objects.update_or_create(
        client_id="imperium",
        defaults={
            "name": "Imperium",
            "client_type": "public",
            "client_secret": "",
            "authorization_flow": Flow.objects.get(slug="default-provider-authorization-implicit-consent"),
            "invalidation_flow": Flow.objects.get(slug="default-provider-invalidation-flow"),
            "grant_types": ["authorization_code", "refresh_token"],
            "_redirect_uris": [
                {"matching_mode": "strict", "url": "https://imperium.decaneva.cloud/auth/callback", "redirect_uri_type": "authorization"},
                {"matching_mode": "strict", "url": "https://imperium.decaneva.cloud/", "redirect_uri_type": "logout"},
            ],
            "issuer_mode": "per_provider",
            "signing_key": signing_key,
            "access_token_validity": "minutes=5",
            "refresh_token_validity": "hours=10",
            "include_claims_in_id_token": True,
        },
    )
    scopes = [ScopeMapping.objects.get(managed=f"goauthentik.io/providers/oauth2/scope-{scope}")
              for scope in ["openid", "profile", "offline_access"]]
    groups_mapping, _ = ScopeMapping.objects.update_or_create(
        name="Imperium groups", defaults={
            "scope_name": "profile",
            "expression": 'return {"groups": list(request.user.ak_groups.values_list("name", flat=True))}',
        },
    )
    verified_email, _ = ScopeMapping.objects.update_or_create(
        name="decanID verified email", defaults={
            "scope_name": "email",
            "expression": 'return {"email": request.user.email, "email_verified": request.user.attributes.get("email_verified", False) is True}',
        },
    )
    provider.property_mappings.set([*scopes, groups_mapping, verified_email])
    Application.objects.update_or_create(slug="imperium", defaults={
        "name": "Imperium", "provider": provider,
        "meta_launch_url": "https://imperium.decaneva.cloud/",
    })
    group, _ = Group.objects.get_or_create(name="imperium-admin", defaults={"is_superuser": False})
    User.objects.get(username="akadmin").ak_groups.add(group)
print("Configured Imperium public OIDC provider, strict callbacks, refresh scopes, and application administrator group.")
