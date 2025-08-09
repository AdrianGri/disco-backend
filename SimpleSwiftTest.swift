import Foundation

// Simple Swift test to hit the /codes endpoint
// Run this with: swift SimpleSwiftTest.swift

struct CodesResponse: Codable {
    let codes: [String]
}

struct PromptRequest: Codable {
    let prompt: String
}

func testCodesEndpoint() async {
    print("🚀 Testing /codes endpoint from Swift...")
    
    // Create the URL
    guard let url = URL(string: "http://localhost:8000/codes") else {
        print("❌ Invalid URL")
        return
    }
    
    // Create the request
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    // Create the request body
    let requestBody = PromptRequest(prompt: "Find Amazon coupon codes")
    
    do {
        // Encode the request body
        request.httpBody = try JSONEncoder().encode(requestBody)
        
        // Make the request
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Check response status
        if let httpResponse = response as? HTTPURLResponse {
            print("📡 Response status: \(httpResponse.statusCode)")
            
            if httpResponse.statusCode == 200 {
                // Parse the response
                let codesResponse = try JSONDecoder().decode(CodesResponse.self, from: data)
                
                print("✅ Success! Found \(codesResponse.codes.count) codes:")
                for (index, code) in codesResponse.codes.enumerated() {
                    print("  \(index + 1). \(code)")
                }
                
                // Print raw JSON for debugging
                if let jsonString = String(data: data, encoding: .utf8) {
                    print("\n📄 Raw JSON response:")
                    print(jsonString)
                }
            } else {
                print("❌ Server error: \(httpResponse.statusCode)")
                if let errorString = String(data: data, encoding: .utf8) {
                    print("Error details: \(errorString)")
                }
            }
        }
        
    } catch {
        print("❌ Error: \(error)")
    }
}

// Multiple test prompts
func testMultiplePrompts() async {
    let prompts = [
        "Find Amazon coupon codes",
        "Get McDonald's promo codes",
        "Find Nike discount codes"
    ]
    
    for prompt in prompts {
        print("\n" + "="*50)
        print("Testing prompt: '\(prompt)'")
        print("="*50)
        
        guard let url = URL(string: "http://localhost:8000/codes") else { continue }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let requestBody = PromptRequest(prompt: prompt)
        
        do {
            request.httpBody = try JSONEncoder().encode(requestBody)
            let (data, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200 {
                let codesResponse = try JSONDecoder().decode(CodesResponse.self, from: data)
                
                print("✅ Found \(codesResponse.codes.count) codes:")
                codesResponse.codes.enumerated().forEach { index, code in
                    print("  \(index + 1). \(code)")
                }
                
                if codesResponse.codes.isEmpty {
                    print("  No codes found")
                }
            } else {
                print("❌ Request failed")
            }
        } catch {
            print("❌ Error: \(error)")
        }
        
        // Small delay between requests
        try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
    }
}

// Entry point
if #available(macOS 12.0, iOS 15.0, *) {
    Task {
        print("📱 Swift API Client Test")
        print("🎯 Target: http://localhost:8000/codes")
        print("")
        
        // Test single request
        await testCodesEndpoint()
        
        print("\n" + "🔄 Testing multiple prompts...")
        
        // Test multiple requests
        await testMultiplePrompts()
        
        print("\n✅ All tests completed!")
        exit(0)
    }
    
    RunLoop.main.run()
} else {
    print("❌ This requires macOS 12+ or iOS 15+ for async/await")
}

extension String {
    static func *(lhs: String, rhs: Int) -> String {
        return String(repeating: lhs, count: rhs)
    }
}
