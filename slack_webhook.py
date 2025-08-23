import os
import datetime
import json
import requests
import re
from flask import Flask, request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from werkzeug.utils import secure_filename
import pytesseract
from PIL import Image
import tempfile

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
DROPBOX_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"
DROPBOX_TOKEN = os.environ.get("DROPBOX_TOKEN")

def get_google_creds():
    creds_dict = json.loads(os.environ.get("GOOGLE_CREDS_JSON"))
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
        "Authorization": f"Bearer {DROPBOX_TOKEN}",
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
                "Authorization": f"Bearer {DROPBOX_TOKEN}",
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

@app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        # Log incoming request
        print("\n=== INCOMING REQUEST ===")
        print(f"Headers: {request.headers}")
        
        if not request.is_json:
            print("ERROR: Request is not JSON")
            return "Invalid request", 400
            
        data = request.get_json()
        print(f"Request data: {data}")
        
        # Handle URL verification challenge
        if data and 'challenge' in data:
            print(f"Responding to Slack challenge: {data['challenge']}")
            return data['challenge']
            
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
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
