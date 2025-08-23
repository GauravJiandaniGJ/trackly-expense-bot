import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_health_check():
    """Test the health check endpoint"""
    url = 'http://localhost:5000/'
    try:
        response = requests.get(url)
        print(f"\nHealth Check Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Error testing health check: {e}")
        return False

def test_slack_challenge():
    """Test Slack URL verification challenge"""
    url = 'http://localhost:5000/slack/events'
    challenge_value = 'test_challenge_123'

    test_payload = {
        "token": "test_token",
        "challenge": challenge_value,
        "type": "url_verification"
    }

    try:
        response = requests.post(url, json=test_payload)
        print(f"\nSlack Challenge Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))

        if response.status_code == 200 and response.json().get('challenge') == challenge_value:
            print("✅ Slack URL verification successful!")
            return True
        else:
            print("❌ Slack URL verification failed!")
            return False
    except Exception as e:
        print(f"Error testing Slack challenge: {e}")
        return False

def check_environment():
    """Check if required environment variables are set"""
    required_vars = [
        'SPREADSHEET_ID',
        'GOOGLE_CREDS_JSON',
        'DROPBOX_ACCESS_TOKEN',
        'SLACK_BOT_TOKEN',
        'PORT'
    ]

    print("\nEnvironment Variables Check:")
    print("=" * 30)
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        status = "✅ Set" if value else "❌ Missing"
        print(f"{var}: {status}")
        if not value:
            all_set = False

    if all_set:
        print("\n✅ All required environment variables are set!")
    else:
        print("\n❌ Some required environment variables are missing!")

    return all_set

if __name__ == "__main__":
    print("Starting local tests...")
    print("=" * 50)

    # Check environment variables first
    env_ok = check_environment()
    if not env_ok:
        print("\nPlease set up the required environment variables in the .env file.")
        exit(1)

    # Test endpoints
    health_ok = test_health_check()
    challenge_ok = test_slack_challenge()

    print("\nTest Summary:")
    print("=" * 50)
    print(f"Health Check: {'✅ PASSED' if health_ok else '❌ FAILED'}")
    print(f"Slack Challenge: {'✅ PASSED' if challenge_ok else '❌ FAILED'}")

    if health_ok and challenge_ok:
        print("\n✅ All tests passed! Your application is ready for deployment.")
    else:
        print("\n❌ Some tests failed. Please check the output above for issues.")
