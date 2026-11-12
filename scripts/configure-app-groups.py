"""Provision shared administrators and per-app access groups.

Run inside Authentik: ak shell < scripts/configure-app-groups.py
Set DECANID_APP_SLUG for another already-configured OIDC application.
Only Orbit's first run preserves the formerly unrestricted human users.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from django.db import transaction
from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping
from authentik.policies.expression.models import ExpressionPolicy

slug = os.environ.get("DECANID_APP_SLUG", "imperium")
if not slug or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug):
    raise ValueError("Use an application slug containing lowercase letters, numbers and hyphens")

with transaction.atomic():
    app = Application.objects.get(slug=slug)
    provider = OAuth2Provider.objects.get(pk=app.provider_id)
    names = ["orbit-admins", "orbit-users"] if slug == "imperium" else ["decanid-admins", f"{slug}-admin", f"{slug}-user"]
    bindings = PolicyBinding.objects.filter(target=app)
    # Do not silently change the meaning of an existing access policy.
    if bindings.exclude(group__name__in=names).exists():
        raise ValueError("Application has other access bindings; reconcile them before applying group access")

    snapshot = {
        "application": slug, "policy_engine_mode": app.policy_engine_mode,
        "bindings": list(bindings.values("order", "group__name", "enabled", "negate")),
        "groups": list(Group.objects.filter(name__in=names).values("name", "is_superuser", "attributes")),
        "memberships": {u.username: list(u.groups.values_list("name", flat=True))
                        for u in User.objects.filter(type__in=["internal", "external"])},
        "provider_mappings": list(provider.property_mappings.values_list("name", flat=True)),
        "enrollment_policy": list(ExpressionPolicy.objects.filter(name="decanid-enrollment-mark-verified").values("name", "expression")),
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = Path(f"/data/decanid-{slug}-groups-before-{stamp}.json")
    with open(backup, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
        json.dump(snapshot, output, indent=2)

    shared, created = Group.objects.get_or_create(name="decanid-admins", defaults={"is_superuser": False})
    admin, _ = Group.objects.get_or_create(name="orbit-admins" if slug == "imperium" else f"{slug}-admin", defaults={"is_superuser": False})
    users, _ = Group.objects.get_or_create(name="orbit-users" if slug == "imperium" else f"{slug}-user", defaults={"is_superuser": False})
    if any(group.is_superuser for group in [shared, admin, users]):
        raise ValueError("Application groups must not grant Authentik superuser rights")
    if created:
        # Bootstrap only the known existing operator, never all app administrators.
        User.objects.get(username="akadmin").groups.add(shared)

    if slug == "imperium" and not users.attributes.get("decanid_access_initialized"):
        if bindings.exists():
            raise ValueError("Cannot automatically preserve users for an already restricted application")
        users.users.add(*User.objects.filter(type__in=["internal", "external"]))
        users.attributes["decanid_access_initialized"] = True
        users.save(update_fields=["attributes"])

    mapping, _ = ScopeMapping.objects.update_or_create(name="decanID groups", defaults={
        "scope_name": "profile",
        "expression": 'return {"groups": sorted(group.name for group in request.user.all_groups())}',
    })
    provider.property_mappings.remove(*ScopeMapping.objects.filter(name=f"{app.name} groups"))
    provider.property_mappings.add(mapping)
    app.policy_engine_mode = "any"
    app.save(update_fields=["policy_engine_mode"])
    for order, group in enumerate([admin, users] if slug == "imperium" else [shared, admin, users], start=100):
        PolicyBinding.objects.update_or_create(target=app, group=group, defaults={
            "order": order, "enabled": True, "negate": False,
            "policy": None, "user": None,
        })

    if slug == "imperium":
        # Enrollment grants access only after email verification, never admin rights.
        # Updating this policy avoids rebuilding or disturbing the enrollment flow.
        verified = ExpressionPolicy.objects.filter(name="decanid-enrollment-mark-verified").first()
        if verified:
            verified.expression = '''plan = request.context.get("flow_plan")
user = plan.context.get("pending_user") if plan else None
if not user or not user.is_active:
    return False
from authentik.core.models import Group
group = Group.objects.get(name="orbit-users")
if group.is_superuser:
    return False
user.groups.add(group)
user.attributes["email_verified"] = True
user.save(update_fields=["attributes"])
return True'''.replace('orbit-users', users.name)
            verified.save(update_fields=["expression"])

    if os.environ.get("DECANID_GROUPS_DRY_RUN") == "1":
        transaction.set_rollback(True)

print(f"{'Dry run' if os.environ.get('DECANID_GROUPS_DRY_RUN') == '1' else 'Configured'} {slug}: shared administrators, app administrators and general users. Backup: {backup}")
