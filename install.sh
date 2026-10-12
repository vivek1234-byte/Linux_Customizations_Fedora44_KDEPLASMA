#!/usr/bin/env bash
# Installs the terminal + KDE Plasma desktop customizations from this repo.
#
#   ./install.sh               everything (asks before each big step)
#   ./install.sh --terminal    only the terminal part
#   ./install.sh --desktop     only the desktop part
#   ./install.sh --yes         don't ask, use the defaults
#
# Every file that gets replaced is backed up first to
#   ~/.local/share/kde-rice/backup-<date>/   (uninstall.sh restores the newest one)
#
# Tested on Fedora 44 KDE Plasma 6.7 (Wayland), bash.

set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
STATE=$HOME/.local/share/kde-rice
BACKUP=$STATE/backup-$(date +%Y%m%d-%H%M%S)
DL=$(mktemp -d)
trap 'rm -rf "$DL"' EXIT

DO_TERMINAL=1 DO_DESKTOP=1 ASSUME_YES=0
for a in "$@"; do
    case $a in
        --terminal) DO_DESKTOP=0 ;;
        --desktop)  DO_TERMINAL=0 ;;
        --yes|-y)   ASSUME_YES=1 ;;
        -h|--help)  sed -n 2,12p "$0"; exit 0 ;;
        *) echo "unknown option: $a"; exit 1 ;;
    esac
done

