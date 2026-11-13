"""Configure the isolated MTG dev OIDC client and access groups.

Run: docker compose exec -T server ak shell < scripts/configure-mtg-dev.py
"""
from django.db import transaction
from authentik.core.models import Application, Group
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

slug = "mtg-dev"
origin = "https://mtg-dev.decaneva.cloud"

with transaction.atomic():
    signing_key = next(key for key in CertificateKeyPair.objects.exclude(key_data="")
                       if isinstance(key.private_key, RSAPrivateKey))
    provider, _ = OAuth2Provider.objects.update_or_create(client_id=slug, defaults={
        "name": "MTG Tabletop Dev", "client_type": "public", "client_secret": "",
        "authorization_flow": Flow.objects.get(slug="default-provider-authorization-implicit-consent"),
        "invalidation_flow": Flow.objects.get(slug="default-invalidation-flow"),
        "grant_types": ["authorization_code"],
        "_redirect_uris": [
            {"matching_mode": "strict", "url": origin + "/auth/callback", "redirect_uri_type": "authorization"},
            {"matching_mode": "strict", "url": origin + "/", "redirect_uri_type": "logout"},
        ],
        "issuer_mode": "per_provider", "signing_key": signing_key,
        "access_token_validity": "minutes=5", "include_claims_in_id_token": True,
    })
    mappings = [ScopeMapping.objects.get(managed=f"goauthentik.io/providers/oauth2/scope-{name}")
                for name in ["openid", "profile", "email"]]
    groups_mapping, _ = ScopeMapping.objects.update_or_create(name="decanID groups", defaults={
        "scope_name": "profile",
        "expression": 'return {"groups": sorted(group.name for group in request.user.all_groups())}',
    })
    provider.property_mappings.set([*mappings, groups_mapping])
    app, _ = Application.objects.update_or_create(slug=slug, defaults={
        "name": "MTG Tabletop Dev", "provider": provider, "meta_launch_url": origin + "/",
        "policy_engine_mode": "any",
    })
    shared, _ = Group.objects.get_or_create(name="decanid-admins", defaults={"is_superuser": False})
    admins, _ = Group.objects.get_or_create(name="mtg-dev-admin", defaults={"is_superuser": False})
    users, _ = Group.objects.get_or_create(name="mtg-dev-user", defaults={"is_superuser": False})
    if any(group.is_superuser for group in [shared, admins, users]):
        raise ValueError("MTG groups must not grant Authentik superuser rights")
    groups = [shared, admins, users]
    PolicyBinding.objects.filter(target=app, group__name__in=["mtg-tabletop-admins", "mtg-tabletop-users"]).delete()
    if PolicyBinding.objects.filter(target=app).exclude(group__name__in=[group.name for group in groups]).exists():
        raise ValueError("MTG dev application has unrelated access bindings; reconcile them first")
    for order, group in enumerate(groups, start=100):
        PolicyBinding.objects.update_or_create(target=app, group=group, defaults={
            "order": order, "enabled": True, "negate": False, "policy": None, "user": None,
        })

print("Configured the MTG dev provider, strict callback, decanID groups, and app access bindings.")
