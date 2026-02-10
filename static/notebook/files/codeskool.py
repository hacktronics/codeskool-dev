"""CodeSkool — Scratch-style Python sprites for JupyterLite notebook.

Uses synchronous XMLHttpRequest through the service worker to send
commands to scratch-vm via the parent page. No ``await`` needed.

Methods send scratch-vm opcodes directly so the bridge can use
getOpcodeFunction() to execute them — same engine as block execution.
"""

import json
from urllib.parse import quote

# ── JS bridge: sync XHR via service worker ─────────────────

_cmd_id = 0
_has_xhr = False

try:
    from js import XMLHttpRequest
    _has_xhr = True
except Exception:
    pass


def _make_cmd(sprite_name, action, params):
    global _cmd_id
    _cmd_id += 1
    return json.dumps({
        "_codeskool": True,
        "id": f"cs-{_cmd_id}",
        "sprite": sprite_name,
        "action": action,
        "params": params,
    })


def _send(sprite_name, action, params):
    """Send command via sync XHR, block for response, return result."""
    cmd = _make_cmd(sprite_name, action, params)
    if not _has_xhr:
        return ""
    try:
        data = json.loads(cmd)
        xhr = XMLHttpRequest.new()
        xhr.open("GET", f"/api/codeskool?id={quote(data['id'])}&cmd={quote(cmd)}", False)
        xhr.send(None)
        return str(xhr.responseText)
    except Exception:
        return ""


# ── Sprite class ────────────────────────────────────────────

class Sprite:

    def __init__(self, name=None):
        resp = _send(name or '', 'create', {})
        self.name = name or 'Sprite1'
        self.x = 0
        self.y = 0
        self.direction = 90
        self._sync(resp)

    def _sync(self, resp):
        """Parse JSON response from bridge, update local state."""
        if not resp:
            return None
        try:
            data = json.loads(resp)
            if 'error' in data:
                return data
            if 'name' in data:
                self.name = data['name']
            if 'x' in data:
                self.x = data['x']
            if 'y' in data:
                self.y = data['y']
            if 'dir' in data:
                self.direction = data['dir']
            return data
        except (json.JSONDecodeError, KeyError):
            return None

    def _do(self, opcode, args=None):
        """Execute a scratch-vm opcode, sync state from response."""
        r = _send(self.name, opcode, args or {})
        self._sync(r)

    def _query(self, opcode, args=None):
        """Execute a getter opcode and return the value."""
        r = _send(self.name, opcode, args or {})
        data = self._sync(r)
        return data.get('val') if data else None

    # ── Motion ──────────────────────────────────────────

    def move_steps(self, steps):
        return self._do('motion_movesteps', {'STEPS': steps})

    def turn_right(self, degrees):
        return self._do('motion_turnright', {'DEGREES': degrees})

    def turn_left(self, degrees):
        return self._do('motion_turnleft', {'DEGREES': degrees})

    def goto_xy(self, x, y):
        return self._do('motion_gotoxy', {'X': x, 'Y': y})

    def set_x(self, x):
        return self._do('motion_setx', {'X': x})

    def set_y(self, y):
        return self._do('motion_sety', {'Y': y})

    def change_x(self, dx):
        return self._do('motion_changexby', {'DX': dx})

    def change_y(self, dy):
        return self._do('motion_changeyby', {'DY': dy})

    def set_direction(self, deg):
        return self._do('motion_pointindirection', {'DIRECTION': deg})

    def bounce_if_on_edge(self):
        return self._do('motion_ifonedgebounce')

    def set_rotation_style(self, style):
        return self._do('motion_setrotationstyle', {'STYLE': style})

    def get_x(self):
        return self._query('motion_xposition')

    def get_y(self):
        return self._query('motion_yposition')

    def get_direction(self):
        return self._query('motion_direction')

    # ── Looks ───────────────────────────────────────────

    def say(self, message):
        return self._do('looks_say', {'MESSAGE': str(message)})

    def think(self, message):
        return self._do('looks_think', {'MESSAGE': str(message)})

    def switch_costume(self, costume):
        return self._do('looks_switchcostumeto', {'COSTUME': costume})

    def next_costume(self):
        return self._do('looks_nextcostume')

    def change_size(self, change):
        return self._do('looks_changesizeby', {'CHANGE': change})

    def set_size(self, size):
        return self._do('looks_setsizeto', {'SIZE': size})

    def show(self):
        return self._do('looks_show')

    def hide(self):
        return self._do('looks_hide')

    def change_effect(self, effect, change):
        return self._do('looks_changeeffectby', {'EFFECT': effect, 'CHANGE': change})

    def set_effect(self, effect, value):
        return self._do('looks_seteffectto', {'EFFECT': effect, 'VALUE': value})

    def clear_effects(self):
        return self._do('looks_cleargraphiceffects')

    def go_to_layer(self, layer):
        """layer: 'front' or 'back'"""
        return self._do('looks_gotofrontback', {'FRONT_BACK': layer})

    def get_costume(self):
        return self._query('looks_costumenumbername', {'NUMBER_NAME': 'name'})

    def get_size(self):
        return self._query('looks_size')

    # ── Pen ─────────────────────────────────────────────

    def pen_down(self):
        return self._do('pen_penDown')

    def pen_up(self):
        return self._do('pen_penUp')

    def pen_clear(self):
        return self._do('pen_clear')

    def pen_stamp(self):
        return self._do('pen_stamp')

    def pen_set_color(self, r, g, b, a=255):
        return self._do('pen_setPenColorToColor', {'COLOR': [r, g, b, a]})

    def pen_set_size(self, size):
        return self._do('pen_setPenSizeTo', {'SIZE': size})

    def pen_change_size(self, change):
        return self._do('pen_changePenSizeBy', {'SIZE': change})

    # ── Sound ───────────────────────────────────────────

    def play_sound(self, sound):
        return self._do('sound_play', {'SOUND_MENU': sound})

    def stop_all_sounds(self):
        return self._do('sound_stopallsounds')

    def set_volume(self, vol):
        return self._do('sound_setvolumeto', {'VOLUME': vol})

    def change_volume(self, change):
        return self._do('sound_changevolumeby', {'VOLUME': change})

    def get_volume(self):
        return self._query('sound_volume')

    # ── Sensing ─────────────────────────────────────────

    def is_touching(self, target_name):
        if isinstance(target_name, Sprite):
            target_name = target_name.name
        return self._query('sensing_touchingobject', {'TOUCHINGOBJECTMENU': target_name})

    def distance_to(self, target_name):
        if isinstance(target_name, Sprite):
            target_name = target_name.name
        return self._query('sensing_distanceto', {'DISTANCETOMENU': target_name})

    def is_key_pressed(self, key):
        return self._query('sensing_keypressed', {'KEY_OPTION': key})

    def get_timer(self):
        return self._query('sensing_timer')

    def reset_timer(self):
        return self._do('sensing_resettimer')

    # ── Events ──────────────────────────────────────────

    def broadcast(self, message):
        return self._do('event_broadcast', {
            'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
        })

    # ── Clone ───────────────────────────────────────────

    def create_clone(self):
        return self._do('control_create_clone_of', {'CLONE_OPTION': '_myself_'})

    # ── Display ─────────────────────────────────────────

    @property
    def position(self):
        return (round(self.x, 1), round(self.y, 1))

    def __repr__(self):
        return f"{self.name}(x={self.x:.0f}, y={self.y:.0f}, dir={self.direction:.0f}°)"


