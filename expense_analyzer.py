

import re
import pytesseract
from PIL import Image
import tempfile
import requests
import os
import json
import datetime
from werkzeug.utils import secure_filename
from flask import render_template

DROPBOX_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"
DROPBOX_ACCESS_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN")

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

def extract_paid_via(text):
    match = re.search(r'via\s(.+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def extract_paid_to(text):
    match = re.search(r'to\s(.+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def extract_paid_date(text):
    match = re.search(r'on\s(\d{1,2}\s\w+\s\d{4})', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def extract_purpose(text):
    match = re.search(r'for\s(.+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Not found"

def analyze_expense(event):
    user = event.get("user")
    text = event.get("text", "")
    files = event.get("files", [])
    ts = float(event.get("ts", ""))
    timestamp = datetime.datetime.fromtimestamp(ts)

    description = text.strip() if text else "No message"
    amount, currency = get_currency_and_amount(description)
    paid_via = extract_paid_via(description)
    paid_to = extract_paid_to(description)
    paid_date = extract_paid_date(description)
    purpose = extract_purpose(description)
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
                        paid_via = extract_paid_via(description)
                        paid_to = extract_paid_to(description)
                        paid_date = extract_paid_date(description)
                        purpose = extract_purpose(description)
                        ocr_info = "OCR used"
                    else:
                        ocr_info = "OCR failed"
        else:
            dropbox_url = "Download error"
    else:
        ocr_info = "OCR skipped (text provided)"

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
        "dropbox_url": dropbox_url,
        "ocr_info": ocr_info
    }

