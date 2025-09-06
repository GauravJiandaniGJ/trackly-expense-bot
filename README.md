# Trackly v2

Trackly v2 is a web-based expense tracker that allows users to log their expenses and upload invoices.

## Project Structure

```
.
├── activity-logs.md
├── activity-logs/
├── expense_analyzer.py
├── requirements.txt
├── sheets_logger.py
├── slack_receiver.py
├── static/
│   └── styles.css
├── templates/
│   ├── expense.html
│   ├── index.html
│   └── welcome.html
└── README.md
```

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    ```
2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    ```
3.  **Activate the virtual environment:**
    ```bash
    source venv/bin/activate
    ```
4.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Set up the environment variables:**
    Create a `.env` file in the root directory and add the following variables:
    ```
    SPREADSHEET_ID=<your-spreadsheet-id>
    GOOGLE_CREDS_B64=<your-base64-encoded-google-credentials>
    DROPBOX_ACCESS_TOKEN=<your-dropbox-access-token>
    SLACK_BOT_TOKEN=<your-slack-bot-token>
    PORT=5000
    ```
6.  **Run the application:**
    ```bash
    python3 slack_receiver.py
    ```

## Contribution Guidelines

Please follow the standard GitHub flow for contributions:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Submit a pull request.