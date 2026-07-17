# User-provided Google OAuth

Deep Thought does not require or use a shared Google Cloud project during the
initial open-source release. Each user supplies a Desktop OAuth client created
in their own Google Cloud project.

## Google Cloud setup

1. Create a Google Cloud project.
2. Enable the Gmail API and Google Calendar API.
3. Configure Google Auth Platform with an External audience in Testing mode.
4. Add the Google account that will use Deep Thought as a test user.
5. Create an OAuth client with application type **Desktop app**.
6. Download the client JSON.

## Deep Thought setup

1. Open **Settings**.
2. Select **Add OAuth JSON** beside Gmail or Google Calendar.
3. Choose the downloaded Desktop OAuth JSON.
4. Select **Connect**.
5. Sign in to Google and approve the Gmail and Calendar permissions.

The JSON is validated to ensure that authorization and token exchange use
Google's official HTTPS endpoints. It is stored only on the local computer in
a permission-restricted application credentials directory. OAuth access and
refresh tokens are stored in the operating-system keyring when available, with
a mode-`0600` local-file fallback. Gmail and Calendar share one authorization.
