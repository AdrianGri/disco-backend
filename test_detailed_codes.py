"""
Test script for the detailed codes endpoint
"""
import requests
import json

def test_detailed_codes():
    """Test the detailed codes endpoint"""
    base_url = "http://localhost:8000"
    
    # Test different prompts for detailed codes
    test_prompts = [
        "Find Amazon coupon codes with conditions and expiration dates",
        "Get McDonald's promo codes with details about when they apply",
        "Find Nike discount codes with minimum purchase requirements",
        "Get Target coupon codes with usage restrictions"
    ]
    
    for prompt in test_prompts:
        print(f"\n{'='*60}")
        print(f"Testing: {prompt}")
        print('='*60)
        
        payload = {"prompt": prompt}
        
        try:
            response = requests.post(f"{base_url}/codes-detailed", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                codes = result['codes']
                
                print(f"✅ Found {len(codes)} detailed codes:")
                print()
                
                for i, code_info in enumerate(codes, 1):
                    print(f"📋 Code #{i}: {code_info['code']}")
                    
                    # Show description with indicator
                    desc_indicator = "✅" if code_info['has_description'] else "❓"
                    print(f"   💰 Description: {code_info['description']} {desc_indicator}")
                    
                    # Show conditions with indicator
                    cond_indicator = "✅" if code_info['has_conditions'] else "❓"
                    print(f"   📝 Conditions: {code_info['conditions']} {cond_indicator}")
                    print()
                    
                if not codes:
                    print("   No detailed codes found")
                    
            else:
                print(f"❌ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    # Test structured format
    print(f"\n{'='*60}")
    print("Testing JSON structure")
    print('='*60)
    
    payload = {"prompt": "Find Amazon coupon codes with details"}
    
    try:
        response = requests.post(f"{base_url}/codes-detailed", json=payload)
        if response.status_code == 200:
            result = response.json()
            print("📄 Raw JSON response:")
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    print("🔍 Testing Detailed Codes Endpoint")
    print("🎯 Target: http://localhost:8000/codes-detailed")
    print()
    
    test_detailed_codes()
    
    print("\n✅ Testing completed!")
