
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")

def get_google_creds():
    import base64
    creds_json = base64.b64decode(os.environ.get("GOOGLE_CREDS_B64")).decode('utf-8')
    creds_dict = json.loads(creds_json)
    return Credentials.from_authorized_user_info(creds_dict, SCOPES)

def get_month_sheet_name(timestamp):
    return timestamp.strftime("%B")

def append_to_google_sheet(row_data, sheet_name):
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

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

    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": [row_data]}
    ).execute()

def log_expense(expense_data):
    timestamp = expense_data["timestamp"]
    sheet_name = get_month_sheet_name(timestamp)

    row_data = [
        timestamp.strftime("%Y-%m-%d"),
        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        expense_data["amount"],
        expense_data["currency"],
        expense_data["paid_via"],
        expense_data["paid_to"],
        expense_data["paid_date"],
        expense_data["purpose"],
        expense_data["description"],
        expense_data["user"],
        expense_data["dropbox_url"],
        expense_data["ocr_info"]
    ]

    append_to_google_sheet(row_data, sheet_name)
