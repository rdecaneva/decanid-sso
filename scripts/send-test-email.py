"""Queue a branded email through Authentik's normal email worker.
Set DECANID_TEST_RECIPIENT with docker compose exec -e before running this in ak shell.
"""
import os
from authentik.stages.email.utils import TemplateEmailMessage
from authentik.stages.email.tasks import send_mails
recipient = os.environ["DECANID_TEST_RECIPIENT"]
message = TemplateEmailMessage(
    subject="decanID — Email setup confirmed",
    to=[("", recipient)],
    template_name="email/setup.html",
    template_context={},
)
send_mails(None, message)
print("Queued the branded decanID email through the normal worker.")
