import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else {
    print("Usage: mac_vision_ocr <image_path>")
    exit(1)
}

let imgPath = CommandLine.arguments[1]
let imgURL = URL(fileURLWithPath: imgPath)
guard let img = NSImage(contentsOf: imgURL),
      let cgImg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("Failed to load image")
    exit(1)
}

let request = VNRecognizeTextRequest { request, error in
    guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
    for obs in observations {
        if let candidate = obs.topCandidates(1).first {
            print(candidate.string)
        }
    }
}
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false

let handler = VNImageRequestHandler(cgImage: cgImg, options: [:])
try? handler.perform([request])
