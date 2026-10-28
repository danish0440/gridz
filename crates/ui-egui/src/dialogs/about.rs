use super::*;

/// Help ▸ About GridZ: the app, its contributors and the AI models that helped. The credits
/// are compiled in (`crate::credits`, docs/contributors.md).
pub(super) fn about(ui: &mut egui::Ui, d: &mut Dialog) {
    ui.horizontal(|ui| {
        for tab in ["About", "Contributors", "Models"] {
            if ui.selectable_label(d.tab == tab, tab).clicked() {
                d.tab = tab.to_string();
            }
        }
    });
    ui.separator();
    match d.tab.as_str() {
        "Contributors" => crate::credits::contributors_ui(ui),
        "Models" => crate::credits::models_ui(ui),
        _ => {
            ui.heading("GridZ");
            ui.label(format!("Version {}", env!("CARGO_PKG_VERSION")));
            // PINTAZ-ABOUT: required credit (Apache-2.0 change notice; ArtCraft brand licence)
            ui.label(egui::RichText::new("by PINTAZ").strong());
            ui.label("Based on GridCraft by Storytold (ArtCraft), Apache-2.0. Changes by PINTAZ TECHNOLOGIES.");
            ui.add_space(4.0);
            ui.label("A clean-room, open-source, Rust-native spreadsheet. ");
            ui.hyperlink_to("github.com/danish0440/gridz", "https://github.com/danish0440/gridz");
            ui.hyperlink_to("Get help on GitHub", "https://github.com/danish0440/gridz/issues");
        }
    }
}
