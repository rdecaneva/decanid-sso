# decanID

Shared single sign-on at **https://sso.decaneva.cloud/**, powered by Authentik 2026.8.5 and PostgreSQL 16. Imperium uses decanID for account sign-in. Resend supplies SMTP delivery from **decanID <noreply@mail.decaneva.cloud>**.

## Deployment

Requirements: Docker with Compose v2, at least 2 CPU cores/2 GB RAM, and the shared `decan-cloud-nginx` ingress stack. The external Docker network `decan-cloud-services` must exist before starting this project.

```sh
# Once per host, if the shared ingress has not already created it:
docker network create decan-cloud-services

# On a fresh checkout, generate separate random values for both secret placeholders:
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
openssl rand -hex 32
# Put the generated values into PG_PASS and AUTHENTIK_SECRET_KEY in .env.

docker compose config --quiet
docker compose up -d
docker compose ps
```

Initial database migrations can take several minutes; startup health checks can temporarily report unhealthy until initialization completes. All three services should ultimately be healthy. Keep `AUTHENTIK_SECRET_KEY` stable across restarts and upgrades.

| Service | Purpose | Storage / network |
| --- | --- | --- |
| `server` | Login, portal, administration, OIDC, static branding | Private network plus shared ingress, alias `authentik-sso` |
| `worker` | Email delivery, tasks, blueprint reconciliation | Private Compose network |
| `postgresql` | Accounts, flows, provider configuration, sessions | Private Compose network; no published database port |

The Compose project name is `decanid-sso`. Restart policy is `unless-stopped`. Docker socket access is disabled; additional outposts must be managed separately.

## DNS, HTTPS, and Nginx

The `sso.decaneva.cloud` DNS A record must point to the current public ingress IP. This host's public IP was `172.113.63.197` when HTTPS was configured on November 5, 2026. TCP ports 80 and 443 forward to the Docker host at `192.168.1.102`; update public DNS if the ISP changes the address.

