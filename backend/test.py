import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.getenv('OPENAI_API_KEY')

# Simple test request
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

payload = {
    "model": "gpt-3.5-turbo",  # Using a widely available model for testing
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello world"}
    ]
}

try:
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload
    )
    
    result = response.json()
    print("Response status code:", response.status_code)
    print("Response content:", result)
    
    if 'error' in result:
        print("API Error:", result['error'])
    elif 'choices' in result:
        print("Success! API is working.")
        print("Response:", result['choices'][0]['message']['content'])
    else:
        print("Unexpected response structure")
        
except Exception as e:
    print(f"Error making request: {e}")