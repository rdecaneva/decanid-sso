"""Grant the explicitly requested decanID account MTG dev access and write its subject link."""
import json
import os
from pathlib import Path

from authentik.core.models import Group, User

email = "decan0505@gmail.com"
matches = list(User.objects.filter(email__iexact=email))
if len(matches) != 1:
    raise ValueError(f"Expected exactly one Authentik account for the requested email; found {len(matches)}")
user = matches[0]
if not user.is_active:
    raise ValueError("The requested Authentik account must be active before granting app access")
admins = Group.objects.get(name="mtg-tabletop-admins")
users = Group.objects.get(name="mtg-tabletop-users")
dev_admins = Group.objects.get(name="mtg-dev-admin")
if admins.is_superuser or users.is_superuser or dev_admins.is_superuser:
    raise ValueError("MTG app admin group must not grant Authentik superuser rights")
admins.users.add(user)
users.users.add(user)
dev_admins.users.add(user)
output = Path("/tmp/mtg-tabletop-admin-link.json")
with open(output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
    json.dump({"version": 1, "issuer": "https://sso.decaneva.cloud/application/o/mtg-dev/", "users": [{
        "authentikSub": str(user.pk), "email": user.email.strip().lower(), "name": user.name.strip(), "admin": True,
    }]}, stream, indent=2)
print(f"Granted MTG Tabletop dev access and administration; private subject link written to {output}.")
