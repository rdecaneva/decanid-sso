"""Read-only check that MTG dev's email-based Authentik usernames are unused."""
import json
from pathlib import Path
from authentik.core.models import User

roster = json.loads(Path("/tmp/mtg-dev-users.json").read_text())
collisions = [row for row in roster.get("users", [])
              if User.objects.filter(username=row.get("email", "").strip().lower()).exists()]
print(json.dumps({"roster_count": len(roster.get("users", [])), "collision_count": len(collisions)}))
