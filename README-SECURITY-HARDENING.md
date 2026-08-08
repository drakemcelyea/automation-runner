# Automation Runner security-hardening package

This package layers security controls on top of the Alembic-enabled Automation Runner build.

## Included changes

- CSRF token endpoint and server-side CSRF enforcement for POST/PUT/PATCH/DELETE requests.
- Frontend fetch wrapper that obtains and sends CSRF tokens automatically and retries once after a stale-token response.
- Login failure throttling persisted in SQLite by source IP.
- Per-account failed-login tracking and temporary account lockout.
- Admin unlock action for temporarily locked accounts.
- Session configuration through environment variables, including cookie name, lifetime, SameSite policy, and HTTPS-only cookies.
- Fail-fast validation for missing/weak SESSION_SECRET values.
- Audit events for CSRF failures, account lockouts, IP throttling, login successes/failures, and admin unlocks.
- Alembic revision `0002_security_hardening` that adds lockout columns to `users` and creates the `login_throttles` table.

No passwords, CSRF tokens, session values, or vault secrets are written to the audit table.

## Expected one-time behavior

The session cookie name changes from Starlette's default `session` to `automation_runner_session` unless overridden. Existing browser sessions will therefore be logged out once after deployment. Users can immediately log back in.

## Before deployment

Back up the database:

```bash
sudo cp /var/lib/automation-runner/settings/auth.db \
  /var/lib/automation-runner/settings/auth.db.pre-security-hardening
```

Confirm the existing secret file contains a strong `SESSION_SECRET`:

```bash
sudo grep '^SESSION_SECRET=' /etc/automation-runner/automation-runner.env
```

Generate a replacement if necessary:

```bash
openssl rand -hex 32
```

Do not commit the real environment file to Git.

For current HTTP testing, leave:

```text
SESSION_HTTPS_ONLY=false
```

After TLS is deployed and HTTP access is disabled, change it to:

```text
SESSION_HTTPS_ONLY=true
```

## Build

```bash
cd /opt/automation-runner
sudo -u automationsvc podman build \
  --no-cache \
  -t localhost/automation-runner-security:latest \
  -f container/backend/ContainerFile \
  .
```

## Test deployment on port 8081

Use the same persistent mounts as the normal deployment. At minimum the auth database must be mounted:

```bash
sudo -u automationsvc podman run -d \
  --name automation-runner-security-test \
  --env-file /etc/automation-runner/automation-runner.env \
  -p 8081:8000 \
  -v /var/lib/automation-runner/settings:/var/lib/automation-runner/settings:Z \
  localhost/automation-runner-security:latest
```

The container runs `alembic upgrade head` before Uvicorn. Check:

```bash
sudo -u automationsvc podman logs automation-runner-security-test --tail 100
sudo -u automationsvc podman exec automation-runner-security-test alembic current
```

Expected Alembic revision:

```text
0002_security_hardening (head)
```

## Browser validation

1. Open `/ui` and log in normally.
2. Verify Users, Audit Log, Inventory, Playbooks, Runs, Settings, and Vault requests still work.
3. Log out and log back in; logout is now a CSRF-protected POST.
4. Enter a bad password five times for a test account. The account should become temporarily locked.
5. As an admin, open Users. The locked account should show `Locked` and an `Unlock` button.
6. Unlock it and verify login succeeds with the correct password.
7. Review Audit Log for `security.account_locked`, `user.unlock`, and failed `auth.login` events.

## CSRF validation with curl

Unsafe API requests now require both the signed session cookie and the CSRF header. To fetch a token manually:

```bash
curl -s -c /tmp/ar.cookies http://127.0.0.1:8081/csrf-token
```

A POST without the matching `X-CSRF-Token` should return HTTP 403 and an `X-CSRF-Error: 1` response header.

The browser UI handles this automatically.

## Login security defaults

- Account lockout: 5 failed attempts for 15 minutes.
- IP throttle: 30 failed attempts inside 5 minutes, blocked for 5 minutes.
- Session lifetime: 8 hours.
- SameSite: `lax`.
- HTTPS-only cookie: configurable and disabled by default to preserve local HTTP testing.

All values can be overridden using the variables in `deploy/automation-runner.env.example`.
