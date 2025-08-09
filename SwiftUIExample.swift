import SwiftUI

// SwiftUI View example for iOS/macOS apps
// This shows how to integrate the /codes endpoint into a SwiftUI app

struct CodesResponse: Codable {
    let codes: [String]
}

struct PromptRequest: Codable {
    let prompt: String
}

// MARK: - API Service
@MainActor
class CodesService: ObservableObject {
    @Published var codes: [String] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let baseURL = "http://localhost:8000"
    
    func fetchCodes(prompt: String) async {
        isLoading = true
        errorMessage = nil
        
        guard let url = URL(string: "\(baseURL)/codes") else {
            errorMessage = "Invalid URL"
            isLoading = false
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            let requestBody = PromptRequest(prompt: prompt)
            request.httpBody = try JSONEncoder().encode(requestBody)
            
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                errorMessage = "Invalid response"
                isLoading = false
                return
            }
            
            if httpResponse.statusCode == 200 {
                let codesResponse = try JSONDecoder().decode(CodesResponse.self, from: data)
                codes = codesResponse.codes
            } else {
                errorMessage = "Server error: \(httpResponse.statusCode)"
            }
            
        } catch {
            errorMessage = "Error: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
}

// MARK: - SwiftUI Views
struct ContentView: View {
    @StateObject private var codesService = CodesService()
    @State private var searchText = "Find Amazon coupon codes"
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // Search Input
                VStack(alignment: .leading) {
                    Text("Enter your prompt:")
                        .font(.headline)
                    
                    TextField("e.g., Find Amazon coupon codes", text: $searchText)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .onSubmit {
                            Task {
                                await codesService.fetchCodes(prompt: searchText)
                            }
                        }
                    
                    Button("Get Codes") {
                        Task {
                            await codesService.fetchCodes(prompt: searchText)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(codesService.isLoading)
                }
                .padding()
                
                // Loading State
                if codesService.isLoading {
                    ProgressView("Fetching codes...")
                        .padding()
                }
                
                // Error State
                if let errorMessage = codesService.errorMessage {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .padding()
                }
                
                // Results
                if !codesService.codes.isEmpty {
                    VStack(alignment: .leading) {
                        Text("Found \(codesService.codes.count) codes:")
                            .font(.headline)
                            .padding(.horizontal)
                        
                        List(codesService.codes, id: \.self) { code in
                            CodeRowView(code: code)
                        }
                    }
                } else if !codesService.isLoading && codesService.errorMessage == nil {
                    Text("No codes found yet")
                        .foregroundColor(.secondary)
                        .padding()
                }
                
                Spacer()
            }
            .navigationTitle("Coupon Codes")
        }
    }
}

struct CodeRowView: View {
    let code: String
    @State private var showCopiedAlert = false
    
    var body: some View {
        HStack {
            Text(code)
                .font(.monospaced(.body)())
                .padding(.vertical, 4)
            
            Spacer()
            
            Button("Copy") {
                UIPasteboard.general.string = code
                showCopiedAlert = true
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
        .alert("Copied!", isPresented: $showCopiedAlert) {
            Button("OK") { }
        }
    }
}

// MARK: - Quick Test Buttons View
struct QuickTestView: View {
    @StateObject private var codesService = CodesService()
    
    let testPrompts = [
        "Find Amazon coupon codes",
        "Get McDonald's promo codes",
        "Find Nike discount codes",
        "Get Walmart coupon codes"
    ]
    
    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                Text("Quick Tests")
                    .font(.title2)
                    .padding()
                
                ForEach(testPrompts, id: \.self) { prompt in
                    Button(prompt) {
                        Task {
                            await codesService.fetchCodes(prompt: prompt)
                        }
                    }
                    .buttonStyle(.bordered)
                    .disabled(codesService.isLoading)
                }
                
                if codesService.isLoading {
                    ProgressView()
                        .padding()
                }
                
                if !codesService.codes.isEmpty {
                    List(codesService.codes, id: \.self) { code in
                        Text(code)
                            .font(.monospaced(.body)())
                    }
                }
                
                Spacer()
            }
            .padding()
            .navigationTitle("API Tests")
        }
    }
}

// MARK: - App Entry Point
@main
struct CodesApp: App {
    var body: some Scene {
        WindowGroup {
            TabView {
                ContentView()
                    .tabItem {
                        Image(systemName: "magnifyingglass")
                        Text("Search")
                    }
                
                QuickTestView()
                    .tabItem {
                        Image(systemName: "play.circle")
                        Text("Quick Tests")
                    }
            }
        }
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
