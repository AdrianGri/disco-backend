//
//  ShareViewController.swift
//  RaftShareExtension
//
//  Created by Adrian Gri on 2025-07-19.
//

import UIKit
import Social
import UniformTypeIdentifiers

let appGroupID = "group.com.yourcompany.raft"

class ShareViewController: SLComposeServiceViewController {
    override func isContentValid() -> Bool { true }

    override func didSelectPost() {
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem else {
            return
        }

        for attachment in extensionItem.attachments ?? [] {
            if attachment.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                attachment.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { item, error in
                    if let url = item as? URL {
                        self.queryDiscountCodes(for: url)
                    }
                }
            }
        }
    }

    // Response models for the FastAPI server
    struct CodesResponse: Codable {
        let codes: [String]
    }
    
    struct PromptRequest: Codable {
        let prompt: String
    }
    
    func callGeminiServer(prompt: String, completion: @escaping ([String]) -> Void) {
        // Update this URL to match your server's address
        // For testing: "http://localhost:8000/codes"
        // For production: use your actual server URL
        guard let url = URL(string: "http://localhost:8000/codes") else {
            print("❌ Invalid server URL")
            completion([])
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30.0 // 30 second timeout

        let requestBody = PromptRequest(prompt: prompt)
        
        do {
            request.httpBody = try JSONEncoder().encode(requestBody)
        } catch {
            print("❌ Error encoding request: \(error)")
            completion([])
            return
        }

        let task = URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                print("❌ Network error: \(error)")
                completion([])
                return
            }
            
            guard let data = data else {
                print("❌ No data received")
                completion([])
                return
            }
            
            guard let httpResponse = response as? HTTPURLResponse else {
                print("❌ Invalid response type")
                completion([])
                return
            }
            
            print("📡 Server response status: \(httpResponse.statusCode)")
            
            if httpResponse.statusCode == 200 {
                do {
                    let codesResponse = try JSONDecoder().decode(CodesResponse.self, from: data)
                    let codes = codesResponse.codes
                    
                    print("✅ Received \(codes.count) codes from server: \(codes)")
                    
                    // Save to App Group for main app access
                    if let defaults = UserDefaults(suiteName: appGroupID) {
                        defaults.set(codes, forKey: "discountCodes")
                        print("💾 Saved codes to App Group")
                    }
                    
                    completion(codes)
                } catch {
                    print("❌ Error decoding response: \(error)")
                    // Try to print raw response for debugging
                    if let responseString = String(data: data, encoding: .utf8) {
                        print("📄 Raw response: \(responseString)")
                    }
                    completion([])
                }
            } else {
                print("❌ Server error: \(httpResponse.statusCode)")
                if let responseString = String(data: data, encoding: .utf8) {
                    print("📄 Error details: \(responseString)")
                }
                completion([])
            }
        }

        task.resume()
    }

    func queryDiscountCodes(for url: URL) {
        let domain = url.host ?? ""
        let prompt = "Find current discount codes for \(domain)"
        
        print("🔍 Searching for codes for domain: \(domain)")
        print("📝 Prompt: \(prompt)")

        callGeminiServer(prompt: prompt) { codes in
            DispatchQueue.main.async {
                if codes.isEmpty {
                    print("ℹ️ No discount codes found for \(domain)")
                } else {
                    print("🎉 Found \(codes.count) discount codes for \(domain): \(codes)")
                }
                
                // Close the share extension
                self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
            }
        }
    }

    override func configurationItems() -> [Any]! {
        return []
    }
}
