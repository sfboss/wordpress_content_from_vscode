# Connect this folder to WordPress

1. Replace `example.com` in `site.yaml` and `.env` with the real HTTPS site URL.
2. Sign in to WordPress as the user that should own the content.
3. Open **Users → Profile → Application Passwords**.
4. Name it `VS Code WordPress Factory`, click **Add New Application Password**, and copy the one-time password.
5. Put the username and generated password in this folder's `.env`. Do not use the normal wp-admin password.
6. Optional: put a Slack Incoming Webhook URL for `#general` in `SLACK_WEBHOOK_URL`.
7. From VS Code, run **Terminal → Run Task → Factory: 2 - Test connection** and enter this folder name.
8. Run **Lint Markdown**, **Preview sync plan**, then **Push site**.
9. Run **Verify live records**. Published URLs are fetched; drafts are confirmed by authenticated REST read-back.

No OAuth plugin is required. WordPress 5.6+ has revocable Application Passwords built in. Use HTTPS.

