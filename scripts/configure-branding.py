"""Apply decanID's versioned assets and CSS using Authentik's native branding fields.
Run: docker compose exec -T server ak shell < scripts/configure-branding.py
"""
import json
import os
from pathlib import Path
from django.db import transaction
from authentik.brands.models import Brand
from authentik.flows.models import Flow

backup = Path("/data/decanid-branding-backup.json")
if not backup.exists():
    current = Brand.objects.get(default=True)
    fields = ["branding_title", "branding_logo", "branding_favicon", "branding_default_flow_background", "branding_custom_css", "attributes"]
    data = {"brand_uuid": str(current.pk), "brand": {name: getattr(current, name) for name in fields}, "flows": list(Flow.objects.filter(slug="default-authentication-flow").values("slug", "title", "background"))}
    with open(backup, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as handle:
        json.dump(data, handle, indent=2)

with transaction.atomic():
    brand = Brand.objects.get(default=True)
    brand.branding_title = "decanID"
    brand.branding_logo = "/static/dist/custom/decanid-wordmark.svg"
    brand.branding_favicon = "/static/dist/custom/decanid-favicon.svg"
    brand.branding_default_flow_background = ""
    brand.branding_custom_css = Path("/web/dist/custom/decanid.css").read_text()
    attributes = dict(brand.attributes or {})
    settings = attributes.setdefault("settings", {})
    theme = settings.setdefault("theme", {})
    theme["base"] = "light"
    brand.attributes = attributes
    brand.save()
    Flow.objects.filter(slug="default-authentication-flow").update(title="", background="")
print("Applied decanID branding.")
