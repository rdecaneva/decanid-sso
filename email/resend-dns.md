# Resend sending domain

Sender: `decanID <noreply@mail.decaneva.cloud>`.
Region: US East (N. Virginia). Sending enabled, receiving disabled; open/click tracking disabled.

Open https://resend.com/domains/803a8315-d888-4809-913c-e05f7d73ed80 and choose **Auto Configure** to review and approve these DNS additions in GoDaddy. Existing root-domain mailbox and DMARC records should remain unchanged.

Names below are relative to the GoDaddy zone `decaneva.cloud`. Use its default TTL (or 600 seconds).

```text
DNS Records to configure:

DKIM (TXT):
  Name: resend._domainkey.mail
  Value: p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDe3WkiuScZs5EO08aK3PaHKN1vH7AG2bJfiXuJgSYz1GQ8PCz32n59THUcXobeCM04SA0jN/p+6TUSH91898LlFXJD2dmJ1HVYGu08eFJODcFdO/YYhhi3YGcMKtuAotmLyVgchqMUGnpx44duqHuLIgsuGzjVg51mXg8tdTx4jwIDAQAB
  TTL: Auto
  Status: verified

SPF (MX):
  Name: send.mail
  Value: feedback-smtp.us-east-1.amazonses.com
  TTL: Auto
  Status: verified
  Priority: 10

SPF (TXT):
  Name: send.mail
  Value: v=spf1 include:amazonses.com ~all
  TTL: Auto
  Status: verified

SPF (CNAME):
  Name: rsend.mail
  Value: send.forge.rmta.net
  TTL: Auto
  Status: verified
```

Domain and all listed DNS records are verified. SMTP is active in Authentik; the initial test was confirmed delivered by Resend.
