import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let size = CGSize(width: 1024, height: 1024)
let colorSpace = CGColorSpaceCreateDeviceRGB()
guard let context = CGContext(
    data: nil,
    width: Int(size.width),
    height: Int(size.height),
    bitsPerComponent: 8,
    bytesPerRow: 0,
    space: colorSpace,
    bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue // Solid RGB, no transparency for Apple AppIcon
) else {
    fatalError("Failed to create CGContext")
}

// 1. Solid Canvas Background: Deep Luxe Pine & Emerald Gradient
let bgColors = [
    CGColor(red: 0.04, green: 0.22, blue: 0.17, alpha: 1.0), // #0a382b
    CGColor(red: 0.02, green: 0.11, blue: 0.08, alpha: 1.0)  // #051c14
] as CFArray

if let bgGrad = CGGradient(colorsSpace: colorSpace, colors: bgColors, locations: [0.0, 1.0]) {
    context.drawRadialGradient(
        bgGrad,
        startCenter: CGPoint(x: 512, y: 550),
        startRadius: 50,
        endCenter: CGPoint(x: 512, y: 512),
        endRadius: 720,
        options: []
    )
}

// Subtle ambient glow behind central logo mark
if let glowGrad = CGGradient(
    colorsSpace: colorSpace,
    colors: [
        CGColor(red: 0.10, green: 0.72, blue: 0.52, alpha: 0.35),
        CGColor(red: 0.05, green: 0.30, blue: 0.22, alpha: 0.0)
    ] as CFArray,
    locations: [0.0, 1.0]
) {
    context.drawRadialGradient(
        glowGrad,
        startCenter: CGPoint(x: 512, y: 512),
        startRadius: 30,
        endCenter: CGPoint(x: 512, y: 512),
        endRadius: 460,
        options: []
    )
}

// 2. Central Isometric Smart Crate / Warehouse Cube
let cx: CGFloat = 512
let cy: CGFloat = 490
let side: CGFloat = 280
let h: CGFloat = 162
let wall: CGFloat = 270

// Ground drop shadow
let shadow = CGMutablePath()
shadow.addEllipse(in: CGRect(x: cx - 320, y: cy - wall * 0.5 - 70, width: 640, height: 160))
context.saveGState()
context.setFillColor(CGColor(red: 0.0, green: 0.04, blue: 0.03, alpha: 0.7))
context.addPath(shadow)
context.fillPath()
context.restoreGState()

// Top Facet (Luminous Mint Jade)
let topFace = CGMutablePath()
topFace.move(to: CGPoint(x: cx, y: cy + wall + h))
topFace.addLine(to: CGPoint(x: cx + side, y: cy + wall))
topFace.addLine(to: CGPoint(x: cx, y: cy + wall - h))
topFace.addLine(to: CGPoint(x: cx - side, y: cy + wall))
topFace.closeSubpath()

let topColors = [
    CGColor(red: 0.16, green: 0.60, blue: 0.46, alpha: 1.0), // #299975
    CGColor(red: 0.09, green: 0.42, blue: 0.32, alpha: 1.0)  // #176b52
] as CFArray
if let topGrad = CGGradient(colorsSpace: colorSpace, colors: topColors, locations: [0.0, 1.0]) {
    context.saveGState()
    context.addPath(topFace)
    context.clip()
    context.drawLinearGradient(topGrad, start: CGPoint(x: cx, y: cy + wall + h), end: CGPoint(x: cx, y: cy + wall - h), options: [])
    context.restoreGState()
}

// Left Facet (Dark Forest)
let leftFace = CGMutablePath()
leftFace.move(to: CGPoint(x: cx - side, y: cy + wall))
leftFace.addLine(to: CGPoint(x: cx, y: cy + wall - h))
leftFace.addLine(to: CGPoint(x: cx, y: cy - h))
leftFace.addLine(to: CGPoint(x: cx - side, y: cy))
leftFace.closeSubpath()

let leftColors = [
    CGColor(red: 0.08, green: 0.34, blue: 0.26, alpha: 1.0),
    CGColor(red: 0.04, green: 0.20, blue: 0.15, alpha: 1.0)
] as CFArray
if let leftGrad = CGGradient(colorsSpace: colorSpace, colors: leftColors, locations: [0.0, 1.0]) {
    context.saveGState()
    context.addPath(leftFace)
    context.clip()
    context.drawLinearGradient(leftGrad, start: CGPoint(x: cx - side, y: cy + wall), end: CGPoint(x: cx, y: cy - h), options: [])
    context.restoreGState()
}

// Right Facet (Deep Pine)
let rightFace = CGMutablePath()
rightFace.move(to: CGPoint(x: cx, y: cy + wall - h))
rightFace.addLine(to: CGPoint(x: cx + side, y: cy + wall))
rightFace.addLine(to: CGPoint(x: cx + side, y: cy))
rightFace.addLine(to: CGPoint(x: cx, y: cy - h))
rightFace.closeSubpath()

let rightColors = [
    CGColor(red: 0.05, green: 0.26, blue: 0.20, alpha: 1.0),
    CGColor(red: 0.02, green: 0.14, blue: 0.11, alpha: 1.0)
] as CFArray
if let rightGrad = CGGradient(colorsSpace: colorSpace, colors: rightColors, locations: [0.0, 1.0]) {
    context.saveGState()
    context.addPath(rightFace)
    context.clip()
    context.drawLinearGradient(rightGrad, start: CGPoint(x: cx, y: cy + wall - h), end: CGPoint(x: cx + side, y: cy), options: [])
    context.restoreGState()
}

