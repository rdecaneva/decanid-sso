"""Provision Authentik identities for the approved production MTG roster.

Run inside Authentik with /tmp/mtg-prod-users.json present:
  ak shell < scripts/provision-mtg-tabletop-users.py
The mapping file includes only MTG IDs, emails, names and Authentik subjects.
"""
import json
import os
from pathlib import Path

from django.db import transaction
from authentik.core.models import Group, User

ISSUER = "https://sso.decaneva.cloud/application/o/mtg-tabletop/"
source = Path("/tmp/mtg-prod-users.json")
roster = json.loads(source.read_text())
if roster.get("version") != 1 or not isinstance(roster.get("users"), list):
    raise ValueError("Unsupported MTG user roster")

admins = Group.objects.get(name="mtg-tabletop-admins")
users = Group.objects.get(name="mtg-tabletop-users")
if admins.is_superuser or users.is_superuser:
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
        matches = list(User.objects.filter(email__iexact=email))
        if len(matches) > 1:
            raise ValueError(f"Multiple Authentik accounts match {email}; review manually")
        user = matches[0] if matches else None
        username_match = User.objects.filter(username__iexact=email).first()
        if user and user.attributes.get("mtg_tabletop_prod_user_id") not in (None, mtg_id):
            raise ValueError(f"Authentik account {email} is already mapped to another production MTG ID")
        if user and not user.is_active:
            raise ValueError(f"Authentik account {email} is inactive; review before migration")
        if not user:
            if username_match:
                raise ValueError(f"Username {email} exists with a different email; review manually")
            user = User.objects.create(
                username=email, name=row.get("name", "")[:150], email=email,
                type="internal", path="users/mtg-tabletop", is_active=True,
                attributes={"mtg_tabletop_prod_user_id": mtg_id, "email_verified": False},
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
        user.attributes = {**user.attributes, "mtg_tabletop_prod_user_id": mtg_id}
        user.save(update_fields=["attributes"])
        user.groups.remove(admins)
        users.users.add(user)
        if row.get("admin"):
            admins.users.add(user)
        mapping.append({"mtgUserId": mtg_id, "email": email, "authentikSub": str(user.pk)})

    # These groups authorize the production application. Restrict membership to
    # the complete approved production roster, removing any dev-only bootstrap
    # memberships while leaving all other Authentik groups untouched.
    production_subjects = {row["authentikSub"] for row in mapping}
    for group in [admins, users]:
        for extra in group.users.exclude(pk__in=production_subjects):
            group.users.remove(extra)

output = Path("/tmp/mtg-prod-authentik-map.json")
temporary = output.with_name(output.name + ".tmp")
descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(descriptor, "w") as stream:
    json.dump({"version": 1, "issuer": ISSUER, "users": mapping}, stream, indent=2)
os.replace(temporary, output)
print(f"Provisioned/mapped {len(mapping)} production account(s); private mapping written to {output}.")
