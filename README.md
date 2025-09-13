# Trackly: Slack Expense Tracker Bot

Trackly is a smart, conversational expense tracking bot for Slack. It allows users to log expenses through natural language messages in Slack or via a simple web interface. All expense data is automatically organized and stored in a Google Sheet.

## Features

-   **Slack Integration**: Log expenses by sending a message to the bot in Slack.
-   **Web Interface**: A user-friendly web form for detailed expense entry, including invoice uploads.
-   **Google Sheets Logging**: Automatically logs all expenses into a designated Google Sheet for easy tracking and analysis.
-   **Dropbox Integration**: Securely stores uploaded invoices in a Dropbox folder.
-   **Real-time Logging**: A live log viewer in the web UI to monitor bot activity and expense processing.
-   **Health Check**: An endpoint to monitor the application's status and configuration.

## Architecture

Trackly is built with a simple and effective architecture:

-   **Frontend**: A lightweight web interface built with Flask, HTML, and CSS.
-   **Backend**: A Python Flask server that handles requests from Slack and the web UI.
-   **Database**: A Google Sheet acts as the primary database for storing expense data.
-   **File Storage**: Dropbox is used for storing invoice files.
-   **Real-time Communication**: Flask-SocketIO is used to provide real-time log updates to the web UI.

```
+----------------+      +-------------------+      +-----------------+
|   Slack User   |----->|    Flask Server   |<---->|   Google Sheet  |
+----------------+      | (slack_receiver.py) |      +-----------------+
                        +-------------------+
                                  ^
                                  |
+----------------+      +-------------------+      +-----------------+
|    Web User    |----->|    Flask Server   |<---->|     Dropbox     |
+----------------+      | (slack_receiver.py) |      +-----------------+
                        +-------------------+
```

## Setup and Installation

Follow these steps to set up the project locally.

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd slack-expense-tracker-bot
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The application requires several credentials and environment variables to be set up.

### 1. Credentials Files

The following files contain sensitive credentials and **should not be committed to version control**. Ensure they are listed in your `.gitignore` file.

-   `client_secret.json`: Google Cloud client secrets.
-   `token.json`: Google API token, generated after the first authentication.
-   `trackly-*.json`: Google Service Account key (if used).
-   `encoded-key.txt`: Any other sensitive keys.

### 2. Environment Variables

Create a `.env` file in the root of the project and add the following variables. You can also set these as system environment variables.

```
# The ID of the Google Sheet where expenses will be logged
SPREADSHEET_ID=<your-google-spreadsheet-id>

# Your Google Cloud credentials, base64 encoded
GOOGLE_CREDS_B64=<your-base64-encoded-google-credentials>

# Your Dropbox access token
DROPBOX_ACCESS_TOKEN=<your-dropbox-access-token>

# Your Slack Bot User OAuth Token
SLACK_BOT_TOKEN=<your-slack-bot-token>

# The port for the Flask application
PORT=5000
```

## Usage

1.  **Run the Flask application:**
    ```bash
    source venv/bin/activate
    python slack_receiver.py
    ```
    The server will start on `http://localhost:5000`.

2.  **Expose your local server with ngrok:**
    Slack needs a public URL to send events to. Use a tool like [ngrok](https://ngrok.com/) to expose your local server.
    ```bash
    ngrok http 5000
    ```

3.  **Update Slack Request URL:**
    Copy the HTTPS forwarding URL from ngrok (e.g., `https://<unique-id>.ngrok.io`) and paste it into your Slack App's "Event Subscriptions" settings, followed by `/slack/events`.

## API Endpoints

| Method  | Route                    | Description                                                                                              |
| :------ | :----------------------- | :------------------------------------------------------------------------------------------------------- |
| `GET`   | `/`                      | Displays the welcome page (`welcome.html`).                                                              |
| `GET`   | `/health`                | Provides a health check of the application and its environment variables.                                |
| `GET`   | `/logs`                  | Renders a page (`index.html`) for displaying real-time application logs via WebSockets.                  |
| `GET`   | `/expense`               | Shows a form (`expense.html`) for logging expenses through the web interface.                            |
-   `POST`  | `/log_expense_from_web`  | Handles expense submissions from the web form.                                                           |
-   `POST`  | `/slack/events`          | The endpoint for receiving all events from Slack, including challenges and user messages.                |

## Contribution Guidelines

Please follow the standard GitHub flow for contributions:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
