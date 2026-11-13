"""Create/reset-password-ready Authentik users from an approved MTG dev roster.

Run inside Authentik with /tmp/mtg-dev-users.json present:
  ak shell < scripts/provision-mtg-dev-users.py
The JSON mapping printed to stdout contains MTG IDs, email addresses and Authentik subjects only.
"""
import json
import os
from pathlib import Path

from django.db import transaction
from authentik.core.models import Group, User

source = Path("/tmp/mtg-dev-users.json")
roster = json.loads(source.read_text())
if roster.get("version") != 1 or not isinstance(roster.get("users"), list):
    raise ValueError("Unsupported MTG user roster")

dev_admins = Group.objects.get(name="mtg-dev-admin")
dev_users = Group.objects.get(name="mtg-dev-user")
if any(group.is_superuser for group in [dev_admins, dev_users]):
    raise ValueError("MTG access groups must not grant Authentik superuser rights")

normalized = set()
for row in roster["users"]:
    email = str(row.get("email", "")).strip().lower()
    if not row.get("mtgUserId") or "@" not in email or email in normalized:
        raise ValueError("Roster contains a missing ID, invalid email, or duplicate email")
    normalized.add(email)

mapping = []
with transaction.atomic():
    for row in roster["users"]:
        email = row["email"].strip().lower()
        mtg_id = row["mtgUserId"]
        existing = User.objects.filter(username=email).first()
        if existing and existing.attributes.get("mtg_dev_user_id") != mtg_id:
            raise ValueError(f"Authentik username {email} already exists; review and map it explicitly")
        if existing:
            user = existing
        else:
            user = User.objects.create(
                username=email, name=row.get("name", "")[:150], email=email,
                type="internal", path="users/mtg-dev", is_active=True,
                attributes={"mtg_dev_user_id": mtg_id, "email_verified": False},
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
        user.groups.remove(dev_admins, dev_users)
        (dev_admins if row.get("admin") else dev_users).users.add(user)
        user.attributes = {**user.attributes, "mtg_dev_user_id": mtg_id, "email_verified": False}
        user.save(update_fields=["attributes"])
        mapping.append({"mtgUserId": mtg_id, "email": email, "authentikSub": str(user.pk)})

output = Path("/tmp/mtg-dev-authentik-map.json")
with open(output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
    json.dump({"version": 1, "issuer": "https://sso.decaneva.cloud/application/o/mtg-dev/", "users": mapping}, stream, indent=2)
print(f"Provisioned {len(mapping)} account(s); private subject mapping written to {output}.")
