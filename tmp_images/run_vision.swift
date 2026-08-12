
    import Foundation
    import Vision
    import AppKit

    let imgURL = URL(fileURLWithPath: "/Users/yashjha/.gemini/antigravity/brain/0fb60785-059f-4315-9eba-454c6e72ad42/.user_uploaded/media_1786378589124.jpg")
    guard let img = NSImage(contentsOf: imgURL),
          let cgImg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
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
    