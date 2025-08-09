import Foundation

// MARK: - Response Models
struct CodesResponse: Codable {
    let codes: [String]
}

struct PromptRequest: Codable {
    let prompt: String
}

// MARK: - API Client
class GeminiAPIClient {
    private let baseURL = "http://localhost:8000"
    
    // MARK: - Async/Await Version (iOS 15+)
    func getCodes(prompt: String) async throws -> [String] {
        guard let url = URL(string: "\(baseURL)/codes") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let requestBody = PromptRequest(prompt: prompt)
        request.httpBody = try JSONEncoder().encode(requestBody)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        let codesResponse = try JSONDecoder().decode(CodesResponse.self, from: data)
        return codesResponse.codes
    }
    
    // MARK: - Completion Handler Version (iOS 13+)
    func getCodes(prompt: String, completion: @escaping (Result<[String], Error>) -> Void) {
        guard let url = URL(string: "\(baseURL)/codes") else {
            completion(.failure(URLError(.badURL)))
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            let requestBody = PromptRequest(prompt: prompt)
            request.httpBody = try JSONEncoder().encode(requestBody)
        } catch {
            completion(.failure(error))
            return
        }
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            
            guard let data = data,
                  let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                completion(.failure(URLError(.badServerResponse)))
                return
            }
            
            do {
                let codesResponse = try JSONDecoder().decode(CodesResponse.self, from: data)
                completion(.success(codesResponse.codes))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
    
    // MARK: - Health Check
    func healthCheck() async throws -> Bool {
        guard let url = URL(string: "\(baseURL)/") else {
            throw URLError(.badURL)
        }
        
        let (_, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            return false
        }
        
        return httpResponse.statusCode == 200
    }
}

// MARK: - Usage Examples
class TestExamples {
    private let apiClient = GeminiAPIClient()
    
    // MARK: - Async/Await Examples
    func testAsyncAwait() async {
        print("🚀 Testing with async/await...")
        
        // Health check first
        do {
            let isHealthy = try await apiClient.healthCheck()
            print("✅ Server health check: \(isHealthy ? "OK" : "Failed")")
        } catch {
            print("❌ Health check failed: \(error)")
            return
        }
        
        // Test different prompts
        let testPrompts = [
            "Find Amazon coupon codes",
            "Get McDonald's promo codes",
            "Find Nike discount codes",
            "Get Walmart coupon codes"
        ]
        
        for prompt in testPrompts {
            print("\n--- Testing: \(prompt) ---")
            
            do {
                let codes = try await apiClient.getCodes(prompt: prompt)
                print("✅ Found \(codes.count) codes:")
                for (index, code) in codes.enumerated() {
                    print("  \(index + 1). \(code)")
                }
                if codes.isEmpty {
                    print("  No codes found")
                }
            } catch {
                print("❌ Error: \(error)")
            }
        }
    }
    
    // MARK: - Completion Handler Examples
    func testCompletionHandler() {
        print("\n🚀 Testing with completion handlers...")
        
        let testPrompts = [
            "Find Amazon coupon codes",
            "Get Target promo codes"
        ]
        
        let group = DispatchGroup()
        
        for prompt in testPrompts {
            group.enter()
            print("\n--- Testing: \(prompt) ---")
            
            apiClient.getCodes(prompt: prompt) { result in
                defer { group.leave() }
                
                switch result {
                case .success(let codes):
                    print("✅ Found \(codes.count) codes:")
                    for (index, code) in codes.enumerated() {
                        print("  \(index + 1). \(code)")
                    }
                    if codes.isEmpty {
                        print("  No codes found")
                    }
                    
                case .failure(let error):
                    print("❌ Error: \(error)")
                }
            }
        }
        
        group.wait()
    }
    
    // MARK: - SwiftUI Example
    @MainActor
    func testSwiftUI() async {
        print("\n🚀 Testing SwiftUI-style...")
        
        do {
            let codes = try await apiClient.getCodes(prompt: "Find Amazon coupon codes")
            
            // This is how you'd use it in SwiftUI
            DispatchQueue.main.async {
                // Update your @State or @StateObject here
                print("📱 SwiftUI: Received \(codes.count) codes for UI update")
                print("📱 Codes: \(codes)")
            }
        } catch {
            print("❌ SwiftUI Error: \(error)")
        }
    }
}

// MARK: - Main Test Runner
func runTests() async {
    let tester = TestExamples()
    
    print("🧪 Starting Swift API Tests...")
    print("📡 Server: http://localhost:8000")
    print("=" * 50)
    
    // Test async/await
    await tester.testAsyncAwait()
    
    // Test completion handlers
    tester.testCompletionHandler()
    
    // Test SwiftUI style
    await tester.testSwiftUI()
    
    print("\n✅ All tests completed!")
}

// MARK: - Entry Point
if #available(iOS 15.0, macOS 12.0, *) {
    Task {
        await runTests()
        exit(0)
    }
    
    // Keep the program running for async tasks
    RunLoop.main.run()
} else {
    print("❌ This example requires iOS 15+ or macOS 12+ for async/await support")
    let tester = TestExamples()
    tester.testCompletionHandler()
}

// MARK: - Helper Extension
extension String {
    static func * (left: String, right: Int) -> String {
        return String(repeating: left, count: right)
    }
}
