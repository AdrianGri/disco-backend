"""
Simple test for the codes endpoint
"""
import requests
import json

def test_codes_endpoint():
    """Test just the codes endpoint"""
    base_url = "http://localhost:8000"
    
    # Test different types of code requests
    test_prompts = [
        "Find Amazon coupon codes",
        "Get McDonald's promo codes", 
        "Find Nike discount codes",
        "Get Walmart coupon codes"
    ]
    
    for prompt in test_prompts:
        print(f"\n--- Testing: {prompt} ---")
        payload = {"prompt": prompt}
        
        try:
            response = requests.post(f"{base_url}/codes", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                codes = result['codes']
                print(f"✅ Found {len(codes)} codes:")
                for i, code in enumerate(codes, 1):
                    print(f"  {i}. {code}")
                if not codes:
                    print("  No codes found")
            else:
                print(f"❌ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print("\n--- Testing structured format ---")
    prompt = "Find Amazon coupon codes"
    payload = {"prompt": prompt}
    
    try:
        response = requests.post(f"{base_url}/codes", json=payload)
        if response.status_code == 200:
            result = response.json()
            print("Response structure:")
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_codes_endpoint()
