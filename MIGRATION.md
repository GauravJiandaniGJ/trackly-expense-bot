# Application Migration Guide

This guide provides instructions for migrating the Trackly application's connections to new accounts for Google, Dropbox, and Slack.

## 1. Google Drive & Sheets Migration

The goal is to move your files, especially the spreadsheet your bot writes to, from the old Google account to the new one.

**Steps:**

1.  **Share Data:** From your current Google account, share all relevant files and folders in Google Drive with your new Google account. Make sure to give the new account "Editor" permissions.
2.  **Transfer Ownership:**
    *   Log in to your **new** Google account.
    *   Find the shared files/folders from the old account.
    *   Create a copy of the shared spreadsheet. This is important because the copy will be owned by your new account and will have a new "Spreadsheet ID".
3.  **Update Application Configuration:**
    *   You will need to go through the Google Cloud authentication process again with your **new** Google account to generate a new `client_secret.json` and `token.json`.
    *   Update the `SPREADSHEET_ID` in your application's environment variables to the ID of the **newly copied** spreadsheet.

## 2. Dropbox Migration

This process is for moving any files your application might be using from one Dropbox account to another.

**Steps:**

1.  **Share Data:** From your current Dropbox account, create a shared folder containing all the files you need to migrate. Invite your new Dropbox account to this folder.
2.  **Move Files:** Log in to your **new** Dropbox account. Accept the shared folder invitation. Move the contents from the shared folder into a private folder within your new account. This will make the new account the owner.
3.  **Update Application Configuration:**
    *   You will need to generate a new Dropbox access token for your new account.
    *   Update the `DROPBOX_ACCESS_TOKEN` in your application's environment variables with the new token.

## 3. Slack Workspace Migration

You can't directly "move" a Slack app from one workspace to another. You have to recreate it.

**Steps:**

1.  **Create a New Slack App:** In your **new** Slack workspace, go to the Slack API website and create a new app.
2.  **Copy Configuration:** Manually copy all the settings from your old app to the new one. This includes permissions (scopes), event subscriptions, bot user settings, etc.
3.  **Install the New App:** Install the new app into your new workspace. This will generate a new set of credentials.
4.  **Update Application Configuration:**
    *   Copy the new "Bot User OAuth Token" from your new Slack app's settings.
    *   Update the `SLACK_BOT_TOKEN` in your application's environment variables with this new token.
5.  **Update Request URL:** If you are using ngrok, your public URL will likely change every time you restart it. You will need to update the "Request URL" in your Slack App's "Event Subscriptions" settings with the new ngrok URL.

---

**Important:** After performing these migrations, make sure to restart your Flask application to ensure it loads the new environment variables and credentials.