# ── helpers ──────────────────────────────────────────────────────────────
c_pink=$'\e[38;2;247;168;196m' c_blue=$'\e[38;2;142;197;255m' c_dim=$'\e[2m' c_off=$'\e[0m'
step() { printf '\n%s✿ %s%s\n' "$c_pink" "$*" "$c_off"; }
info() { printf '  %s%s%s\n' "$c_dim" "$*" "$c_off"; }
ask() {   # ask "question" default(y/n)
    local def=${2:-y} ans
    (( ASSUME_YES )) && { [[ $def == y ]]; return; }
    read -rp "  $1 [$( [[ $def == y ]] && echo Y/n || echo y/N )] " ans
    ans=${ans:-$def}; [[ ${ans,,} == y* ]]
}
backup() {   # backup <path>  (keeps the path relative to $HOME)
    local p=$1
    [[ -e $p ]] || return 0
    local rel=${p#"$HOME"/}
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -a "$p" "$BACKUP/$rel"
    echo "$rel" >> "$BACKUP/MANIFEST"
}
put() {      # put <src> <dest>   copy, backing up whatever was there
    local src=$1 dest=$2
    [[ -e $dest ]] || added "$dest"     # new file: uninstall deletes it
    backup "$dest"
    mkdir -p "$(dirname "$dest")"
    rm -rf "$dest"
    cp -a "$src" "$dest"
}
added() { echo "$1" >> "$STATE/ADDED"; }   # files/dirs uninstall.sh should delete
subst() {    # replace @HOME@ / @USER_NAME@ / @WALLPAPER@ in a file
    sed -i -e "s|@HOME@|$HOME|g" -e "s|@USER_NAME@|$USER_NAME|g" -e "s|@WALLPAPER@|$WALLPAPER|g" "$1"
}
gh_latest() { # gh_latest owner/repo asset-name -> download URL of the newest release asset
    echo "https://github.com/$1/releases/latest/download/$2"
}

[[ -f /etc/fedora-release ]] || echo "${c_blue}Note:${c_off} written for Fedora; on other distros install the packages yourself."
mkdir -p "$STATE" "$BACKUP"

DISPLAY_NAME=$(getent passwd "$USER" | cut -d: -f5 | cut -d, -f1)
DISPLAY_NAME=${DISPLAY_NAME%% *}
[[ -n $DISPLAY_NAME ]] || DISPLAY_NAME=${USER^}
USER_NAME=$DISPLAY_NAME
WALLPAPER=""

# ═════════════════════════════════════════════════════════════════════════
#  TERMINAL
# ═════════════════════════════════════════════════════════════════════════
if (( DO_TERMINAL )); then
    step "Terminal: packages (needs sudo)"
    PKGS=(kitty fastfetch fzf zoxide eza bat btop lazygit
          atuin du-dust duf git-delta glow procs tealdeer
          python3-pillow curl unzip xz)
    info "${PKGS[*]}"
    if ask "Install these with dnf?"; then
        sudo dnf install -y "${PKGS[@]}" || echo "  some packages failed — continuing"
    fi

    step "Terminal: tools not packaged in Fedora (installed to ~/.local)"
    mkdir -p ~/.local/bin ~/.local/share ~/.local/share/fonts
    if ! command -v starship >/dev/null; then
        info "starship prompt"
        curl -fsSL https://starship.rs/install.sh | sh -s -- -y -b "$HOME/.local/bin" >/dev/null
    fi
    if ! command -v yazi >/dev/null; then
        info "yazi file manager"
        curl -fsSL -o "$DL/yazi.zip" "$(gh_latest sxyazi/yazi yazi-x86_64-unknown-linux-gnu.zip)"
        unzip -qo "$DL/yazi.zip" -d "$DL"
        install -m755 "$DL"/yazi-x86_64-unknown-linux-gnu/{yazi,ya} ~/.local/bin/
        added "$HOME/.local/bin/yazi"; added "$HOME/.local/bin/ya"
    fi
    if [[ ! -f ~/.local/share/blesh/ble.sh ]]; then
        info "ble.sh (autosuggestions + syntax highlighting for bash)"
        curl -fsSL -o "$DL/blesh.tar.xz" https://github.com/akinomyoga/ble.sh/releases/download/nightly/ble-nightly.tar.xz
        tar xJf "$DL/blesh.tar.xz" -C "$DL"
        cp -r "$DL/ble-nightly" ~/.local/share/blesh
        added "$HOME/.local/share/blesh"
    fi
    if ! fc-list | grep -q "JetBrainsMono Nerd Font"; then
        info "JetBrainsMono Nerd Font"
        curl -fsSL -o "$DL/jbm.tar.xz" "$(gh_latest ryanoasis/nerd-fonts JetBrainsMono.tar.xz)"
        mkdir -p ~/.local/share/fonts/JetBrainsMonoNerd
        tar xJf "$DL/jbm.tar.xz" -C ~/.local/share/fonts/JetBrainsMonoNerd
        added "$HOME/.local/share/fonts/JetBrainsMonoNerd"
        fc-cache -f ~/.local/share/fonts >/dev/null
    fi

    step "Terminal: config files"
    put "$REPO/terminal/kitty/kitty.conf"        ~/.config/kitty/kitty.conf
    put "$REPO/terminal/kitty/ff_dclick.py"      ~/.config/kitty/ff_dclick.py
    put "$REPO/terminal/starship/starship.toml"  ~/.config/starship.toml
    put "$REPO/terminal/bash/bashrc.d/aesthetic.sh" ~/.bashrc.d/aesthetic.sh
    put "$REPO/terminal/bash/bashrc.d/tools.sh"  ~/.bashrc.d/tools.sh
    put "$REPO/terminal/lazygit/config.yml"      ~/.config/lazygit/config.yml
    for f in config.jsonc cutout.py design.py ff-logo.py make-images.py; do
        put "$REPO/terminal/fastfetch/$f" ~/.config/fastfetch/$f
    done
    subst ~/.config/fastfetch/make-images.py
    chmod +x ~/.config/fastfetch/ff-logo.py ~/.config/fastfetch/make-images.py
    put "$REPO/terminal/bin/remfetch" ~/.local/bin/remfetch; chmod +x ~/.local/bin/remfetch
    ln -sf ~/.config/fastfetch/make-images.py ~/.local/bin/ff-images; added "$HOME/.local/bin/ff-images"
    mkdir -p ~/.config/fastfetch/images ~/Pictures/ff
    info "configs copied (old ones backed up to $BACKUP)"

    step "Terminal: ~/.bashrc"
    backup ~/.bashrc
    touch ~/.bashrc
    if ! grep -q 'bashrc.d' ~/.bashrc; then
        cat >> ~/.bashrc <<'RC'

# >>> kde-rice: load ~/.bashrc.d >>>
if [ -d ~/.bashrc.d ]; then
    for rc in ~/.bashrc.d/*; do [ -f "$rc" ] && . "$rc"; done
fi
unset rc
# <<< kde-rice <<<
RC
    fi
    if ! grep -q 'kde-rice: ble.sh' ~/.bashrc; then
        # ble.sh must be sourced first (no-attach) and attached last
        { printf '# >>> kde-rice: ble.sh (top) >>>\n[[ $- == *i* && -f ~/.local/share/blesh/ble.sh ]] && source ~/.local/share/blesh/ble.sh --noattach\n# <<< kde-rice <<<\n\n'; cat ~/.bashrc; } > "$DL/bashrc"
        cat "$DL/bashrc" > ~/.bashrc
        printf '\n# >>> kde-rice: ble.sh (attach, keep last) >>>\n[[ ${BLE_VERSION-} ]] && ble-attach\n# <<< kde-rice <<<\n' >> ~/.bashrc
    fi
    info "ble.sh + ~/.bashrc.d hooked in"

    step "Terminal: git (delta pager) and caches"
    git config --global core.pager delta
    git config --global interactive.diffFilter 'delta --color-only'
    git config --global delta.navigate true
    git config --global delta.line-numbers true
    git config --global delta.side-by-side true
    git config --global delta.syntax-theme 'Monokai Extended'
    git config --global merge.conflictStyle zdiff3
    command -v atuin >/dev/null && atuin import bash >/dev/null 2>&1 || true
    command -v tldr  >/dev/null && tldr --update >/dev/null 2>&1 || true

    step "Terminal: picture tools for fastfetch (optional, ~400 MB)"
    info "Real-ESRGAN (anime upscale) + isnet-anime (background removal) for the 'ff-images' command"
    if ask "Install the picture tools?" n; then
        T=~/.local/share/ff-tools
        mkdir -p "$T/models" "$T/realesrgan"
        python3 -m venv "$T/venv"
        "$T/venv/bin/pip" install -q numpy onnxruntime pillow
        curl -fsSL -o "$T/models/isnet-anime.onnx" \
            https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx
        curl -fsSL -o "$DL/esrgan.zip" \
            https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip
        unzip -qo "$DL/esrgan.zip" -d "$T/realesrgan"
        chmod +x "$T/realesrgan/realesrgan-ncnn-vulkan"
        added "$T"
        info "done — put pictures in ~/Pictures/ff and run: ff-images"
    fi
fi

# ═════════════════════════════════════════════════════════════════════════
#  DESKTOP (KDE Plasma 6)
# ═════════════════════════════════════════════════════════════════════════
if (( DO_DESKTOP )); then
    command -v plasmashell >/dev/null || { echo "plasmashell not found — skipping the desktop part"; exit 0; }
    QDBUS=$(command -v qdbus-qt6 || command -v qdbus6 || command -v qdbus)

    step "Desktop: your details"
    if (( ! ASSUME_YES )); then
        read -rp "  Name for the clock greeting [$USER_NAME]: " n; USER_NAME=${n:-$USER_NAME}
        read -rp "  Wallpaper picture (path, Enter = keep current wallpaper): " w
        [[ -n ${w:-} ]] && WALLPAPER="file://$(realpath "$w")"
    fi
    if [[ -z $WALLPAPER ]]; then   # reuse the picture the desktop already shows
        WALLPAPER=$(grep -m1 -A1 '\[Wallpaper\]\[org.kde.image\]\[General\]' \
                    ~/.config/plasma-org.kde.plasma.desktop-appletsrc 2>/dev/null | sed -n 's/^Image=//p')
        [[ $WALLPAPER == file://* || -z $WALLPAPER ]] || WALLPAPER="file://$WALLPAPER"
        [[ -n $WALLPAPER ]] || WALLPAPER="file:///usr/share/wallpapers/Next/contents/images/1920x1080.png"
    fi
    info "greeting: $USER_NAME   wallpaper: $WALLPAPER"

    step "Desktop: fonts, widgets, wallpaper plugin, icons, colours"
    F=~/.local/share/fonts/kde-rice; mkdir -p "$F"; cp "$REPO"/desktop/fonts/*.ttf "$F"/; added "$F"
    fc-cache -f ~/.local/share/fonts >/dev/null
    for p in "$REPO"/desktop/plasmoids/*/; do
        id=$(basename "$p"); dest=~/.local/share/plasma/plasmoids/$id
        put "$p" "$dest"; added "$dest"
    done
    # the clock ships its fonts inside the package (works before a re-login)
    mkdir -p ~/.local/share/plasma/plasmoids/com.vivek.cometclock/contents/fonts
    cp "$REPO"/desktop/fonts/*.ttf ~/.local/share/plasma/plasmoids/com.vivek.cometclock/contents/fonts/
    subst ~/.local/share/plasma/plasmoids/com.vivek.cometclock/contents/ui/ClockFace.qml
    put "$REPO/desktop/wallpapers/com.vivek.sakura" ~/.local/share/plasma/wallpapers/com.vivek.sakura
    added "$HOME/.local/share/plasma/wallpapers/com.vivek.sakura"
    subst ~/.local/share/plasma/wallpapers/com.vivek.sakura/contents/config/main.xml
    put "$REPO/desktop/icons" ~/.local/share/icons/aesthetic-launchers; added "$HOME/.local/share/icons/aesthetic-launchers"
    put "$REPO/desktop/applications/sakura-menu.desktop" ~/.local/share/applications/sakura-menu.desktop
    subst ~/.local/share/applications/sakura-menu.desktop; added "$HOME/.local/share/applications/sakura-menu.desktop"
    for c in "$REPO"/desktop/color-schemes/*.colors; do
        put "$c" ~/.local/share/color-schemes/$(basename "$c"); added "$HOME/.local/share/color-schemes/$(basename "$c")"
    done
    put "$REPO/desktop/desktoptheme/KimiNoNaWa" ~/.local/share/plasma/desktoptheme/KimiNoNaWa
    added "$HOME/.local/share/plasma/desktoptheme/KimiNoNaWa"

    WITH_DOCK=no
    step "Desktop: macOS-style zoom dock (Wave Task Manager, needs sudo)"
    info "comes from the developer's Fedora COPR repo vcalles/wavetask (not part of Fedora)"
    if rpm -q wavetask >/dev/null 2>&1; then
        WITH_DOCK=yes
    elif ask "Add the COPR repo and install wavetask?" y; then
        sudo dnf copr enable -y vcalles/wavetask && sudo dnf install -y wavetask && WITH_DOCK=yes \
            || echo "  wavetask install failed — keeping your current task manager"
    fi

    step "Desktop: KWin effects + pink accent"
    backup ~/.config/kwinrc; backup ~/.config/kdeglobals
    for e in blur wobblywindows magiclamp cube scale sheet slide slidingpopups dimscreen; do
        kwriteconfig6 --file kwinrc --group Plugins --key "${e}Enabled" true
    done
    kwriteconfig6 --file kwinrc --group Plugins --key fadeEnabled false
    kwriteconfig6 --file kwinrc --group Plugins --key glideEnabled false
    kwriteconfig6 --file kwinrc --group Plugins --key squashEnabled false
    "$QDBUS" org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true
    plasma-apply-colorscheme --accent-color "#DA6E8A" >/dev/null 2>&1 || true

    step "Desktop: lock screen (same picture + petals)"
    backup ~/.config/kscreenlockerrc
    kwriteconfig6 --file kscreenlockerrc --group Greeter --key WallpaperPlugin com.vivek.sakura
    kwriteconfig6 --file kscreenlockerrc --group Greeter --group Wallpaper --group com.vivek.sakura --group General --key Image "$WALLPAPER"

    step "Desktop: placing widgets (plasmashell restarts, the screen flickers once)"
    backup ~/.config/plasma-org.kde.plasma.desktop-appletsrc
    backup ~/.config/plasmashellrc
    systemctl --user restart plasma-plasmashell.service 2>/dev/null || { kquitapp6 plasmashell; kstart plasmashell & }
    sleep 6
    sed -e "s|@WALLPAPER@|$WALLPAPER|" -e "s|@WITH_DOCK@|$WITH_DOCK|" "$REPO/desktop/layout/apply-layout.js" > "$DL/layout.js"
    "$QDBUS" org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat "$DL/layout.js")" \
        || echo "  could not place the widgets automatically — add them via right-click → Add Widgets"
fi

echo "$BACKUP" > "$STATE/LAST_BACKUP"
step "Done!"
info "Open a new kitty window to see the terminal changes."
info "Backups of replaced files: $BACKUP"
info "Undo everything: ./uninstall.sh"
