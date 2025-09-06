
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")


def get_google_creds():
    import base64
    creds_json = os.environ.get("GOOGLE_CREDS_B64")
    if not creds_json:
        raise ValueError("GOOGLE_CREDS_B64 environment variable not set")
    
    creds_dict = json.loads(base64.b64decode(creds_json))
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)


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
        header = ["Date", "Timestamp", "Amount", "Currency", "Paid Via", "Paid To", "Paid Date", "Purpose", "Description", "User", "Dropbox URL", "OCR Info"]
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [header]}
        ).execute()

    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}!A:A").execute()
    num_rows = len(result.get('values', []))

    range_to_update = f"{sheet_name}!A{num_rows + 1}"

    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_to_update,
        valueInputOption="USER_ENTERED",
        body={"values": [row_data]}
    ).execute()


def write_multi_hyperlink_rich_text(service, spreadsheet_id, sheet_name, row_idx0, col_idx0, parts):
    """
    Write multiple hyperlinks inside ONE cell using rich-text runs.

    parts: list of (text, url_or_None)
      e.g. [("IMAGE1", "https://...1"), (" , ", None), ("IMAGE2", "https://...2")]

    row_idx0, col_idx0 are 0-based indexes.
    """
    # Get sheetId by title
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet = next(s for s in meta["sheets"] if s["properties"]["title"] == sheet_name)
    sheet_id = sheet["properties"]["sheetId"]

    full_text = "".join(t for t, _ in parts)

    # Build textFormatRuns (startIndex is cumulative)
    runs = []
    cursor = 0
    for text, url in parts:
        run = {"startIndex": cursor}
        if url:
            run["format"] = {"link": {"uri": url}}
        runs.append(run)
        cursor += len(text)

    body = {
        "requests": [
            {
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row_idx0,
                        "endRowIndex": row_idx0 + 1,
                        "startColumnIndex": col_idx0,
                        "endColumnIndex": col_idx0 + 1,
                    },
                    "rows": [
                        {
                            "values": [
                                {
                                    "userEnteredValue": {"stringValue": full_text},
                                    "textFormatRuns": runs,
                                }
                            ]
                        }
                    ],
                    "fields": "userEnteredValue,textFormatRuns"
                }
            }
        ]
    }
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()


def log_expense(expense_data, logger):
    logger.info("Logging expense to Google Sheet...")
    from googleapiclient.discovery import build

    ts = expense_data["timestamp"]
    sheet_name = ts.strftime("%B")

    # 1) Build your normal row (no formula in the link cell; we'll overwrite it with rich text)
    row_data = [
        ts.strftime("%Y-%m-%d"),
        ts.strftime("%Y-%m-%d %H:%M:%S"),
        expense_data["amount"],
        expense_data["currency"],
        expense_data["paid_via"],
        expense_data["paid_to"],
        expense_data["paid_date"],
        expense_data["purpose"],
        expense_data["description"],
        expense_data["user"],
        "",  # <-- placeholder; we'll replace this with rich text links
        expense_data["ocr_info"],
    ]

    # 2) Write/ensure sheet + header + compute next row (you already have this)
    append_to_google_sheet(row_data, sheet_name)

    # 3) Compute the row index we just wrote (0-based)
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)
    colA = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{sheet_name}!A:A"
    ).execute()
    num_rows = len(colA.get("values", []))  # includes header row
    target_row_1based = num_rows  # last written row
    target_row_0based = target_row_1based - 1

    # 4) Build parts for rich text runs in the link cell
    urls = expense_data.get("dropbox_url") or []
    labels = expense_data.get("dropbox_texts") or expense_data.get("dropbox_labels") or []
    logger.info(f"URLs received in sheets_logger: {urls}")

    parts = []
    for i, url in enumerate(urls):
        if not url:
            continue
        label = labels[i] if i < len(labels) and labels[i] else f"IMAGE{i+1}"
        if parts:
            parts.append((" , ", None))  # separator
        parts.append((str(label), str(url)))

    logger.info(f"Parts list for rich text: {parts}")

    if parts:
        # Column index for your “Dropbox URL” cell:
        # A=0, B=1, ... K=10 → adjust if your schema differs.
        dropbox_col_idx0 = 10

        write_multi_hyperlink_rich_text(
            service,
            SPREADSHEET_ID,
            sheet_name,
            row_idx0=target_row_0based,
            col_idx0=dropbox_col_idx0,
            parts=parts,
        )

    logger.info("Expense logged successfully to Google Sheet.")
