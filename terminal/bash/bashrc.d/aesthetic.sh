# Terminal aesthetics — Catppuccin Mocha everywhere.
# Remove this file to undo everything here.

[[ $- != *i* ]] && return   # only for interactive shells

# ── Prompt: Starship (github.com/starship/starship) ──
command -v starship >/dev/null && eval "$(starship init bash)"

# ── Smarter cd: zoxide → use `z <part-of-dir>` ──
command -v zoxide >/dev/null && eval "$(zoxide init bash)"

# ── Fuzzy finder: Ctrl+R history, Ctrl+T files, Alt+C dirs ──
if command -v fzf >/dev/null; then
    eval "$(fzf --bash)"
    export FZF_DEFAULT_OPTS="--height 45% --layout=reverse --border=rounded --info=inline \
--color=bg+:#313244,bg:#1E1E2E,spinner:#F5E0DC,hl:#F38BA8 \
--color=fg:#CDD6F4,header:#F38BA8,info:#CBA6F7,pointer:#F5E0DC \
--color=marker:#B4BEFE,fg+:#CDD6F4,prompt:#CBA6F7,hl+:#F38BA8 \
--color=selected-bg:#45475A,border:#6C7086,label:#CDD6F4"
fi

# ── ls with icons & colours: eza ──
if command -v eza >/dev/null; then
    alias ls='eza --icons=auto --group-directories-first'
    alias ll='eza -l --icons=auto --git --group-directories-first --time-style=relative'
    alias la='eza -la --icons=auto --git --group-directories-first --time-style=relative'
    alias lt='eza --tree --level=2 --icons=auto'
fi

# ── cat with syntax highlighting: bat ──
if command -v bat >/dev/null; then
    export BAT_THEME="ansi"
    alias cat='bat --paging=never --style=plain'
fi

# ── Nicer history ──
HISTSIZE=50000
HISTFILESIZE=100000
HISTCONTROL=ignoreboth:erasedups
shopt -s histappend cdspell autocd 2>/dev/null
bind 'set completion-ignore-case on' 2>/dev/null
bind 'set colored-stats on' 2>/dev/null
bind 'set colored-completion-prefix on' 2>/dev/null
bind 'set show-all-if-ambiguous on' 2>/dev/null

# in kitty, `clear` should also drop any images left on screen
[[ -n $KITTY_WINDOW_ID ]] && alias clear='kitten icat --clear 2>/dev/null; command clear; remfetch'

# Typing `fastfetch` in an interactive shell runs the picture flow (remfetch).
alias fastfetch='remfetch'

# ── Welcome screen (only in kitty, once per window) ──
# Waits until the window has stopped resizing (KDE maximises new windows a
# moment after launch, which would otherwise cut the output off).
if [[ -n $KITTY_WINDOW_ID && -z $_WELCOMED ]] && command -v fastfetch >/dev/null; then
    export _WELCOMED=1
    _prev="" _stable=0
    for _i in {1..20}; do
        _cur=$(stty size 2>/dev/null)
        if [[ $_cur == "$_prev" ]]; then (( ++_stable >= 3 )) && break; else _stable=0; fi
        _prev=$_cur
        sleep 0.03
    done
    unset _prev _cur _stable _i
    kitten icat --clear 2>/dev/null; command clear
    _ff_size=$(stty size 2>/dev/null)             # size the welcome is drawn at
    if command -v remfetch >/dev/null; then remfetch; else fastfetch; fi
fi

# ── Redraw the picture logo on terminal resize (kitty only) ──
# The picture's size is fixed when it is drawn; after a resize it would be cut
# or wrapped, so it is redrawn — the SAME picture, without any intro effect
# (FF_SAME=1). Maximise/minimise send a burst of resize signals, so the handler
# first waits until the size has stopped changing and then redraws once at the
# final size. Only when bash itself is in the foreground (nvim/ssh/... handle
# resizes themselves). New windows (splits, KDE maximising) often get their
# final size just after the welcome was drawn, so that is caught too.
if [[ -n $KITTY_WINDOW_ID ]] && command -v remfetch >/dev/null; then
    : "${_ff_size:=$(stty size 2>/dev/null)}"
    _ff_on_winch() {
        [[ $(ps -o stat= -p $$ 2>/dev/null) == *+* ]] || return
        local size prev="" stable=0 i
        # wait for the window to settle (size unchanged for ~150 ms, max ~1.5 s)
        for i in {1..30}; do
            size=$(stty size 2>/dev/null)
            if [[ $size == "$prev" ]]; then (( ++stable >= 3 )) && break; else stable=0; fi
            prev=$size
            sleep 0.05
        done
        [[ $size == "$_ff_size" ]] && return
        _ff_size=$size
        kitten icat --clear >/dev/null 2>&1
        printf '\e[H\e[2J\e[3J'
        FF_SAME=1 remfetch
        # the screen was wiped under readline, so draw the prompt again
        # (not at startup: bash prints its first prompt itself)
        [[ $1 == startup ]] && return
        # ble.sh draws the prompt itself; just tell it the screen was wiped
        if [[ ${BLE_VERSION-} ]]; then ble/textarea#invalidate; return; fi
        local ps=${PS1@P}
        ps=${ps//$'\001'/}; printf '%s' "${ps//$'\002'/}"
    }
    trap _ff_on_winch WINCH
    # resized while the welcome was being drawn (before the trap existed)?
    [[ $(stty size 2>/dev/null) != "$_ff_size" ]] && _ff_on_winch startup
fi
