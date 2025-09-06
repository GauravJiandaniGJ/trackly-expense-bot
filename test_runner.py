import requests

def test_log_expense_from_web():
    url = "http://localhost:5000/log_expense_from_web"
    data = {
        "amount": "100",
        "currency": "USD",
        "paid_to": "Test Vendor",
        "paid_via": "Test Card",
        "paid_date": "2025-09-06",
        "purpose": "Test Purpose",
        "description": "Test Description"
    }
    files = [
        ('invoices', ('dummy1.txt', b'This is dummy file 1.', 'text/plain')),
        ('invoices', ('dummy2.txt', b'This is dummy file 2.', 'text/plain'))
    ]
    response = requests.post(url, data=data, files=files)
    print(response.text)

if __name__ == "__main__":
    test_log_expense_from_web()