The sibling [`decan-cloud-nginx`](https://github.com/rdecaneva/decan-cloud-nginx) repository owns the HTTP/HTTPS listeners. Its route maps `sso.decaneva.cloud` to `authentik-sso:9000`. It terminates TLS, redirects HTTP to HTTPS, forwards WebSocket upgrades, and overwrites forwarded host/protocol/client-IP headers. The application's database and worker are not attached to the shared ingress network.

A trusted Let's Encrypt certificate was issued November 5, 2026, initially expiring February 3, 2027. The existing certificate service checks renewals hourly; both Nginx replicas detect changes and reload gracefully. Certificate state is stored in that stack's persistent volumes.

```sh
python3 ../decan-cloud-nginx/scripts/check-routes.py --trusted

# Retry issuance after correcting DNS or public port forwarding:
docker compose -f ../decan-cloud-nginx/compose.yaml restart certificates
```

Local HTTP remains at http://127.0.0.1:9001/; port 9001 avoids Portainer's port 9000. Local HTTPS at https://127.0.0.1:9443/ uses Authentik's own certificate, independently of the public Nginx certificate. Both local listeners bind to loopback.

```sh
# From another computer, for local troubleshooting:
ssh -L 9001:127.0.0.1:9001 <user>@<docker-host>
```

## Accounts and self-registration

Users can create an account at the enrollment link on the SSO login page, directly at https://sso.decaneva.cloud/if/flow/decanid-enrollment/, or using **Create decanID** in Imperium.

The `decanid-enrollment` flow collects a unique username, name, email, password, and password confirmation. Passwords require at least 12 characters. The user-write stage creates an **inactive regular internal user** in `users/decanid`, belonging only to `decanid-users`. The mandatory email stage sends a verification link valid for 30 minutes. Opening that link and pressing **Continue** activates the account, records `email_verified`, and completes sign-in. The confirmation prevents mail-link previews from completing enrollment automatically. Enrollment email resends are limited to five attempts per ten minutes for the stage's recovery limit.

Internal is Authentik’s portal-enabled user type: it provides the application dashboard and personal settings, not administrator privileges. New accounts do not receive Authentik administration or the `imperium-admin` group. Reapplying the enrollment script also corrects the type of accounts previously created by this flow, without replacing their IDs, passwords, or group memberships. Existing accounts and passwords are preserved. Signed-in users should sign out before opening the enrollment flow to create a different account.

From Imperium, registration preserves the OIDC authorization request, PKCE verifier, state, nonce, and intended return path. Its browser-bound pending login lasts one hour to allow time for email verification; ordinary sign-in retains its five-minute limit. Account verification returns through Imperium's normal callback. Complete the email link in the same browser that started Imperium registration; if you verify on another device, return to Imperium and sign in normally with the new account.

Reapply the idempotent enrollment configuration with:

```sh
docker compose exec -T server ak shell < scripts/configure-enrollment.py
```

Existing operators can use their own administrator account. The original bootstrap account is `akadmin`; its initially generated password was saved in the Git-ignored `.env.initial-admin` file. That file does not track later password changes. Initialize an administrator before exposing a fresh installation publicly.

## Imperium OIDC integration

| Setting | Value |
| --- | --- |
| Application / client ID | `imperium` |
| Issuer, including trailing slash | `https://sso.decaneva.cloud/application/o/imperium/` |
| Discovery | `https://sso.decaneva.cloud/application/o/imperium/.well-known/openid-configuration` |
| Callback | `https://imperium.decaneva.cloud/auth/callback` |
| Post-logout redirect | `https://imperium.decaneva.cloud/` |
| Scopes | `openid profile email offline_access` |
| App administrator group | `imperium-admin` |

Imperium’s provider uses `default-invalidation-flow` for logout, which clears the decanID SSO session as well as Imperium’s local session. The application-only `default-provider-invalidation-flow` has no logout stage and leaves the SSO session active; do not use it for this provider.

The public OAuth2 provider uses authorization code with PKCE S256, RSA-signed tokens, strict callback/logout URL matching, five-minute access tokens, and refresh tokens valid for up to ten hours. Imperium discovers authorization, token, JWKS, and logout endpoints and validates signatures, issuer, audience, subject, expiry, and initial nonce.

Tokens are stored on Imperium's server; its browser cookie is opaque, HttpOnly, SameSite=Lax, and Secure over HTTPS. Signed group claims grant application administration. The email scope reports `email_verified` only when the account has the explicit verified-email attribute set by enrollment. The existing Authentik `akadmin` account is assigned to `imperium-admin`; ordinary users must be granted that group explicitly if needed. Granting this group does not grant Authentik administration.

Imperium saves verified user subjects in server sessions and derives game ownership from the `(issuer, subject)` pair. Accounts have separate libraries across identities; no email/username-based ownership migration occurs. Existing browser-owned games can be linked from the original browser with **Link this browser's games**. Existing game data remains in Imperium's original `ti4-turn-tracker_game_data` volume.

```sh
docker compose exec -T server ak shell < scripts/configure-imperium.py
```

Application source and its own configuration are in the sibling `imperium` repository. Its Compose project name remains `ti4-turn-tracker` to retain the existing volume. Its application endpoint `/api/auth/register` starts registration; `/api/auth/login` starts ordinary sign-in.

## Resend SMTP

The sending domain `mail.decaneva.cloud` is verified in Resend's `us-east-1` region. Its DKIM, MX/SPF, TXT/SPF, and additional return-path CNAME records are verified. GoDaddy is the authoritative DNS provider; the existing root-domain DMARC policy is retained. Receiving and open/click tracking are disabled. Exact DNS values are recorded in [email/resend-dns.md](email/resend-dns.md).

| Authentik setting | Value |
| --- | --- |
| `AUTHENTIK_EMAIL__HOST` | `smtp.resend.com` |
| `AUTHENTIK_EMAIL__PORT` | `587` |
| `AUTHENTIK_EMAIL__USERNAME` | `resend` |
| `AUTHENTIK_EMAIL__PASSWORD` | Private domain-restricted sending key |
| `AUTHENTIK_EMAIL__USE_TLS` | `true` (STARTTLS) |
| `AUTHENTIK_EMAIL__USE_SSL` | `false` |
| `AUTHENTIK_EMAIL__TIMEOUT` | `30` seconds |
| `AUTHENTIK_EMAIL__FROM` | `decanID <noreply@mail.decaneva.cloud>` |

The key is named **decanID SMTP**, has sending-only permission, and is restricted to this domain. Settings are active in `.env`; `.env.resend-smtp` contains the private provisioned copy. Both have mode 600 and are ignored by Git. Resend management authorization is separate from the SMTP key and is not passed to Authentik.

Both `server` and `worker` load `.env`, so recreate both after email configuration changes:

```sh
docker compose up -d --no-deps server worker

# Native Authentik transport test:
docker compose exec -T worker ak test_email <your-address>

# Branded test, queued through the normal worker:
docker compose exec -T -e DECANID_TEST_RECIPIENT=<your-address> worker ak shell < scripts/send-test-email.py
```

Both the initial SMTP test and the updated branded decanID test were confirmed **delivered** by Resend and recorded as `email_sent` by Authentik. The native test command reported a result-handling error despite delivery; check the worker's event log and Resend delivery status before resending. The branded test helper queues the normal email task without waiting on that result-handling path.

SMTP configuration alone does not enable every email flow. Enrollment verification is explicitly configured here; a separate account recovery flow has not been configured.

## Login and email branding

The live brand is **decanID**, with an original rook/keyhole mark, ivory `#f6f4ed`, charcoal `#202823`, forest `#28533b`, and serif wordmark. Login uses a centered form with no side illustration or slogan. Its loading overlay is transparent while preserving the native spinner and click blocking. Controls remain accessible on desktop, tablet, and phone.

[branding/](branding/) contains SVG marks, favicon, CSS, and the PNG email wordmark. It is mounted read-only at `/web/dist/custom` in the server. Reapply saved brand CSS/settings after editing them:

```sh
docker compose exec -T server ak shell < scripts/configure-branding.py
```

The first branding application backed up the old brand and login presentation settings to `/data/decanid-branding-backup.json` (mode 600). Authentication stages and provider permissions are independent of these presentation settings.

[templates/email/](templates/email/) overrides the email base, transport test, account confirmation, and password reset templates. Native invitation and notification templates inherit the branded base. Matching plain-text alternatives accompany custom message bodies. Buttons, copy, links, and the ivory/forest palette match login; HTML uses email-compatible tables and inline styles.

The PNG wordmark is embedded as `cid:logo`, allowing email clients to display it without SVG support or an external image fetch. Both containers mount the PNG over Authentik's existing email-logo asset path `/web/dist/assets/icons/icon_left_brand.png`, and mount `templates/email` read-only under `/templates/email`. These asset/template paths should be reviewed when upgrading Authentik. Recreate server and worker after editing templates to clear Django's template cache.

See [branding/README.md](branding/README.md) for the design notes. Preview screenshots are local artifacts under `.taste-skill/` and are not required to run the service.

## Operations, persistence, and backups

```sh
docker compose ps
docker compose logs --tail=100 server worker
docker compose stop
docker compose up -d
docker compose down
```

Named volumes retain PostgreSQL data (`database`), uploaded data (`data`), certificates (`certs`), and custom templates (`custom-templates`). The versioned email overrides are bind mounts layered into the template volume. `docker compose down` preserves volumes; **`docker compose down -v` permanently deletes the installation data**.

Back up PostgreSQL, the data volume, `.env`, and any private bootstrap/SMTP files securely. Database backups include account credentials and session tokens. Preserve the secret key and database password when restoring. Back up the shared ingress's Let's Encrypt volumes separately. Do not commit secrets or dump expanded `docker compose config` output into logs.

For upgrades, back up first, review Authentik's release notes and official Compose changes, update the pinned tag, pull, recreate, and repeat health, proxy, sign-in, registration/email-verification, and logout checks. The setup is based on the [official Docker Compose installation](https://docs.goauthentik.io/install-config/install/docker-compose), adapted for the shared proxy, named storage, and versioned branding.

## Verification

The Imperium migration passed its application test suite and production build. Browser checks cover sign-in/admin controls at 1440, 768, and 390 pixels; live tests exercised OIDC login, application administrator claims, token refresh, local logout, and the Authentik end-session endpoint. Public ingress routes passed trusted HTTPS checks.

```sh
python3 ../decan-cloud-nginx/scripts/check-routes.py --trusted
cd ../imperium
npm test
npm run build
BASE_URL=http://127.0.0.1:5173 node tests/auth-browser.mjs
```

Registration should reject short passwords, keep accounts inactive until the email link is followed, record `email_verified`, return Imperium signups through its OIDC callback, and leave new users without administrator privileges. Use a separate test account and remove only that account after verification; do not repurpose an operator account.

The live enrollment check passed email verification, ordinary-user authorization, and the Imperium callback; its temporary test account was removed afterward. The updated branded Gmail test was confirmed delivered.

### Session and portal regression checks

Self-registered decanID accounts use Authentik's ordinary `internal` user type so they can open the application dashboard and personal settings. This does not assign superuser rights, administrative roles, or the `imperium-admin` group. Accounts created by the earlier external-user enrollment configuration are repaired in place by `scripts/configure-enrollment.py`.

Imperium's logout clears the local application session and the Authentik SSO session. This permits a subsequent **Create decanID** action; enrollment intentionally still requires an unauthenticated session. A signed-in user who opens an enrollment URL directly should sign out first.

`../imperium/tests/sso-session-browser.mjs` checks portal access, denied administrator APIs, full SSO logout, and registration after logout. Supply a dedicated regular test account through `SSO_TEST_USERNAME` and `SSO_TEST_PASSWORD` in the environment, then run the script from the Imperium directory. It does not create users or games. A live run passed all checks; its separately provisioned temporary test account was removed.
