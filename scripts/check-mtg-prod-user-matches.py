"""Read-only preflight for MTG production account provisioning."""
import json
from pathlib import Path
from authentik.core.models import Application, User

roster = json.loads(Path("/tmp/mtg-prod-users.json").read_text())
if roster.get("version") != 1 or not isinstance(roster.get("users"), list):
    raise ValueError("Unsupported production roster")

counts = {"roster": len(roster["users"]), "one_email_match": 0, "no_email_match": 0,
          "duplicate_email_matches": 0, "linked_to_other_mtg_id": 0, "username_conflicts": 0}
for row in roster["users"]:
    email = row["email"].strip().lower()
    matches = list(User.objects.filter(email__iexact=email))
    if len(matches) > 1:
        counts["duplicate_email_matches"] += 1
    elif len(matches) == 1:
        counts["one_email_match"] += 1
        mapped = matches[0].attributes.get("mtg_tabletop_prod_user_id")
        if mapped and mapped != row["mtgUserId"]:
            counts["linked_to_other_mtg_id"] += 1
    else:
        counts["no_email_match"] += 1
    if User.objects.filter(username=email).exclude(email__iexact=email).exists():
        counts["username_conflicts"] += 1

print(json.dumps({**counts, "mtg_tabletop_application_exists": Application.objects.filter(slug="mtg-tabletop").exists()}))
