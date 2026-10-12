# Extra CLI tools: atuin, yazi, delta, tealdeer, dust, duf, procs, glow.

[[ $- != *i* ]] && return

# ── atuin: searchable history on Ctrl+R (Up arrow left alone) ──
command -v atuin >/dev/null && eval "$(atuin init bash --disable-up-arrow)"

# ── yazi: `y` opens the file manager; quitting with q cds into its dir ──
y() {
    local tmp cwd
    tmp=$(mktemp -t "yazi-cwd.XXXXXX")
    yazi "$@" --cwd-file="$tmp"
    IFS= read -r -d '' cwd < "$tmp"
    [[ -n $cwd && $cwd != "$PWD" ]] && builtin cd -- "$cwd"
    rm -f -- "$tmp"
}

# ── ble.sh colours to match the pink/lavender theme ──
if [[ ${BLE_VERSION-} ]]; then
    ble-face auto_complete='fg=#6C7086'
    ble-face command_builtin='fg=#C3A6FF' command_alias='fg=#94E2D5' command_function='fg=#94E2D5'
    ble-face command_file='fg=#A6E3A1' syntax_error='fg=#F38BA8,bold'
    ble-face filename_directory='fg=#89B4FA,underline'
    bleopt exec_errexit_mark=  # no "[ble: exit 1]" lines
fi
