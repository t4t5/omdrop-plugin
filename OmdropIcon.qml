import QtQuick
import QtQuick.Shapes
import qs.Commons

// The AirDrop mark: a dot with two waves broadcasting from it. Nothing in a
// Nerd Font draws this, and an SVG asset would not follow the bar's
// foreground colour, so it is a Shape authored on a 24 grid and scaled to
// whatever the caller asks for. Two waves, not AirDrop's three, and heavier
// strokes than the bar's glyph icons: at 12 px three waves run together.
Item {
  id: root

  property color color: Color.foreground
  property real iconSize: Style.font.icon
  property bool crossed: false

  // Drifting, while the radio gate runs. It sways and sinks rather than
  // spinning: the wait is 15-60s and a spinner that long reads as a hang,
  // where drift reads as travel.
  property bool drifting: false

  implicitWidth: iconSize
  implicitHeight: iconSize

  Item {
    anchors.centerIn: parent
    width: 24
    height: 24
    scale: root.iconSize / 24

    // verticalCenterOffset, not y: the item is anchored with centerIn, and an
    // animation on y silently loses to the anchor. Two loops of different
    // length, so they never resolve together and it reads as drift. Each loop
    // ends back at rest, because alwaysRunToEnd finishes the loop in progress
    // when drifting stops: a loop ending at its far swing left the icon
    // tilted in the panel for as long as it stayed open.
    SequentialAnimation on anchors.verticalCenterOffset {
      running: root.drifting
      loops: Animation.Infinite
      alwaysRunToEnd: true
      NumberAnimation { to: 1.6; duration: 750; easing.type: Easing.OutSine }
      NumberAnimation { to: -1.6; duration: 1500; easing.type: Easing.InOutSine }
      NumberAnimation { to: 0; duration: 750; easing.type: Easing.InSine }
    }

    SequentialAnimation on rotation {
      running: root.drifting
      loops: Animation.Infinite
      alwaysRunToEnd: true
      NumberAnimation { to: 4; duration: 950; easing.type: Easing.OutSine }
      NumberAnimation { to: -4; duration: 1900; easing.type: Easing.InOutSine }
      NumberAnimation { to: 0; duration: 950; easing.type: Easing.InSine }
    }

    // CurveRenderer, because the default renderer does not antialias: the
    // arcs came out stair-stepped at bar and panel sizes.
    Shape {
      anchors.fill: parent
      preferredRendererType: Shape.CurveRenderer

      // The waves: arcs about the dot, open 90 degrees at the bottom. The
      // centre sits below the grid's middle because the open bottom leaves
      // the mark's weight above it.
      ShapePath {
        strokeColor: root.color
        fillColor: "transparent"
        strokeWidth: 2
        capStyle: ShapePath.RoundCap
        PathSvg { path: "M8.111 16.889A5.5 5.5 0 1 1 15.889 16.889M5.282 19.718A9.5 9.5 0 1 1 18.718 19.718" }
      }

      ShapePath {
        strokeColor: "transparent"
        fillColor: root.color
        PathSvg { path: "M9.8 13a2.2 2.2 0 1 0 4.4 0a2.2 2.2 0 1 0 -4.4 0z" }
      }

      // Struck through while the radio support is missing. Kept as its own
      // path with a real `d` at all times -- an empty path string takes the
      // whole Shape down with it.
      ShapePath {
        strokeColor: root.crossed ? root.color : "transparent"
        fillColor: "transparent"
        strokeWidth: 2
        capStyle: ShapePath.RoundCap
        PathSvg { path: "M3 21 21 3" }
      }
    }
  }
}
