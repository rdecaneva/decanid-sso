"""Enable decanID self-registration with mandatory email verification.
Run: docker compose exec -T server ak shell < scripts/configure-enrollment.py
"""
from django.db import transaction
from authentik.core.models import Group
from authentik.flows.models import Flow, FlowStageBinding
from authentik.policies.models import PolicyBinding
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.password.models import PasswordPolicy
from authentik.stages.prompt.models import Prompt, PromptStage
from authentik.stages.user_write.models import UserWriteStage
from authentik.stages.user_login.models import UserLoginStage
from authentik.stages.email.models import EmailStage
from authentik.stages.identification.models import IdentificationStage

with transaction.atomic():
    flow, _ = Flow.objects.update_or_create(slug="decanid-enrollment", defaults={
        "name": "Create decanID", "title": "Create your decanID", "designation": "enrollment",
        "authentication": "require_unauthenticated", "background": "",
    })
    fields = []
    for order, (key, label, kind) in enumerate([
        ("username", "Username", "username"), ("name", "Name", "text"),
        ("email", "Email address", "email"), ("password", "Password", "password"),
        ("password_repeat", "Confirm password", "password"),
    ]):
        field, _ = Prompt.objects.update_or_create(name="decanid-enrollment-"+key, defaults={
            "field_key": key, "label": label, "type": kind, "required": True,
            "placeholder": label, "order": order,
            "sub_text": "Use at least 12 characters." if key == "password" else "",
        })
        fields.append(field)
    prompt, _ = PromptStage.objects.get_or_create(name="decanid-enrollment-details")
    prompt.fields.set(fields)
    password, _ = PasswordPolicy.objects.update_or_create(name="decanid-enrollment-password", defaults={
        "length_min": 12, "check_static_rules": True, "check_have_i_been_pwned": False,
        "error_message": "Use a password with at least 12 characters.",
    })
    prompt.validation_policies.set([password])
    group, _ = Group.objects.get_or_create(name="decanid-users", defaults={"is_superuser": False})
    assert not group.is_superuser, "Enrollment group must not grant administration"
    write, _ = UserWriteStage.objects.update_or_create(name="decanid-enrollment-create", defaults={
        "user_creation_mode": "always_create", "create_users_as_inactive": True,
        "create_users_group": group, "user_type": "external", "user_path_template": "users/decanid",
    })
    email, _ = EmailStage.objects.update_or_create(name="decanid-enrollment-verify-email", defaults={
        "use_global_settings": True, "activate_user_on_success": True,
        "template": "email/account_confirmation.html", "subject": "Verify your email for decanID",
        "token_expiry": "minutes=30", "recovery_max_attempts": 5, "recovery_cache_timeout": "minutes=10",
    })
    login, _ = UserLoginStage.objects.update_or_create(name="decanid-enrollment-login", defaults={"session_duration": "hours=10"})
    for order, stage in [(10, prompt), (20, write), (30, email), (50, login)]:
        binding, _ = FlowStageBinding.objects.update_or_create(target=flow, order=order, defaults={
            "stage": stage, "evaluate_on_plan": False, "re_evaluate_policies": True,
        })
        if stage == login:
            verified, _ = ExpressionPolicy.objects.update_or_create(name="decanid-enrollment-mark-verified", defaults={
                "expression": '''plan = request.context.get("flow_plan")
user = plan.context.get("pending_user") if plan else None
if not user or not user.is_active:
    return False
user.attributes["email_verified"] = True
user.save(update_fields=["attributes"])
return True''',
            })
            PolicyBinding.objects.update_or_create(target=binding, order=0, defaults={"policy": verified, "enabled": True})
    IdentificationStage.objects.filter(name="default-authentication-identification").update(enrollment_flow=flow)
print("Configured decanID enrollment with inactive accounts, mandatory email verification, and no administrator grants.")
