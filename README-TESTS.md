# Automation Runner authentication/RBAC tests

This package adds isolated automated tests for:

- self-service registration creates pending viewer accounts
- pending/disabled accounts cannot authenticate
- successful login and session role reporting
- invalid passwords
- disabled-session invalidation
- unauthenticated endpoint protection
- viewer read-only authorization
- operator execution/syntax-check authorization
- admin-only inventory/playbook/settings/vault/users/audit authorization
- role changes taking effect without re-login
- administrator approval workflow
- administrator self-protection/final-admin protection
- audit logging of successful and failed logins

## Production safety

The tests do not use `/var/lib/automation-runner` or the production auth database. `tests/conftest.py` creates a temporary database/data/config tree under `/tmp` before importing the application.

## Build and run as a disposable test container

From the project root:

```bash
sudo -u automationsvc podman build \
  --no-cache \
  -t localhost/automation-runner-tests:latest \
  -f container/backend/ContainerFile.test \
  .

sudo -u automationsvc podman run --rm \
  localhost/automation-runner-tests:latest
```

A successful run ends with all tests passing and exit code 0.
