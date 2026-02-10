"""CodeSkool — Scratch-style Python sprites.

Uses synchronous XMLHttpRequest through the service worker to send
commands to scratch-vm via the parent page. No ``await`` needed.

Methods send scratch-vm opcodes directly so the bridge can use
getOpcodeFunction() to execute them — same engine as block execution.

Works in both notebook mode (JupyterLite) and editor mode (Pyodide worker).
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

# Set by pyodide.mjs before import (editor mode only)
__SPRITE_NAME__ = "Sprite1"
__IS_STAGE__ = False


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


def _parse_val(resp):
    """Parse JSON response and return the 'val' field."""
    if not resp:
        return None
    try:
        data = json.loads(resp)
        return data.get('val')
    except (json.JSONDecodeError, KeyError):
        return None


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

    def goto_position(self, target):
        return self._do('motion_goto', {'TO': target})

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

    def point_towards(self, target):
        return self._do('motion_pointtowards', {'TOWARDS': target})

    def set_rotation_style(self, style):
        return self._do('motion_setrotationstyle', {'STYLE': style})

    def get_x(self):
        return self._query('motion_xposition')

    def get_y(self):
        return self._query('motion_yposition')

    def get_direction(self):
        return self._query('motion_direction')

    # ── Looks ───────────────────────────────────────────

    def say(self, message, secs=None):
        if secs is not None:
            return self._do('looks_sayforsecs', {'MESSAGE': str(message), 'SECS': secs})
        return self._do('looks_say', {'MESSAGE': str(message)})

    def think(self, message, secs=None):
        if secs is not None:
            return self._do('looks_thinkforsecs', {'MESSAGE': str(message), 'SECS': secs})
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

    def change_layer(self, direction, amount):
        return self._do('looks_goforwardbackwardlayers', {'FORWARD_BACKWARD': direction, 'NUM': amount})

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

    def pen_change_color(self, param, change):
        return self._do('pen_changePenColorParamBy', {'COLOR_PARAM': param, 'VALUE': change})

    def pen_set_size(self, size):
        return self._do('pen_setPenSizeTo', {'SIZE': size})

    def pen_change_size(self, change):
        return self._do('pen_changePenSizeBy', {'SIZE': change})

    # ── Sound ───────────────────────────────────────────

    def play_until_done(self, sound):
        return self._do('sound_playuntildone', {'SOUND_MENU': sound})

    def play_sound(self, sound):
        return self._do('sound_play', {'SOUND_MENU': sound})

    def stop_all_sounds(self):
        return self._do('sound_stopallsounds')

    def set_volume(self, vol):
        return self._do('sound_setvolumeto', {'VOLUME': vol})

    def change_sound_effect(self, effect, change):
        return self._do('sound_changeeffectby', {'EFFECT': effect, 'VALUE': change})

    def set_sound_effect(self, effect, value):
        return self._do('sound_seteffectto', {'EFFECT': effect, 'VALUE': value})

    def clear_sound_effects(self):
        return self._do('sound_cleareffects')

    def change_volume(self, change):
        return self._do('sound_changevolumeby', {'VOLUME': change})

    def get_volume(self):
        return self._query('sound_volume')

    # ── Sensing ─────────────────────────────────────────

    def is_touching(self, target_name):
        if isinstance(target_name, Sprite):
            target_name = target_name.name
        return self._query('sensing_touchingobject', {'TOUCHINGOBJECTMENU': target_name})

    def is_touching_color(self, r, g, b, a=255):
        return self._query('sensing_touchingcolor', {'COLOR': [r, g, b, a]})

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

    def broadcast_and_wait(self, message):
        return self._do('event_broadcastandwait', {
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


# ── Pen class (standalone helper) ─────────────────────────

class Pen:
    """Convenience class for pen operations on a sprite."""

    def __init__(self, sprite=None):
        self.sprite_name = sprite.name if sprite else __SPRITE_NAME__

    def down(self):
        _send(self.sprite_name, 'pen_penDown', {})

    def up(self):
        _send(self.sprite_name, 'pen_penUp', {})

    def clear(self):
        _send(self.sprite_name, 'pen_clear', {})

    def stamp(self):
        _send(self.sprite_name, 'pen_stamp', {})

    def set_color(self, r, g, b, a=255):
        _send(self.sprite_name, 'pen_setPenColorToColor', {'COLOR': [r, g, b, a]})

    def set_size(self, size):
        _send(self.sprite_name, 'pen_setPenSizeTo', {'SIZE': size})

    def change_size(self, change):
        _send(self.sprite_name, 'pen_changePenSizeBy', {'SIZE': change})


# ── Whizz (RC Car) class ─────────────────────────────────

class Whizz:
    """Controls the Whizz RC Car extension."""

    def __init__(self, sprite_name=None):
        self.sprite_name = sprite_name or __SPRITE_NAME__

    def move_forward(self, steps=1):
        _send(self.sprite_name, 'rcCar_moveForward', {'STEPS': steps})

    def move_backward(self, steps=1):
        _send(self.sprite_name, 'rcCar_moveBackward', {'STEPS': steps})

    def turn_left(self, degrees=90):
        _send(self.sprite_name, 'rcCar_turnLeft', {'DEGREES': degrees})

    def turn_right(self, degrees=90):
        _send(self.sprite_name, 'rcCar_turnRight', {'DEGREES': degrees})

    def toggle_lights(self):
        _send(self.sprite_name, 'rcCar_toggleLights', {})

    def toggle_turbo(self):
        _send(self.sprite_name, 'rcCar_toggleTurboMode', {})


# ── SeaQuest class ────────────────────────────────────────

class SeaQuest:
    """Controls the SeaQuest extension."""

    def __init__(self, sprite_name=None):
        self.sprite_name = sprite_name or __SPRITE_NAME__

    def move_north(self, steps=1):
        _send(self.sprite_name, 'seaQuest_moveNorth', {'STEPS': steps})

    def move_south(self, steps=1):
        _send(self.sprite_name, 'seaQuest_moveSouth', {'STEPS': steps})

    def move_east(self, steps=1):
        _send(self.sprite_name, 'seaQuest_moveEast', {'STEPS': steps})

    def move_west(self, steps=1):
        _send(self.sprite_name, 'seaQuest_moveWest', {'STEPS': steps})


# ── Standalone convenience functions ──────────────────────
# These operate on the sprite identified by __SPRITE_NAME__

def _sprite_name():
    return __SPRITE_NAME__

# Motion
def move_steps(steps):
    _send(_sprite_name(), 'motion_movesteps', {'STEPS': steps})

def turn_right(degrees):
    _send(_sprite_name(), 'motion_turnright', {'DEGREES': degrees})

def turn_left(degrees):
    _send(_sprite_name(), 'motion_turnleft', {'DEGREES': degrees})

def goto_position(target):
    _send(_sprite_name(), 'motion_goto', {'TO': target})

def goto_xy(x, y):
    _send(_sprite_name(), 'motion_gotoxy', {'X': x, 'Y': y})

def get_x():
    return _parse_val(_send(_sprite_name(), 'motion_xposition', {}))

def get_y():
    return _parse_val(_send(_sprite_name(), 'motion_yposition', {}))

def get_direction():
    return _parse_val(_send(_sprite_name(), 'motion_direction', {}))

def set_direction(deg):
    _send(_sprite_name(), 'motion_pointindirection', {'DIRECTION': deg})

def point_towards(target):
    _send(_sprite_name(), 'motion_pointtowards', {'TOWARDS': target})

def change_x(dx):
    _send(_sprite_name(), 'motion_changexby', {'DX': dx})

def change_y(dy):
    _send(_sprite_name(), 'motion_changeyby', {'DY': dy})

def set_x(x):
    _send(_sprite_name(), 'motion_setx', {'X': x})

def set_y(y):
    _send(_sprite_name(), 'motion_sety', {'Y': y})

def bounce_if_on_edge():
    _send(_sprite_name(), 'motion_ifonedgebounce', {})

def set_rotation_style(style):
    _send(_sprite_name(), 'motion_setrotationstyle', {'STYLE': style})

# Looks
def sprite_says(message):
    _send(_sprite_name(), 'looks_say', {'MESSAGE': str(message)})

def sprite_think(message):
    _send(_sprite_name(), 'looks_think', {'MESSAGE': str(message)})

def switch_costume(costume):
    _send(_sprite_name(), 'looks_switchcostumeto', {'COSTUME': costume})

def next_costume():
    _send(_sprite_name(), 'looks_nextcostume', {})

def switch_backdrop(backdrop):
    _send(_sprite_name(), 'looks_switchbackdropto', {'BACKDROP': backdrop})

def next_backdrop():
    _send(_sprite_name(), 'looks_nextbackdrop', {})

def change_size(change):
    _send(_sprite_name(), 'looks_changesizeby', {'CHANGE': change})

def set_size(size):
    _send(_sprite_name(), 'looks_setsizeto', {'SIZE': size})

def change_effect(effect, change):
    _send(_sprite_name(), 'looks_changeeffectby', {'EFFECT': effect, 'CHANGE': change})

def set_effect(effect, value):
    _send(_sprite_name(), 'looks_seteffectto', {'EFFECT': effect, 'VALUE': value})

def clear_effects():
    _send(_sprite_name(), 'looks_cleargraphiceffects', {})

def show_sprite():
    _send(_sprite_name(), 'looks_show', {})

def hide_sprite():
    _send(_sprite_name(), 'looks_hide', {})

def go_to_layer(layer):
    _send(_sprite_name(), 'looks_gotofrontback', {'FRONT_BACK': layer})

def change_layer(direction, amount):
    _send(_sprite_name(), 'looks_goforwardbackwardlayers', {'FORWARD_BACKWARD': direction, 'NUM': amount})

def get_costume():
    return _parse_val(_send(_sprite_name(), 'looks_costumenumbername', {'NUMBER_NAME': 'name'}))

def get_backdrop():
    return _parse_val(_send(_sprite_name(), 'looks_backdropnumbername', {'NUMBER_NAME': 'name'}))

def get_sprite_size():
    return _parse_val(_send(_sprite_name(), 'looks_size', {}))

# Sound
def play_until_done(sound):
    _send(_sprite_name(), 'sound_playuntildone', {'SOUND_MENU': sound})

def play_sound(sound):
    _send(_sprite_name(), 'sound_play', {'SOUND_MENU': sound})

def stop_all_sounds():
    _send(_sprite_name(), 'sound_stopallsounds', {})

def change_sound_effect(effect, change):
    _send(_sprite_name(), 'sound_changeeffectby', {'EFFECT': effect, 'VALUE': change})

def set_sound_effect(effect, value):
    _send(_sprite_name(), 'sound_seteffectto', {'EFFECT': effect, 'VALUE': value})

def clear_sound_effects():
    _send(_sprite_name(), 'sound_cleareffects', {})

def change_volume(change):
    _send(_sprite_name(), 'sound_changevolumeby', {'VOLUME': change})

def set_volume_to(vol):
    _send(_sprite_name(), 'sound_setvolumeto', {'VOLUME': vol})

def get_volume():
    return _parse_val(_send(_sprite_name(), 'sound_volume', {}))

# Control
def create_clone():
    _send(_sprite_name(), 'control_create_clone_of', {'CLONE_OPTION': '_myself_'})

# Sensing
def is_touching(target_name):
    return _parse_val(_send(_sprite_name(), 'sensing_touchingobject', {'TOUCHINGOBJECTMENU': target_name}))

def is_touching_color(r, g, b, a=255):
    return _parse_val(_send(_sprite_name(), 'sensing_touchingcolor', {'COLOR': [r, g, b, a]}))

def distance_to(target_name):
    return _parse_val(_send(_sprite_name(), 'sensing_distanceto', {'DISTANCETOMENU': target_name}))

def ask_question(question):
    return _parse_val(_send(_sprite_name(), 'sensing_askandwait', {'QUESTION': question}))

def get_answer():
    return _parse_val(_send(_sprite_name(), 'sensing_answer', {}))

def is_key_pressed(key):
    return _parse_val(_send(_sprite_name(), 'sensing_keypressed', {'KEY_OPTION': key}))

def mouse_x():
    return _parse_val(_send(_sprite_name(), 'sensing_mousex', {}))

def mouse_y():
    return _parse_val(_send(_sprite_name(), 'sensing_mousey', {}))

def get_loudness():
    return _parse_val(_send(_sprite_name(), 'sensing_loudness', {}))

def get_timer():
    return _parse_val(_send(_sprite_name(), 'sensing_timer', {}))

def reset_timer():
    _send(_sprite_name(), 'sensing_resettimer', {})

def get_sprite_current(prop):
    return _parse_val(_send(_sprite_name(), 'sensing_of', {'PROPERTY': prop}))

def days_since_2000():
    return _parse_val(_send(_sprite_name(), 'sensing_dayssince2000', {}))

def get_username():
    return _parse_val(_send(_sprite_name(), 'sensing_username', {}))

# Events
def broadcast_message(message):
    _send(_sprite_name(), 'event_broadcast', {
        'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
    })

def broadcast_and_wait(message):
    _send(_sprite_name(), 'event_broadcastandwait', {
        'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
    })

# Pen (standalone)
def pen_down():
    _send(_sprite_name(), 'pen_penDown', {})

def pen_up():
    _send(_sprite_name(), 'pen_penUp', {})

def pen_clear():
    _send(_sprite_name(), 'pen_clear', {})

def pen_stamp():
    _send(_sprite_name(), 'pen_stamp', {})

def pen_set_color(r, g, b, a=255):
    _send(_sprite_name(), 'pen_setPenColorToColor', {'COLOR': [r, g, b, a]})

def pen_change_color(param, change):
    _send(_sprite_name(), 'pen_changePenColorParamBy', {'COLOR_PARAM': param, 'VALUE': change})

def pen_set_size(size):
    _send(_sprite_name(), 'pen_setPenSizeTo', {'SIZE': size})

def pen_change_size(change):
    _send(_sprite_name(), 'pen_changePenSizeBy', {'SIZE': change})


# ── input() override ─────────────────────────────────────

def input(prompt=''):
    """Ask the user a question using Scratch's ask block."""
    if prompt:
        return ask_question(str(prompt))
    return get_answer()
