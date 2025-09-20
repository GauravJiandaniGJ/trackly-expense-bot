

import re
import pytesseract
from PIL import Image
import tempfile
import requests
import os
import json
import datetime
from werkzeug.utils import secure_filename
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaIoBaseUpload
import io

SCOPES = ['https://www.googleapis.com/auth/drive']
CLIENT_SECRET_FILE = 'client_secret.json'
TOKEN_FILE = 'token.json'

DROPBOX_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"
DROPBOX_ACCESS_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN")

def get_currency_and_amount(text):
    match = re.search(r'(?:([\₹$€£])\s?(\d+(?:[.,]\d{1,2})?))|(?:(\d+(?:[.,]\d{1,2})?)\s?([\₹$€£]))', text)
    if match:
        if match.group(1):
            symbol = match.group(1)
            amount = match.group(2).replace(',', '')
        else:
            symbol = match.group(4)
            amount = match.group(3).replace(',', '')

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
        else:
            print(f"Error creating shared link: {shared_link_resp.status_code} - {shared_link_resp.text}")
    else:
        print(f"Error uploading to Dropbox: {response.status_code} - {response.text}")
    return None

def upload_to_google_drive(file_content, filename):
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                print("Please re-authenticate the application to get a new token.json file.")
                return None
        else:
            print("Error: token.json not found or invalid. Please re-authenticate the application to get a new token.json file.")
            return None

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        if not creds or not creds.valid:
            print("Authentication failed. Cannot upload to Google Drive.")
            return None
            
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': filename,
            'parents': [os.environ.get("GOOGLE_DRIVE_FOLDER_ID")]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream', resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webContentLink, webViewLink').execute()

        # Make the file publicly accessible (optional, but needed for direct links)
        service.permissions().create(fileId=file.get('id'), body={'type': 'anyone', 'role': 'reader'}).execute()

        # Return webViewLink for direct access
        return file.get('webViewLink')

    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")
        return None

def extract_paid_via(text):
    match = re.search(r'via\s(.+?)(?=\s(on|for|to)|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def extract_paid_to(text):
    match = re.search(r'to\s(.+?)(?=\s(on|for|via)|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'from\s(.+?)(?=\s(on|for|via)|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def extract_paid_date(text):
    match = re.search(r'on\s(\d{1,2}(?:st|nd|rd|th)?\s\w+\s\d{4})', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def extract_purpose(text):
    match = re.search(r'for\s(.+?)(?=\s(on|to|via)|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def analyze_expense_from_slack(event, logger):
    logger.info("Analyzing expense from Slack...")
    user = event.get("user")
    text = event.get("text", "")
    files = event.get("files", [])
    ts = float(event.get("ts", ""))
    timestamp = datetime.datetime.fromtimestamp(ts)
    description = text.strip() if text else "No message"

    files_data = []
    if files:
        for file_info in files:
            file_url = file_info.get("url_private_download")
            headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
            file_response = requests.get(file_url, headers=headers)
            if file_response.ok:
                files_data.append((file_response.content, file_info['name']))
            else:
                logger.error(f"Failed to download file from Slack: {file_info['name']}")

    return process_expense_data(description, files_data, user, timestamp, logger, 'slack')

def analyze_expense_from_web(data, files, logger):
    logger.info("Analyzing expense from web...")
    user = "web_user"  # Or get from session if you have auth
    timestamp = datetime.datetime.now()
    description = data.get("description", "")

    files_data = []
    if files:
        for file_info in files:
            file_content = file_info.read()
            file_name = file_info.filename
            files_data.append((file_content, file_name))

    return process_expense_data(description, files_data, user, timestamp, logger, 'web')

def process_expense_data(description, files_data, user, timestamp, logger, source):
    amount, currency = get_currency_and_amount(description)
    paid_date = extract_paid_date(description)
    paid_via = extract_paid_via(description)
    paid_to = extract_paid_to(description)
    purpose = extract_purpose(description)
    google_drive_urls = []
    ocr_info = ""

    if files_data:
        logger.info(f"Found {len(files_data)} file(s) to process.")
        for file_content, file_name in files_data:
            

            if file_content:
                logger.info(f"Uploading {file_name} to Google Drive...")
                filename = f"{int(timestamp.timestamp())}_{secure_filename(file_name)}"
                # dropbox_url = upload_to_dropbox(file_content, filename)
                google_drive_url = upload_to_google_drive(file_content, filename)
                print(f"Google Drive URL: {google_drive_url}")
                if google_drive_url:
                    logger.info("File uploaded to Google Drive successfully.")
                    google_drive_urls.append(google_drive_url)
                else:
                    logger.error("Failed to upload file to Google Drive.")
                
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(file_content)
                    tmp.flush()
                    logger.info("Starting OCR...")
                    extracted = extract_text_from_image(tmp.name)
                    if extracted:
                        if description == "No message":
                            description = extracted.strip().split('\n')[0]
                        
                        ocr_amount, ocr_currency = get_currency_and_amount(extracted)
                        ocr_paid_via = extract_paid_via(extracted)
                        ocr_paid_to = extract_paid_to(extracted)
                        ocr_paid_date = extract_paid_date(extracted)
                        ocr_purpose = extract_purpose(extracted)

                        if ocr_amount != "Not found":
                            amount = ocr_amount
                        if ocr_currency != "Not found":
                            currency = ocr_currency
                        if ocr_paid_via != "Not found":
                            paid_via = ocr_paid_via
                        if ocr_paid_to != "Not found":
                            paid_to = ocr_paid_to
                        if ocr_paid_date != "Not found":
                            paid_date = ocr_paid_date
                        if ocr_purpose != "Not found":
                            purpose = ocr_purpose

                        ocr_info = "OCR used"
                        logger.info("OCR completed successfully.")
                    else:
                        ocr_info = "OCR failed"
                        logger.warning("OCR failed to extract text.")
            else:
                google_drive_urls.append("Download error")
    else:
        ocr_info = "OCR skipped (text provided)"

    print(f"Dropbox URLs at end of analyze_expense: {google_drive_urls}")
    logger.info("Expense analysis complete.")
    return {
        "timestamp": timestamp,
        "amount": amount,
        "currency": currency,
        "paid_via": paid_via,
        "paid_to": paid_to,
        "paid_date": paid_date,
        "purpose": purpose,
        "description": description,
        "user": user,
        "dropbox_url": google_drive_urls,
        "ocr_info": ocr_info
    }

