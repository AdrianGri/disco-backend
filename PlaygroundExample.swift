import Foundation
import PlaygroundSupport

// Swift Playground example for testing the /codes endpoint
// Copy this into an Xcode Playground for interactive testing

PlaygroundPage.current.needsIndefiniteExecution = true

struct CodesResponse: Codable {
    let codes: [String]
}

struct PromptRequest: Codable {
    let prompt: String
}

// Simple function to test the API
func testAPI(prompt: String) async {
    print("🚀 Testing prompt: '\(prompt)'")
    
    guard let url = URL(string: "http://localhost:8000/codes") else {
        print("❌ Invalid URL")
        return
    }
    
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    do {
        let requestBody = PromptRequest(prompt: prompt)
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
    
    print("") // Empty line for spacing
}

// Test different prompts
Task {
    await testAPI(prompt: "Find Amazon coupon codes")
    await testAPI(prompt: "Get Target promo codes")
    await testAPI(prompt: "Find Starbucks discount codes")
    
    print("🎉 Playground testing complete!")
    PlaygroundPage.current.finishExecution()
}

/*
 To use this in Xcode Playground:
 
 1. Create a new Playground in Xcode
 2. Replace the default content with this code
 3. Make sure your FastAPI server is running on localhost:8000
 4. Run the playground
 
 The playground will make HTTP requests to your server and display the results
 in the console area.
 */
