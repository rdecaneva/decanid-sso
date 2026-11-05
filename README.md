# decanid-sso

Authentik at https://sso.decaneva.cloud/, based on the [official Docker Compose configuration](https://docs.goauthentik.io/install-config/install/docker-compose), downloaded November 5, 2026. Uses Authentik 2026.8.5 and PostgreSQL 16.

```sh
docker compose up -d
```

Public certificate issuance is pending as of November 5, 2026: DNS resolves to `172.91.65.235`, while this host reports public IP `172.113.63.197`; Let’s Encrypt timed out reaching TCP port 80. Confirm the public ingress IP, correct DNS if needed, and forward TCP ports 80/443 to `192.168.1.102`. The proxy currently serves a temporary self-signed certificate for SSO.

After fixing public connectivity, trigger issuance and validate trusted HTTPS:

```sh
docker compose -f ../decan-cloud-nginx/compose.yaml restart certificates
python3 ../decan-cloud-nginx/scripts/check-routes.py --trusted
```

First startup runs database migrations and can take several minutes. Check `docker compose ps` until all services are healthy.

Sign in at https://sso.decaneva.cloud/ as `akadmin`. The initial password for this deployment is in the private, Git-ignored `.env.initial-admin` file; change it after signing in. Fresh installations must initialize the administrator before exposing the hostname.

Local access remains available at http://localhost:9001/. HTTPS is available at https://localhost:9443/ with a self-signed certificate. Port 9001 avoids Portainer on port 9000.

Ports bind to loopback. For access from another computer:

```sh
ssh -L 9001:127.0.0.1:9001 <user>@<docker-host>
```

Then open the localhost URL on your computer.

The generated `.env` is private (mode 600) and ignored by Git. On a fresh checkout, copy `.env.example` to `.env` and replace each secret placeholder with a separate `openssl rand -hex 32` result. Keep the secret key stable and back it up securely.

Persistent Docker volumes hold the database, data, certificates, and templates. Docker socket access is disabled; manage outposts manually if needed.

```sh
docker compose ps
docker compose logs --tail=100 server worker
docker compose stop
docker compose down
```

`down` preserves volumes. `docker compose down -v` permanently deletes installation data.

The server joins the external `decan-cloud-services` Docker network as `authentik-sso`. Create that network before starting on a fresh host. The shared `decan-cloud-nginx` repository routes `sso.decaneva.cloud` to `authentik-sso:9000`, terminates HTTPS, forwards WebSockets and client headers, and automatically renews its Let’s Encrypt certificate. The database and worker remain on the private Compose network.

SMTP and service integrations are not configured yet.
