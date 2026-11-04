# Desktop styling decisions

- Consistent rounded controls and cards follow Microsoft Fluent shape guidance: https://fluent2.microsoft.design/shapes
- Visible outlines, readable labels and focus states follow non-text contrast guidance: https://www.w3.org/WAI/WCAG21/understanding/non-text-contrast.html
- Attractive styling supports perceived ease of use, but does not replace functional testing: https://www.nngroup.com/articles/aesthetic-usability-effect/

The implementation preserves native ttk command handling and keyboard behavior. Nine-slice image elements provide button states without rebuilding the widget tree. Images are reused across theme changes. Windows table and input clipping uses the existing native region helper. Cross-platform visual parity still needs native macOS/Linux review.

The white rounded logo tile is used in PNG, SVG and ICO app assets. Python is bundled in Windows executables; existing setup and packaging scripts consume these updated assets. The separate eye tray indicator retains its existing identity.

## Rendering options

The live graph now updates retained canvas items rather than rebuilding them each sample. A local synthetic 90-point benchmark averaged 0.848 ms per callback over 500 calls, with seven retained items. This is callback cost, not an end-to-end frame rate or startup measurement.

For a future visual overhaul, PySide6 + Qt Quick/QML can retain the Python networking backend and use Qt GPU scene-graph rendering: https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph-renderer.html . Tauri uses a Rust core and OS WebView, but integrating the current Python services requires a bridge/sidecar and substantial UI work: https://tauri.app/concept/architecture/ . A language rewrite alone does not establish a performance improvement.
