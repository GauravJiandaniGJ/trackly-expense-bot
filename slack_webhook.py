import os
import datetime
import json
import requests
import re
from flask import Flask, request, jsonify
import traceback
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import tempfile

app = Flask(__name__)

# Validate required environment variables on startup
required_env_vars = [
    'SPREADSHEET_ID',
    'GOOGLE_CREDS_B64',  # Using base64 encoded credentials
    'DROPBOX_ACCESS_TOKEN',
    'SLACK_BOT_TOKEN',
    'PORT'
]

missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars and os.environ.get('FLASK_DEBUG', 'false').lower() != 'true':
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

@app.route('/')
def health_check():
    try:
        # Test basic functionality
        port = os.environ.get('PORT', '5000')
        env_status = {
            'status': 'ok',
            'app': 'slack-expense-tracker',
            'time': datetime.datetime.utcnow().isoformat(),
            'port': port,
            'environment_vars': {var: 'set' if os.environ.get(var) else 'missing' for var in required_env_vars}
        }
        return jsonify(env_status), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
DROPBOX_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"
DROPBOX_ACCESS_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN")

def get_google_creds():
    import base64
    # Decode base64 encoded credentials
    creds_json = base64.b64decode(os.environ.get("GOOGLE_CREDS_B64")).decode('utf-8')
    creds_dict = json.loads(creds_json)
    return Credentials.from_authorized_user_info(creds_dict, SCOPES)

def get_month_sheet_name(timestamp):
    return timestamp.strftime("%B")

def get_currency_and_amount(text):
    match = re.search(r'([\₹$€£])\s?(\d+(?:[.,]\d{1,2})?)', text)
    if match:
        symbol = match.group(1)
        amount = match.group(2).replace(',', '')
        currency_map = {
            "$": "USD",
            "₹": "INR",
            "€": "EUR",
            "£": "GBP"
        }
        currency = currency_map.get(symbol, "Not found")
        return amount, currency
    return "Not found", "Not found"

def extract_text_from_image(file_path):
    try:
        return pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        print("OCR failed:", e)
        return None

def upload_to_dropbox(file_content, filename):
    headers = {
        "Authorization": f"Bearer {DROPBOX_ACCESS_TOKEN}",
        "Dropbox-API-Arg": json.dumps({
            "path": f"/{filename}",
            "mode": "add",
            "autorename": True,
            "mute": False
        }),
        "Content-Type": "application/octet-stream"
    }
    response = requests.post(DROPBOX_UPLOAD_URL, headers=headers, data=file_content)
    if response.status_code == 200:
        metadata = response.json()
        file_path = metadata["path_display"]
        shared_link_resp = requests.post(
            "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings",
            headers={
                "Authorization": f"Bearer {DROPBOX_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            },
            data=json.dumps({"path": file_path})
        )
        if shared_link_resp.ok:
            url = shared_link_resp.json().get("url", "")
            return url.replace("?dl=0", "?dl=1")
    return None

def append_to_google_sheet(row_data, sheet_name):
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    # Ensure sheet tab exists
    existing_sheets = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_titles = [s["properties"]["title"] for s in existing_sheets["sheets"]]

    if sheet_name not in sheet_titles:
        sheet.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [{
                    "addSheet": {
                        "properties": {
                            "title": sheet_name
                        }
                    }
                }]
            }
        ).execute()
        print(f"Created new sheet: {sheet_name}")

    # Append row
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": [row_data]}
    ).execute()

@app.route("/slack/events", methods=["POST", "OPTIONS"])
def slack_events():
    try:
        print("\n=== NEW REQUEST RECEIVED ===")

        # Log request details
        print(f"Method: {request.method}")
        print(f"Headers: {dict(request.headers)}")
        print(f"Content-Type: {request.content_type}")

        # Handle CORS preflight
        if request.method == "OPTIONS":
            print("Handling CORS preflight request")
            response = app.make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add("Access-Control-Allow-Headers", "Content-Type")
            response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
            return response

        # Ensure request is JSON
        if not request.is_json:
            error_msg = "ERROR: Request is not JSON"
            print(error_msg)
            return {"error": error_msg}, 400, {"Content-Type": "application/json"}

        # Parse JSON data
        try:
            data = request.get_json()
            print(f"Request data: {json.dumps(data, indent=2)}")
        except Exception as e:
            error_msg = f"ERROR parsing JSON: {str(e)}"
            print(error_msg)
            return {"error": error_msg}, 400, {"Content-Type": "application/json"}

        # Handle URL verification challenge
        if data and 'challenge' in data:
            challenge = data['challenge']
            print(f"Responding to Slack challenge with: {challenge}")
            return {
                "challenge": challenge
            }, 200, {"Content-Type": "application/json"}

        if not data or 'event' not in data:
            print("ERROR: Missing event data")
            return "Bad Request: Missing event data", 400

        event = data.get("event", {})
        user = event.get("user")
        text = event.get("text", "")
        files = event.get("files", [])
        ts = float(event.get("ts", datetime.datetime.now().timestamp()))
        timestamp = datetime.datetime.fromtimestamp(ts)
        sheet_name = get_month_sheet_name(timestamp)

        description = text.strip() if text else "No message"
        amount, currency = get_currency_and_amount(description)
        dropbox_url = ""
        ocr_info = ""

        if files:
            file_info = files[0]
            file_url = file_info.get("url_private_download")
            headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
            file_response = requests.get(file_url, headers=headers)
            if file_response.ok:
                filename = f"{int(ts)}_{secure_filename(file_info['name'])}"
                dropbox_url = upload_to_dropbox(file_response.content, filename)
                if description == "No message":
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp.write(file_response.content)
                        tmp.flush()
                        extracted = extract_text_from_image(tmp.name)
                        if extracted:
                            description = extracted.strip().split('\n')[0]
                            amount, currency = get_currency_and_amount(extracted)
                            ocr_info = "OCR used"
                        else:
                            ocr_info = "OCR failed"
            else:
                dropbox_url = "Download error"
        else:
            ocr_info = "OCR skipped (text provided)"

        row_data = [
            timestamp.strftime("%Y-%m-%d"),
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            amount,
            currency,
            description,
            user,
            dropbox_url,
            ocr_info
        ]

        append_to_google_sheet(row_data, sheet_name)
        return "OK"

    except Exception as e:
        print(f"ERROR in slack_events: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error processing request: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on 0.0.0.0:{port}")

    # Always run in production mode
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # Use waitress for production server
    if not debug:
        from waitress import serve
        print("Running with Waitress server")
        serve(app, host='0.0.0.0', port=port)
    else:
        print("Running with Flask development server")
        app.run(host='0.0.0.0', port=port, debug=True)
