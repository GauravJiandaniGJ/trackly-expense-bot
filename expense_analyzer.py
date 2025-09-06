

import re
import pytesseract
from PIL import Image
import tempfile
import requests
import os
import json
import datetime
from werkzeug.utils import secure_filename

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

def analyze_expense(event, logger):
    logger.info("Analyzing expense...")
    user = event.get("user")
    text = event.get("text", "")
    files = event.get("files", [])
    ts = float(event.get("ts", ""))
    timestamp = datetime.datetime.fromtimestamp(ts)

    description = text.strip() if text else "No message"
    amount, currency = get_currency_and_amount(description)
    paid_date = extract_paid_date(description)
    paid_via = extract_paid_via(description)
    paid_to = extract_paid_to(description)
    purpose = extract_purpose(description)
    dropbox_urls = []
    ocr_info = ""

    if files:
        logger.info(f"Found {len(files)} file(s) to process.")
        for file_info in files:
            file_url = file_info.get("url_private_download")
            headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
            file_response = requests.get(file_url, headers=headers)
            if file_response.ok:
                logger.info(f"Uploading {file_info['name']} to Dropbox...")
                filename = f"{int(ts)}_{secure_filename(file_info['name'])}"
                dropbox_url = upload_to_dropbox(file_response.content, filename)
                print(f"Dropbox URL: {dropbox_url}")
                if dropbox_url:
                    logger.info("File uploaded to Dropbox successfully.")
                    dropbox_urls.append(dropbox_url)
                else:
                    logger.error("Failed to upload file to Dropbox.")
                
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(file_response.content)
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
                dropbox_urls.append("Download error")
    else:
        ocr_info = "OCR skipped (text provided)"

    print(f"Dropbox URLs at end of analyze_expense: {dropbox_urls}")
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
        "dropbox_url": dropbox_urls,
        "ocr_info": ocr_info
    }

