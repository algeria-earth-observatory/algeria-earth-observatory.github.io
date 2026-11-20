# Security policy

The Algeria Earth Observatory website is a static site served by GitHub Pages. It has no server-side code, user accounts, database or stored secrets. Third-party map tiles are loaded directly by the visitor's browser from their providers.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private vulnerability reporting: on the repository page, go to **Security → Report a vulnerability**. Include the affected URL or file, steps to reproduce, and the potential impact.

You can expect an acknowledgement within 7 days. We will keep you informed and credit you in the fix unless you prefer otherwise.

## In scope

- Cross-site scripting or content injection through catalog data, URL parameters or map popups
- Compromised or malicious dependencies
- Integrity of AEO-distributed files (checksum mismatches)
- Exposure of secrets in the repository or build logs

## Out of scope

- Availability of third-party services (NASA GIBS, OpenFreeMap, data providers)
- Content of external datasets — report errors through the metadata error form

## Practices

- No API keys or tokens are used by the website. Never commit secrets; GitHub Actions uses only the built-in `GITHUB_TOKEN` with minimal permissions.
- Dependencies are pinned to exact versions in `package.json` and locked in `package-lock.json`.
- Every AEO-hosted download has a SHA-256 checksum verified at build time.
