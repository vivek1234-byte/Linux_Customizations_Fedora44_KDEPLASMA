#!/usr/bin/env bash
# Undo install.sh: restore the files it backed up, delete the files it added,
# restart plasmashell. Packages installed with dnf are left alone (see the end).
set -uo pipefail

STATE=$HOME/.local/share/kde-rice
[[ -f $STATE/LAST_BACKUP ]] || { echo "Nothing to undo ($STATE/LAST_BACKUP missing)."; exit 1; }
BACKUP=$(cat "$STATE/LAST_BACKUP")
read -rp "Restore the files saved in $BACKUP and remove the installed widgets? [y/N] " a
[[ ${a,,} == y* ]] || exit 0

systemctl --user disable --now sakura-viz.service 2>/dev/null
systemctl --user stop plasma-plasmashell.service 2>/dev/null

# 1. delete what install.sh added (newest first, skip duplicates)
if [[ -f $STATE/ADDED ]]; then
    tac "$STATE/ADDED" | awk '!seen[$0]++' | while read -r p; do
        [[ -n $p && $p == "$HOME"/* ]] && rm -rf -- "$p"
    done
fi
# 2. put the old files back
if [[ -f $BACKUP/MANIFEST ]]; then
    awk '!seen[$0]++' "$BACKUP/MANIFEST" | while read -r rel; do
        mkdir -p "$HOME/$(dirname "$rel")"
        rm -rf -- "${HOME:?}/$rel"
        cp -a "$BACKUP/$rel" "$HOME/$rel"
        echo "restored ~/$rel"
    done
fi
fc-cache -f ~/.local/share/fonts >/dev/null 2>&1
systemctl --user daemon-reload 2>/dev/null
systemctl --user start plasma-plasmashell.service 2>/dev/null
# re-apply whichever Plasma theme the restored plasmarc names (stock Breeze if none)
t=$(kreadconfig6 --file plasmarc --group Theme --key name --default default)
[[ -d ~/.local/share/plasma/desktoptheme/$t || -d /usr/share/plasma/desktoptheme/$t ]] || t=default
plasma-apply-desktoptheme "$t" >/dev/null 2>&1
(qdbus-qt6 org.kde.KWin /KWin reconfigure || qdbus org.kde.KWin /KWin reconfigure) >/dev/null 2>&1
rm -f "$STATE/ADDED" "$STATE/LAST_BACKUP"

cat <<'MSG'

Done. Packages were not removed. To remove them too:
  sudo dnf remove wavetask && sudo dnf copr remove vcalles/wavetask
  sudo dnf remove atuin du-dust duf git-delta glow procs tealdeer cava
  git config --global --unset core.pager   # stop using delta for git
MSG
