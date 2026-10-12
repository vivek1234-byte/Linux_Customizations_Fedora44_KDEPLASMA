"""kitty kitten: click the fastfetch picture to show the next one.

Mapped in kitty.conf on `left click`. The picture's cells carry its image
id as their 24-bit foreground colour; if the cell under the mouse belongs to a
picture made by ~/.config/fastfetch/ff-logo.py, ask that script to switch it.
"""
import os
import subprocess

from kittens.tui.handler import result_handler

BLOCKS = os.path.join(os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state'),
                      'ff-logo', 'blocks')
SCRIPT = os.path.expanduser('~/.config/fastfetch/ff-logo.py')


def main(args: list[str]) -> None:
    pass


@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss) -> None:
    w = boss.window_id_map.get(target_window_id)
    pos = w.current_mouse_position() if w else None
    if not pos:
        return
    try:
        fg = w.screen.visual_line(pos['cell_y']).cursor_from(pos['cell_x']).fg
    except Exception:
        return
    if fg & 0xff != 2:                     # not a 24-bit colour
        return
    ident = fg >> 8
    if os.path.exists(os.path.join(BLOCKS, f'{ident}.json')):
        subprocess.Popen(['/usr/bin/python3', '-I', SCRIPT, 'next', str(ident)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
