import requests
import json

# Test the Slack event subscription endpoint
def test_slack_challenge():
    url = "https://trackly-todoit.up.railway.app/slack/events"
    
    # This is the challenge payload that Slack sends for URL verification
    challenge_payload = {
        "token": "Jhj5dZrVaK7ZwHHjRyZWjbDl",
        "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tXXAOQ",
        "type": "url_verification"
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=challenge_payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200 and response.text == challenge_payload["challenge"]:
            print("✅ Success! Endpoint is working correctly.")
        else:
            print("❌ Error: Unexpected response from the server.")
            
    except Exception as e:
        print(f"❌ Error making request: {str(e)}")

if __name__ == "__main__":
    test_slack_challenge()
