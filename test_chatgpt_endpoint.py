"""
Test script for the ChatGPT codes endpoint
"""
import requests
import json

# Test the ChatGPT endpoint
def test_chatgpt_endpoint():
    url = "http://localhost:8000/codes-detailed-chatgpt"
    
    payload = {
        "prompt": "nike discount codes"
    }
    
    print(f"Testing ChatGPT endpoint with prompt: {payload['prompt']}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Number of codes found: {len(data['codes'])}")
        print("\nCodes:")
        print("-" * 50)
        
        for code_info in data['codes']:
            print(f"\nCode: {code_info['code']}")
            print(f"Description: {code_info['description']}")
            print(f"Conditions: {code_info['conditions']}")
            print(f"Has Description: {code_info['has_description']}")
            print(f"Has Conditions: {code_info['has_conditions']}")
            print("-" * 30)
            
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")

if __name__ == "__main__":
    test_chatgpt_endpoint()
