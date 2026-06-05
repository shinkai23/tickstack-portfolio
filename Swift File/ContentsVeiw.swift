//
//  ContentView.swift
//  TickStack
//
//  Created for the TickStack project.
//

import SwiftUI
import SafariServices

struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let vc = SFSafariViewController(url: url)
        return vc
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

// ボタンが押された時に、SafariViewを表示
struct ContentView: View {
    @State private var showSafari = false
    let url = URL(string: "https://tickstackm5.pythonanywhere.com")!

    var body: some View {
        VStack {
            Button("Open site (in-app Safari)") {
                showSafari = true
            }
            .sheet(isPresented: $showSafari) {
                SafariView(url: url)
            }
        }.padding()
    }
}
