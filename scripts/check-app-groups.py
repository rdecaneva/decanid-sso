"""Verify Orbit access and enrollment groups; all test users are rolled back.
Run: docker compose exec -T server ak shell < scripts/check-app-groups.py
"""
from types import SimpleNamespace
from uuid import uuid4

from django.db import transaction
from django.test import RequestFactory
from authentik.core.models import Application, Group, User
from authentik.policies.engine import PolicyEngine
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.types import PolicyRequest
from authentik.providers.oauth2.models import ScopeMapping

app = Application.objects.get(slug="imperium")
mapping = ScopeMapping.objects.get(name="decanID groups")
player_group = "orbit-users"
verified = ExpressionPolicy.objects.get(name="decanid-enrollment-mark-verified")

with transaction.atomic():
    user = User.objects.create(username="group-check-" + uuid4().hex, type="internal", is_active=True)
    for names, allowed in [([], False), (["decanid-users"], False),
                           ([player_group], True), (["orbit-admins"], True),
                           (["decanid-admins"], False)]:
        user.groups.set(Group.objects.filter(name__in=names))
        engine = PolicyEngine(app, user)
        engine.use_cache = False
        assert engine.build().passing is allowed, (names, "access mismatch")
        request = RequestFactory().get("/")
        request.user = user
        assert mapping.evaluate(user, request)["groups"] == sorted(names), names
        assert not user.is_superuser, "App group granted Authentik administration"

    user.groups.clear()
    user.is_active = False
    user.save(update_fields=["is_active"])
    request = PolicyRequest(user)
    request.context["flow_plan"] = SimpleNamespace(context={"pending_user": user})
    assert not verified.passes(request).passing, "Unverified account received app access"
    assert not user.groups.exists()
    user.is_active = True
    user.save(update_fields=["is_active"])
    assert verified.passes(request).passing, "Verified enrollment failed"
    assert list(user.groups.values_list("name", flat=True)) == [player_group]
    assert user.attributes["email_verified"] is True
    assert not user.is_superuser
    transaction.set_rollback(True)

print("PASS: shared/admin/user access, denied unassigned users, signed group mapping, verified enrollment, no Authentik admin grants; test users rolled back.")
