# Selenium tests

## Authenticated tests

Authenticated Selenium tests use `logged_in_driver` and require:

- `ADMIN_PASSWORD`: password for `ADMIN_EMAIL`.
- `ADMIN_TOTP_SECRET`: base32 TOTP seed from the authenticator app when the account has MFA enabled.

Optional variables:

- `ADMIN_EMAIL`: defaults to `tiago.sasaki@gmail.com`.
- `BASE_URL`: defaults to `https://smartlic.tech`.
- `HEADLESS`: defaults to `true`.

`ADMIN_TOTP_SECRET` must be provided through the local environment or CI secrets. Never commit the secret value.