// Bevel line highlights
context.saveGState()
context.setStrokeColor(CGColor(red: 0.40, green: 0.90, blue: 0.70, alpha: 0.4))
context.setLineWidth(4.0)
context.addPath(topFace)
context.strokePath()
context.move(to: CGPoint(x: cx, y: cy + wall - h))
context.addLine(to: CGPoint(x: cx, y: cy - h))
context.strokePath()
context.restoreGState()

// 3. Iconic "S" Ribbon & Upward Sales Arrow
let ribbon = CGMutablePath()
// Tail starting at bottom left of cube
ribbon.move(to: CGPoint(x: cx - 220, y: cy + 40))
// Curve across left face to center
ribbon.addCurve(
    to: CGPoint(x: cx, y: cy + 180),
    control1: CGPoint(x: cx - 180, y: cy + 160),
    control2: CGPoint(x: cx - 90, y: cy + 200)
)
// Curve across right face ascending to upper apex
ribbon.addCurve(
    to: CGPoint(x: cx + 250, y: cy + wall + 40),
    control1: CGPoint(x: cx + 90, y: cy + 160),
    control2: CGPoint(x: cx + 190, y: cy + 260)
)
// Arrowhead at apex
ribbon.addLine(to: CGPoint(x: cx + 295, y: cy + wall + 75))
ribbon.addLine(to: CGPoint(x: cx + 260, y: cy + wall + 115))
ribbon.addLine(to: CGPoint(x: cx + 205, y: cy + wall + 55))
// Return contour of ribbon
ribbon.addCurve(
    to: CGPoint(x: cx - 20, y: cy + 110),
    control1: CGPoint(x: cx + 150, y: cy + 210),
    control2: CGPoint(x: cx + 50, y: cy + 120)
)
ribbon.addCurve(
    to: CGPoint(x: cx - 220, y: cy - 30),
    control1: CGPoint(x: cx - 90, y: cy + 90),
    control2: CGPoint(x: cx - 170, y: cy + 10)
)
ribbon.closeSubpath()

let arrowColors = [
    CGColor(red: 0.94, green: 0.38, blue: 0.16, alpha: 1.0), // #f06129 Warm Terracotta
    CGColor(red: 0.98, green: 0.64, blue: 0.14, alpha: 1.0), // #fa9e24 Amber Saffron
    CGColor(red: 1.00, green: 0.90, blue: 0.40, alpha: 1.0)  // #ffe666 Luminous Gold
] as CFArray

if let arrowGrad = CGGradient(colorsSpace: colorSpace, colors: arrowColors, locations: [0.0, 0.5, 1.0]) {
    context.saveGState()
    context.setShadow(offset: CGSize(width: 0, height: -12), blur: 34, color: CGColor(red: 0.96, green: 0.5, blue: 0.15, alpha: 0.85))
    context.addPath(ribbon)
    context.clip()
    context.drawLinearGradient(
        arrowGrad,
        start: CGPoint(x: cx - 220, y: cy - 30),
        end: CGPoint(x: cx + 295, y: cy + wall + 115),
        options: []
    )
    context.restoreGState()
}

// 4. AI Sparkle Diamond Star at Apex
func drawSparkle(center: CGPoint, r: CGFloat, ctx: CGContext) {
    let p = CGMutablePath()
    let pinch: CGFloat = r * 0.22
    p.move(to: CGPoint(x: center.x, y: center.y + r))
    p.addQuadCurve(to: CGPoint(x: center.x + pinch, y: center.y), control: CGPoint(x: center.x + pinch * 0.4, y: center.y + pinch * 0.4))
    p.addLine(to: CGPoint(x: center.x + r, y: center.y))
    p.addQuadCurve(to: CGPoint(x: center.x, y: center.y - pinch), control: CGPoint(x: center.x + pinch * 0.4, y: center.y - pinch * 0.4))
    p.addLine(to: CGPoint(x: center.x, y: center.y - r))
    p.addQuadCurve(to: CGPoint(x: center.x - pinch, y: center.y), control: CGPoint(x: center.x - pinch * 0.4, y: center.y - pinch * 0.4))
    p.addLine(to: CGPoint(x: center.x - r, y: center.y))
    p.addQuadCurve(to: CGPoint(x: center.x, y: center.y + pinch), control: CGPoint(x: center.x - pinch * 0.4, y: center.y + pinch * 0.4))
    p.closeSubpath()

    ctx.saveGState()
    ctx.setShadow(offset: .zero, blur: 28, color: CGColor(red: 1.0, green: 0.95, blue: 0.75, alpha: 1.0))
    ctx.setFillColor(CGColor(red: 1.0, green: 1.0, blue: 1.0, alpha: 1.0))
    ctx.addPath(p)
    ctx.fillPath()
    ctx.restoreGState()
}

drawSparkle(center: CGPoint(x: cx + 285, y: cy + wall + 105), r: 52, ctx: context)
drawSparkle(center: CGPoint(x: cx - 270, y: cy + 320), r: 28, ctx: context)
drawSparkle(center: CGPoint(x: cx + 290, y: cy - 60), r: 22, ctx: context)

// Export Solid PNG
guard let image = context.makeImage() else { fatalError("Image creation failed") }
let destURL = URL(fileURLWithPath: "SmartStock/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png") as CFURL
guard let destination = CGImageDestinationCreateWithURL(destURL, UTType.png.identifier as CFString, 1, nil) else {
    fatalError("Destination creation failed")
}
CGImageDestinationAddImage(destination, image, nil)
if CGImageDestinationFinalize(destination) {
    print("SUCCESS: Rendered solid centered AppIcon-1024.png")
} else {
    fatalError("Failed to finalize image")
}
