"""
Test script for the Gemini API server
"""
import requests
import json

def test_server():
    """Test the FastAPI server endpoints"""
    base_url = "http://localhost:8000"
    
    # Test health check
    print("Testing health check endpoint...")
    try:
        response = requests.get(f"{base_url}/")
        print(f"Health check status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("Server is not running. Start it with: uvicorn main:app --reload")
        return
    
    # Test Gemini API endpoint
    print("\nTesting Gemini API endpoint...")
    test_prompt = "Find current Amazon coupon codes. Output format: CODE1, CODE2, CODE3 (codes only, no text)"
    payload = {"prompt": test_prompt}
    
    try:
        response = requests.post(f"{base_url}/generate", json=payload)
        print(f"Generate endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Prompt: {test_prompt}")
            print(f"Response: {result['response']}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error testing generate endpoint: {e}")
    
    # Test structured codes endpoint
    print("\nTesting structured codes endpoint...")
    codes_prompt = "Find Amazon coupon codes"
    payload = {"prompt": codes_prompt}
    
    try:
        response = requests.post(f"{base_url}/codes", json=payload)
        print(f"Codes endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Prompt: {codes_prompt}")
            print(f"Codes found: {result['codes']}")
            print(f"Number of codes: {len(result['codes'])}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error testing codes endpoint: {e}")
    
    # Test detailed codes endpoint
    print("\nTesting detailed codes endpoint...")
    detailed_prompt = "Find Amazon coupon codes with details"
    payload = {"prompt": detailed_prompt}
    
    try:
        response = requests.post(f"{base_url}/codes-detailed", json=payload)
        print(f"Detailed codes endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            codes = result['codes']
            print(f"Prompt: {detailed_prompt}")
            print(f"Found {len(codes)} detailed codes:")
            for i, code_info in enumerate(codes, 1):
                print(f"  {i}. {code_info['code']}")
                print(f"     Description: {code_info['description']}")
                print(f"     Conditions: {code_info['conditions']}")
                print()
            if not codes:
                print("  No codes found")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing detailed codes endpoint: {e}")

if __name__ == "__main__":
    test_server()
