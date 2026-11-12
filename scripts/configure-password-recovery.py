"""Enable email-verified password recovery for decanID.
Run: docker compose exec -T server ak shell < scripts/configure-password-recovery.py
"""
from django.db import transaction
from authentik.brands.models import Brand
from authentik.flows.models import Flow, FlowStageBinding
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.models import PolicyBinding
from authentik.policies.password.models import PasswordPolicy
from authentik.stages.email.models import EmailStage
from authentik.stages.identification.models import IdentificationStage
from authentik.stages.prompt.models import Prompt, PromptStage
from authentik.stages.user_login.models import UserLoginStage
from authentik.stages.user_write.models import UserWriteStage

with transaction.atomic():
    flow, _ = Flow.objects.update_or_create(slug="decanid-password-recovery", defaults={
        "name": "decanID password recovery", "title": "Reset your password",
        "designation": "recovery", "authentication": "require_unauthenticated",
        "background": "",
    })

    identification, _ = IdentificationStage.objects.update_or_create(
        name="decanid-password-recovery-identification",
        defaults={"user_fields": ["email", "username"]},
    )
    identification.recovery_flow = flow
    identification.save(update_fields=["recovery_flow"])

    email, _ = EmailStage.objects.update_or_create(
        name="decanid-password-recovery-email",
        defaults={
            "use_global_settings": True,
            "activate_user_on_success": False,
            "token_expiry": "minutes=30",
            "recovery_max_attempts": 5,
            "recovery_cache_timeout": "minutes=10",
            "subject": "Reset your decanID password",
            "template": "email/password_reset.html",
        },
    )

    password_prompt, _ = Prompt.objects.update_or_create(
        name="decanid-password-recovery-password",
        defaults={
            "field_key": "password", "label": "New password", "type": "password",
            "required": True, "placeholder": "New password", "order": 0,
            "sub_text": "Use at least 8 characters.",
        },
    )
    repeat_prompt, _ = Prompt.objects.update_or_create(
        name="decanid-password-recovery-password-repeat",
        defaults={
            "field_key": "password_repeat", "label": "Confirm new password",
            "type": "password", "required": True,
            "placeholder": "Confirm new password", "order": 1,
        },
    )
    prompt_stage, _ = PromptStage.objects.get_or_create(name="decanid-password-recovery-prompt")
    prompt_stage.fields.set([password_prompt, repeat_prompt])
    policy = PasswordPolicy.objects.get(name="decanid-enrollment-password")
    prompt_stage.validation_policies.set([policy])

    user_write, _ = UserWriteStage.objects.update_or_create(
        name="decanid-password-recovery-write",
        defaults={"user_creation_mode": "never_create"},
    )
    user_login, _ = UserLoginStage.objects.get_or_create(
        name="decanid-password-recovery-login",
        defaults={"session_duration": "hours=10"},
    )

    bindings = []
    for order, stage in [
        (10, identification), (20, email), (30, prompt_stage),
        (40, user_write), (100, user_login),
    ]:
        binding, _ = FlowStageBinding.objects.update_or_create(
            target=flow, order=order,
            defaults={
                "stage": stage, "evaluate_on_plan": True,
                "re_evaluate_policies": order <= 20,
                "policy_engine_mode": "any", "invalid_response_action": "retry",
            },
        )
        bindings.append(binding)

    restored, _ = ExpressionPolicy.objects.update_or_create(
        name="decanid-password-recovery-skip-identification-on-restore",
        defaults={"expression": "return bool(request.context.get('is_restored', True))"},
    )
    PolicyBinding.objects.update_or_create(
        target=bindings[0], order=0,
        defaults={"policy": restored, "enabled": True, "negate": False, "timeout": 30},
    )

    auth_identification = IdentificationStage.objects.get(name="default-authentication-identification")
    auth_identification.recovery_flow = flow
    auth_identification.save(update_fields=["recovery_flow"])
    brand = Brand.objects.get(default=True)
    brand.flow_recovery = flow
    brand.save(update_fields=["flow_recovery"])

print("Configured decanID password recovery with 30-minute email links and the 8-character password policy.")