# ── Stage class ────────────────────────────────────────────

class Stage:
    """Controls the stage — backdrops, sound, sensing, events, pen clear."""

    def __init__(self):
        resp = _send('Stage', 'create', {})
        self.name = 'Stage'
        self._sync(resp)

    def _sync(self, resp):
        if not resp:
            return None
        try:
            data = json.loads(resp)
            if 'error' in data:
                return data
            if 'name' in data:
                self.name = data['name']
            return data
        except (json.JSONDecodeError, KeyError):
            return None

    def _do(self, opcode, args=None):
        r = _send(self.name, opcode, args or {})
        self._sync(r)

    def _query(self, opcode, args=None):
        r = _send(self.name, opcode, args or {})
        data = self._sync(r)
        return data.get('val') if data else None

    # ── Looks (Backdrops) ────────────────────────────────

    def switch_backdrop(self, backdrop):
        return self._do('looks_switchbackdropto', {'BACKDROP': backdrop})

    def next_backdrop(self):
        return self._do('looks_nextbackdrop')

    def get_backdrop(self):
        return self._query('looks_backdropnumbername', {'NUMBER_NAME': 'name'})

    def change_effect(self, effect, change):
        return self._do('looks_changeeffectby', {'EFFECT': effect, 'CHANGE': change})

    def set_effect(self, effect, value):
        return self._do('looks_seteffectto', {'EFFECT': effect, 'VALUE': value})

    def clear_effects(self):
        return self._do('looks_cleargraphiceffects')

    # ── Pen ──────────────────────────────────────────────

    def pen_clear(self):
        return self._do('pen_clear')

    # ── Sound ────────────────────────────────────────────

    def play_sound(self, sound):
        return self._do('sound_play', {'SOUND_MENU': sound})

    def stop_all_sounds(self):
        return self._do('sound_stopallsounds')

    def set_volume(self, vol):
        return self._do('sound_setvolumeto', {'VOLUME': vol})

    def change_volume(self, change):
        return self._do('sound_changevolumeby', {'VOLUME': change})

    def get_volume(self):
        return self._query('sound_volume')

    # ── Sensing ──────────────────────────────────────────

    def is_key_pressed(self, key):
        return self._query('sensing_keypressed', {'KEY_OPTION': key})

    def get_timer(self):
        return self._query('sensing_timer')

    def reset_timer(self):
        return self._do('sensing_resettimer')

    # ── Events ───────────────────────────────────────────

    def broadcast(self, message):
        return self._do('event_broadcast', {
            'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
        })

    def __repr__(self):
        return f"Stage()"
