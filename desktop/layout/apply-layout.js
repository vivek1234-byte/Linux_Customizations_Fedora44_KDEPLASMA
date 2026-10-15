// Plasma desktop script: places the widgets and sets the wallpaper.
// Run by install.sh through:
//   qdbus-qt6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat apply-layout.js)"
// install.sh replaces @WALLPAPER@ and @WITH_DOCK@ first.

var WALLPAPER = "@WALLPAPER@";
var WITH_DOCK = "@WITH_DOCK@" === "yes";

var d = desktops()[0];
var g = screenGeometry(d.screen);

// remove older copies of our widgets (makes the script safe to re-run)
var old = d.widgets();
for (var i = 0; i < old.length; i++) {
    var t = old[i].type;
    if (t.indexOf("com.vivek.") === 0) old[i].remove();
}

// wallpaper: picture + falling sakura petals
d.wallpaperPlugin = "com.vivek.sakura";
d.currentConfigGroup = ["Wallpaper", "com.vivek.sakura", "General"];
d.writeConfig("Image", WALLPAPER);

// Dynamic Island (top centre), Comet Clock under it, Focus Garden bottom-left
d.addWidget("com.vivek.island",    Math.round((g.width - 512) / 2), 0,   512, 64);
d.addWidget("com.vivek.cometclock", Math.round((g.width - 624) / 2), 64,  624, 304);
d.addWidget("com.vivek.focus",     48, Math.max(64, g.height - 600),    352, 470);

// dock: swap the Icons-only Task Manager for Wave Task Manager (keeps pinned apps)
if (WITH_DOCK) {
    var ps = panels();
    for (var p = 0; p < ps.length; p++) {
        var panel = ps[p];
        if (panel.location !== "bottom") continue;
        var ws = panel.widgets();
        for (var j = 0; j < ws.length; j++) {
            if (ws[j].type !== "org.kde.plasma.icontasks" && ws[j].type !== "org.kde.plasma.taskmanager") continue;
            ws[j].currentConfigGroup = ["General"];
            var launchers = ws[j].readConfig("launchers", []);
            if (typeof launchers === "string") launchers = launchers.length ? launchers.split(",") : [];
            ws[j].remove();
            var wave = panel.addWidget("org.vicko.wavetask");
            wave.currentConfigGroup = ["General"];
            wave.writeConfig("launchers", ["applications:sakura-menu.desktop"].concat(launchers));
            wave.writeConfig("skinName", "Tahoe Dark");
            wave.writeConfig("iconSize", 46);
            wave.writeConfig("magnification", 80.0);
            wave.writeConfig("showReflection", true);
            wave.writeConfig("indicateAudioStreams", true);
            panel.height = 92;
            panel.writeConfig("backgroundHints", 4);
            panel.writeConfig("userBackgroundHints", 4);
            panel.reloadConfig();
            break;
        }
        break;
    }
}
// Tray Island: launcher + system tray in a small floating, auto-hiding pill on the
// left edge (its indigo→plum glass comes from the SakuraIsland Plasma theme).
// Uses the Cutoff launcher when it is installed (KDE Store), Kickoff otherwise.
var LAUNCHERS = ["com.github.galib.cutoff", "org.kde.plasma.kickoff", "org.kde.plasma.kicker",
                 "org.kde.plasma.kickerdash"];
var island = null;
var all = panels();
for (var k = 0; k < all.length; k++) {
    if (all[k].location === "left") { island = all[k]; break; }
}
if (!island) {
    // the tray and the launcher move out of the other panels into the island
    for (var k = 0; k < all.length; k++) {
        var aw = all[k].widgets();
        for (var j = 0; j < aw.length; j++) {
            if (aw[j].type === "org.kde.plasma.systemtray" || LAUNCHERS.indexOf(aw[j].type) >= 0) aw[j].remove();
        }
    }
    island = new Panel("org.kde.panel");
    island.location = "left";
    island.addWidget(knownWidgetTypes.indexOf(LAUNCHERS[0]) >= 0 ? LAUNCHERS[0] : LAUNCHERS[1]);
    island.addWidget("org.kde.plasma.systemtray");
}
island.height = 38;
island.floating = true;
island.lengthMode = "fit";
island.alignment = "center";
island.offset = 0;
island.hiding = "autohide";
island.opacity = "translucent";

print("layout applied");
