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
        resp = str(xhr.responseText)
        _check_incoming_broadcasts(resp)
        return resp
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


# ── Broadcast registry ────────────────────────────────────

_broadcast_handlers = {}   # {"message_name": [handler_fn, ...]}
_dispatching = False       # reentrancy guard
_broadcast_queue = []      # queued broadcasts arriving during dispatch

def when_broadcast(message):
    """Decorator to register a function as a broadcast handler.

    @when_broadcast("start_game")
    def on_start():
        print("Game started!")
    """
    msg = message.lower()
    def decorator(fn):
        _broadcast_handlers.setdefault(msg, []).append(fn)
        return fn
    return decorator

def _dispatch_broadcast(message):
    """Dispatch a broadcast to all registered Python handlers."""
    global _dispatching
    if _dispatching:
        _broadcast_queue.append(message)
        return
    _dispatching = True
    try:
        for handler in _broadcast_handlers.get(message.lower(), []):
            handler()
        # Process any broadcasts that arrived during handler execution
        while _broadcast_queue:
            queued = _broadcast_queue.pop(0)
            for handler in _broadcast_handlers.get(queued.lower(), []):
                handler()
    finally:
        _dispatching = False
        _broadcast_queue.clear()

def _clear_broadcast_handlers():
    """Clear all registered broadcast handlers. Called between executions."""
    _broadcast_handlers.clear()
    _broadcast_queue.clear()

def _check_incoming_broadcasts(resp):
    """Check response for Scratch broadcasts and dispatch to Python handlers."""
    if not resp:
        return
    try:
        data = json.loads(resp)
        for msg in data.get('_broadcasts', []):
            _dispatch_broadcast(msg)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass


def listen():
    """Keep Python running and listening for Scratch broadcasts.

    Call this at the end of your code after registering @when_broadcast handlers.
    Press the stop button to end.

    Example::

        @when_broadcast("start_game")
        def begin():
            sprite.say("Game started!")

        listen()  # keeps running until stopped
    """
    import time
    try:
        while True:
            _send(_sprite_name(), '_poll', {})
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass  # stop button pressed — exit cleanly


# ── Sprite class ────────────────────────────────────────────

class Sprite:
    """A Scratch sprite you can control with Python code.

    Create a sprite with ``penguin = Sprite()`` or ``penguin = Sprite('Penguin')``.
    Then call methods like ``penguin.move_steps(10)`` or ``penguin.say('Hello!')``.
    """

    def __init__(self, name=None):
        """Create or connect to a sprite. If name is omitted, uses the current sprite."""
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
        """Move the sprite forward by the given number of steps."""
        return self._do('motion_movesteps', {'STEPS': steps})

    def turn_right(self, degrees):
        """Turn the sprite clockwise by the given degrees."""
        return self._do('motion_turnright', {'DEGREES': degrees})

    def turn_left(self, degrees):
        """Turn the sprite counter-clockwise by the given degrees."""
        return self._do('motion_turnleft', {'DEGREES': degrees})

    def goto_xy(self, x, y):
        """Move the sprite to position (x, y)."""
        return self._do('motion_gotoxy', {'X': x, 'Y': y})

    def goto_position(self, target):
        """Move the sprite to another sprite or 'random position' or 'mouse-pointer'."""
        return self._do('motion_goto', {'TO': target})

    def set_x(self, x):
        """Set the sprite's x position."""
        return self._do('motion_setx', {'X': x})

    def set_y(self, y):
        """Set the sprite's y position."""
        return self._do('motion_sety', {'Y': y})

    def change_x(self, dx):
        """Change the sprite's x position by dx."""
        return self._do('motion_changexby', {'DX': dx})

    def change_y(self, dy):
        """Change the sprite's y position by dy."""
        return self._do('motion_changeyby', {'DY': dy})

    def set_direction(self, deg):
        """Point the sprite in the given direction (0=up, 90=right, 180=down, -90=left)."""
        return self._do('motion_pointindirection', {'DIRECTION': deg})

    def bounce_if_on_edge(self):
        """If the sprite is touching an edge, bounce off it."""
        return self._do('motion_ifonedgebounce')

    def point_towards(self, target):
        """Point the sprite towards another sprite or 'mouse-pointer'."""
        return self._do('motion_pointtowards', {'TOWARDS': target})

    def set_rotation_style(self, style):
        """Set rotation style: 'left-right', 'don't rotate', or 'all around'."""
        return self._do('motion_setrotationstyle', {'STYLE': style})

    def get_x(self):
        """Return the sprite's current x position."""
        return self._query('motion_xposition')

    def get_y(self):
        """Return the sprite's current y position."""
        return self._query('motion_yposition')

    def get_direction(self):
        """Return the sprite's current direction in degrees."""
        return self._query('motion_direction')

    # ── Looks ───────────────────────────────────────────

    def say(self, message, secs=None):
        """Make the sprite show a speech bubble. If secs is given, it disappears after that time."""
        if secs is not None:
            return self._do('looks_sayforsecs', {'MESSAGE': str(message), 'SECS': secs})
        return self._do('looks_say', {'MESSAGE': str(message)})

    def think(self, message, secs=None):
        """Make the sprite show a thought bubble. If secs is given, it disappears after that time."""
        if secs is not None:
            return self._do('looks_thinkforsecs', {'MESSAGE': str(message), 'SECS': secs})
        return self._do('looks_think', {'MESSAGE': str(message)})

    def switch_costume(self, costume):
        """Switch the sprite's costume by name or number."""
        return self._do('looks_switchcostumeto', {'COSTUME': costume})

    def next_costume(self):
        """Switch to the next costume in the list."""
        return self._do('looks_nextcostume')

    def change_size(self, change):
        """Change the sprite's size by the given amount (percentage)."""
        return self._do('looks_changesizeby', {'CHANGE': change})

    def set_size(self, size):
        """Set the sprite's size to the given percentage."""
        return self._do('looks_setsizeto', {'SIZE': size})

    def show(self):
        """Make the sprite visible."""
        return self._do('looks_show')

    def hide(self):
        """Make the sprite invisible."""
        return self._do('looks_hide')

    def change_effect(self, effect, change):
        """Change a graphic effect. Effects: 'color', 'fisheye', 'whirl', 'pixelate', 'mosaic', 'brightness', 'ghost'."""
        return self._do('looks_changeeffectby', {'EFFECT': effect, 'CHANGE': change})

    def set_effect(self, effect, value):
        """Set a graphic effect to a value. Effects: 'color', 'fisheye', 'whirl', 'pixelate', 'mosaic', 'brightness', 'ghost'."""
        return self._do('looks_seteffectto', {'EFFECT': effect, 'VALUE': value})

    def clear_effects(self):
        """Remove all graphic effects from the sprite."""
        return self._do('looks_cleargraphiceffects')

    def go_to_layer(self, layer):
        """Move sprite to 'front' or 'back' layer."""
        return self._do('looks_gotofrontback', {'FRONT_BACK': layer})

    def change_layer(self, direction, amount):
        """Change layer position. direction: 'forward' or 'backward'."""
        return self._do('looks_goforwardbackwardlayers', {'FORWARD_BACKWARD': direction, 'NUM': amount})

    def get_costume(self):
        """Return the name of the current costume."""
        return self._query('looks_costumenumbername', {'NUMBER_NAME': 'name'})

    def get_size(self):
        """Return the sprite's current size as a percentage."""
        return self._query('looks_size')

    # ── Pen ─────────────────────────────────────────────

    def pen_down(self):
        """Start drawing a trail as the sprite moves."""
        return self._do('pen_penDown')

    def pen_up(self):
        """Stop drawing a trail."""
        return self._do('pen_penUp')

    def pen_clear(self):
        """Erase all pen marks from the stage."""
        return self._do('pen_clear')

    def pen_stamp(self):
        """Stamp the sprite's image onto the stage."""
        return self._do('pen_stamp')

    def pen_set_color(self, r, g, b, a=255):
        """Set the pen color using RGBA values (0-255)."""
        return self._do('pen_setPenColorToColor', {'COLOR': [r, g, b, a]})

    def pen_change_color(self, param, change):
        """Change a pen color parameter. param: 'color', 'saturation', 'brightness', 'transparency'."""
        return self._do('pen_changePenColorParamBy', {'COLOR_PARAM': param, 'VALUE': change})

    def pen_set_size(self, size):
        """Set the pen line thickness."""
        return self._do('pen_setPenSizeTo', {'SIZE': size})

    def pen_change_size(self, change):
        """Change the pen line thickness by the given amount."""
        return self._do('pen_changePenSizeBy', {'SIZE': change})

    # ── Sound ───────────────────────────────────────────

    def play_until_done(self, sound):
        """Play a sound and wait until it finishes."""
        return self._do('sound_playuntildone', {'SOUND_MENU': sound})

    def play_sound(self, sound):
        """Start playing a sound without waiting for it to finish."""
        return self._do('sound_play', {'SOUND_MENU': sound})

    def stop_all_sounds(self):
        """Stop all sounds that are currently playing."""
        return self._do('sound_stopallsounds')

    def set_volume(self, vol):
        """Set the volume to a percentage (0-100)."""
        return self._do('sound_setvolumeto', {'VOLUME': vol})

    def change_sound_effect(self, effect, change):
        """Change a sound effect. effect: 'pitch' or 'pan left/right'."""
        return self._do('sound_changeeffectby', {'EFFECT': effect, 'VALUE': change})

    def set_sound_effect(self, effect, value):
        """Set a sound effect to a value. effect: 'pitch' or 'pan left/right'."""
        return self._do('sound_seteffectto', {'EFFECT': effect, 'VALUE': value})

    def clear_sound_effects(self):
        """Reset all sound effects to normal."""
        return self._do('sound_cleareffects')

    def change_volume(self, change):
        """Change the volume by the given amount."""
        return self._do('sound_changevolumeby', {'VOLUME': change})

    def get_volume(self):
        """Return the current volume (0-100)."""
        return self._query('sound_volume')

    # ── Sensing ─────────────────────────────────────────

    def is_touching(self, target_name):
        """Check if the sprite is touching another sprite, 'mouse-pointer', or 'edge'."""
        if isinstance(target_name, Sprite):
            target_name = target_name.name
        return self._query('sensing_touchingobject', {'TOUCHINGOBJECTMENU': target_name})

    def is_touching_color(self, r, g, b, a=255):
        """Check if the sprite is touching a specific color (RGBA 0-255)."""
        return self._query('sensing_touchingcolor', {'COLOR': [r, g, b, a]})

    def distance_to(self, target_name):
        """Return the distance to another sprite or 'mouse-pointer'."""
        if isinstance(target_name, Sprite):
            target_name = target_name.name
        return self._query('sensing_distanceto', {'DISTANCETOMENU': target_name})

    def is_key_pressed(self, key):
        """Check if a keyboard key is pressed. Example: 'space', 'a', 'left arrow'."""
        return self._query('sensing_keypressed', {'KEY_OPTION': key})

    def get_timer(self):
        """Return the number of seconds since the timer was last reset."""
        return self._query('sensing_timer')

    def reset_timer(self):
        """Reset the timer to 0."""
        return self._do('sensing_resettimer')

    # ── Events ──────────────────────────────────────────

    def broadcast(self, message):
        """Send a broadcast message to all sprites and Python handlers."""
        self._do('event_broadcast', {
            'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
        })
        _dispatch_broadcast(message)

    def broadcast_and_wait(self, message):
        """Send a broadcast message and wait until all listeners finish."""
        self._do('event_broadcastandwait', {
            'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
        })
        _dispatch_broadcast(message)

    # ── Clone ───────────────────────────────────────────

    def create_clone(self):
        """Create a clone of this sprite."""
        return self._do('control_create_clone_of', {'CLONE_OPTION': '_myself_'})

    # ── Display ─────────────────────────────────────────

    @property
    def position(self):
        return (round(self.x, 1), round(self.y, 1))

    def __repr__(self):
        return f"{self.name}(x={self.x:.0f}, y={self.y:.0f}, dir={self.direction:.0f}°)"


# ── Stage class ────────────────────────────────────────────

class Stage:
    """Controls the stage — backdrops, sound, sensing, events, pen clear.

    Create with ``stage = Stage()``.
    """

    def __init__(self):
        """Connect to the stage."""
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
        """Switch the stage backdrop by name or number."""
        return self._do('looks_switchbackdropto', {'BACKDROP': backdrop})

    def next_backdrop(self):
        """Switch to the next backdrop."""
        return self._do('looks_nextbackdrop')

    def get_backdrop(self):
        """Return the name of the current backdrop."""
        return self._query('looks_backdropnumbername', {'NUMBER_NAME': 'name'})

    def change_effect(self, effect, change):
        """Change a graphic effect on the stage."""
        return self._do('looks_changeeffectby', {'EFFECT': effect, 'CHANGE': change})

    def set_effect(self, effect, value):
        """Set a graphic effect on the stage."""
        return self._do('looks_seteffectto', {'EFFECT': effect, 'VALUE': value})

    def clear_effects(self):
        """Remove all graphic effects from the stage."""
        return self._do('looks_cleargraphiceffects')

    # ── Pen ──────────────────────────────────────────────

    def pen_clear(self):
        """Erase all pen marks from the stage."""
        return self._do('pen_clear')

    # ── Sound ────────────────────────────────────────────

    def play_sound(self, sound):
        """Start playing a sound on the stage."""
        return self._do('sound_play', {'SOUND_MENU': sound})

    def stop_all_sounds(self):
        """Stop all sounds."""
        return self._do('sound_stopallsounds')

    def set_volume(self, vol):
        """Set the stage volume (0-100)."""
        return self._do('sound_setvolumeto', {'VOLUME': vol})

    def change_volume(self, change):
        """Change the stage volume by the given amount."""
        return self._do('sound_changevolumeby', {'VOLUME': change})

    def get_volume(self):
        """Return the current stage volume."""
        return self._query('sound_volume')

    # ── Sensing ──────────────────────────────────────────

    def is_key_pressed(self, key):
        """Check if a keyboard key is pressed."""
        return self._query('sensing_keypressed', {'KEY_OPTION': key})

    def get_timer(self):
        """Return the number of seconds since the timer was last reset."""
        return self._query('sensing_timer')

    def reset_timer(self):
        """Reset the timer to 0."""
        return self._do('sensing_resettimer')

    # ── Events ───────────────────────────────────────────

    def broadcast(self, message):
        """Send a broadcast message to all sprites and Python handlers."""
        self._do('event_broadcast', {
            'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
        })
        _dispatch_broadcast(message)

    def __repr__(self):
        return f"Stage()"


# ── Pen class (standalone helper) ─────────────────────────

class Pen:
    """Convenience class for pen operations on a sprite.

    Create with ``pen = Pen(sprite)`` or ``pen = Pen()`` for the current sprite.
    """

    def __init__(self, sprite=None):
        """Create a Pen for the given sprite, or the current sprite if omitted."""
        self.sprite_name = sprite.name if sprite else __SPRITE_NAME__

    def down(self):
        """Start drawing a trail."""
        _send(self.sprite_name, 'pen_penDown', {})

    def up(self):
        """Stop drawing a trail."""
        _send(self.sprite_name, 'pen_penUp', {})

    def clear(self):
        """Erase all pen marks."""
        _send(self.sprite_name, 'pen_clear', {})

    def stamp(self):
        """Stamp the sprite's image onto the stage."""
        _send(self.sprite_name, 'pen_stamp', {})

    def set_color(self, r, g, b, a=255):
        """Set pen color using RGBA values (0-255)."""
        _send(self.sprite_name, 'pen_setPenColorToColor', {'COLOR': [r, g, b, a]})

    def set_size(self, size):
        """Set the pen line thickness."""
        _send(self.sprite_name, 'pen_setPenSizeTo', {'SIZE': size})

    def change_size(self, change):
        """Change the pen line thickness by the given amount."""
        _send(self.sprite_name, 'pen_changePenSizeBy', {'SIZE': change})


# ── Whizz (RC Car) class ─────────────────────────────────

class Whizz:
    """Controls the Whizz RC Car extension.

    Create with ``car = Whizz()`` or ``car = Whizz('SpriteName')``.
    """

    def __init__(self, sprite_name=None):
        """Create a Whizz controller for the given sprite."""
        self.sprite_name = sprite_name or __SPRITE_NAME__

    def move_forward(self, steps=1):
        """Move the car forward by the given number of steps."""
        _send(self.sprite_name, 'rcCar_moveForward', {'STEPS': steps})

    def move_backward(self, steps=1):
        """Move the car backward by the given number of steps."""
        _send(self.sprite_name, 'rcCar_moveBackward', {'STEPS': steps})

    def turn_left(self, degrees=90):
        """Turn the car left by the given degrees."""
        _send(self.sprite_name, 'rcCar_turnLeft', {'DEGREES': degrees})

    def turn_right(self, degrees=90):
        """Turn the car right by the given degrees."""
        _send(self.sprite_name, 'rcCar_turnRight', {'DEGREES': degrees})

    def toggle_lights(self):
        """Toggle the car lights on or off."""
        _send(self.sprite_name, 'rcCar_toggleLights', {})

    def toggle_turbo(self):
        """Toggle turbo mode on or off."""
        _send(self.sprite_name, 'rcCar_toggleTurboMode', {})


# ── SeaQuest class ────────────────────────────────────────

class SeaQuest:
    """Controls the SeaQuest extension.

    Create with ``sub = SeaQuest()`` or ``sub = SeaQuest('SpriteName')``.
    """

    def __init__(self, sprite_name=None):
        """Create a SeaQuest controller for the given sprite."""
        self.sprite_name = sprite_name or __SPRITE_NAME__

    def move_north(self, steps=1):
        """Move north (up) by the given number of steps."""
        _send(self.sprite_name, 'seaQuest_moveNorth', {'STEPS': steps})

    def move_south(self, steps=1):
        """Move south (down) by the given number of steps."""
        _send(self.sprite_name, 'seaQuest_moveSouth', {'STEPS': steps})

    def move_east(self, steps=1):
        """Move east (right) by the given number of steps."""
        _send(self.sprite_name, 'seaQuest_moveEast', {'STEPS': steps})

    def move_west(self, steps=1):
        """Move west (left) by the given number of steps."""
        _send(self.sprite_name, 'seaQuest_moveWest', {'STEPS': steps})


# ── Standalone convenience functions ──────────────────────
# These operate on the sprite identified by __SPRITE_NAME__

def _sprite_name():
    return __SPRITE_NAME__

# Motion
def move_steps(steps):
    """Move the sprite forward by the given number of steps."""
    _send(_sprite_name(), 'motion_movesteps', {'STEPS': steps})

def turn_right(degrees):
    """Turn the sprite clockwise by the given degrees."""
    _send(_sprite_name(), 'motion_turnright', {'DEGREES': degrees})

def turn_left(degrees):
    """Turn the sprite counter-clockwise by the given degrees."""
    _send(_sprite_name(), 'motion_turnleft', {'DEGREES': degrees})

def goto_position(target):
    """Move the sprite to another sprite or 'random position' or 'mouse-pointer'."""
    _send(_sprite_name(), 'motion_goto', {'TO': target})

def goto_xy(x, y):
    """Move the sprite to position (x, y)."""
    _send(_sprite_name(), 'motion_gotoxy', {'X': x, 'Y': y})

def get_x():
    """Return the sprite's current x position."""
    return _parse_val(_send(_sprite_name(), 'motion_xposition', {}))

def get_y():
    """Return the sprite's current y position."""
    return _parse_val(_send(_sprite_name(), 'motion_yposition', {}))

def get_direction():
    """Return the sprite's current direction in degrees."""
    return _parse_val(_send(_sprite_name(), 'motion_direction', {}))

def set_direction(deg):
    """Point the sprite in the given direction."""
    _send(_sprite_name(), 'motion_pointindirection', {'DIRECTION': deg})

def point_towards(target):
    """Point the sprite towards another sprite or 'mouse-pointer'."""
    _send(_sprite_name(), 'motion_pointtowards', {'TOWARDS': target})

def change_x(dx):
    """Change the sprite's x position by dx."""
    _send(_sprite_name(), 'motion_changexby', {'DX': dx})

def change_y(dy):
    """Change the sprite's y position by dy."""
    _send(_sprite_name(), 'motion_changeyby', {'DY': dy})

def set_x(x):
    """Set the sprite's x position."""
    _send(_sprite_name(), 'motion_setx', {'X': x})

def set_y(y):
    """Set the sprite's y position."""
    _send(_sprite_name(), 'motion_sety', {'Y': y})

def bounce_if_on_edge():
    """If the sprite is touching an edge, bounce off it."""
    _send(_sprite_name(), 'motion_ifonedgebounce', {})

def set_rotation_style(style):
    """Set rotation style: 'left-right', 'don't rotate', or 'all around'."""
    _send(_sprite_name(), 'motion_setrotationstyle', {'STYLE': style})

# Looks
def sprite_says(message):
    """Make the sprite show a speech bubble with the message."""
    _send(_sprite_name(), 'looks_say', {'MESSAGE': str(message)})

def sprite_think(message):
    """Make the sprite show a thought bubble with the message."""
    _send(_sprite_name(), 'looks_think', {'MESSAGE': str(message)})

def switch_costume(costume):
    """Switch the sprite's costume by name or number."""
    _send(_sprite_name(), 'looks_switchcostumeto', {'COSTUME': costume})

def next_costume():
    """Switch to the next costume in the list."""
    _send(_sprite_name(), 'looks_nextcostume', {})

def switch_backdrop(backdrop):
    """Switch the stage backdrop by name or number."""
    _send(_sprite_name(), 'looks_switchbackdropto', {'BACKDROP': backdrop})

def next_backdrop():
    """Switch to the next backdrop."""
    _send(_sprite_name(), 'looks_nextbackdrop', {})

def change_size(change):
    """Change the sprite's size by the given amount (percentage)."""
    _send(_sprite_name(), 'looks_changesizeby', {'CHANGE': change})

def set_size(size):
    """Set the sprite's size to the given percentage."""
    _send(_sprite_name(), 'looks_setsizeto', {'SIZE': size})

def change_effect(effect, change):
    """Change a graphic effect. Effects: 'color', 'fisheye', 'whirl', 'pixelate', 'mosaic', 'brightness', 'ghost'."""
    _send(_sprite_name(), 'looks_changeeffectby', {'EFFECT': effect, 'CHANGE': change})

def set_effect(effect, value):
    """Set a graphic effect to a value. Effects: 'color', 'fisheye', 'whirl', 'pixelate', 'mosaic', 'brightness', 'ghost'."""
    _send(_sprite_name(), 'looks_seteffectto', {'EFFECT': effect, 'VALUE': value})

def clear_effects():
    """Remove all graphic effects from the sprite."""
    _send(_sprite_name(), 'looks_cleargraphiceffects', {})

def show_sprite():
    """Make the sprite visible."""
    _send(_sprite_name(), 'looks_show', {})

def hide_sprite():
    """Make the sprite invisible."""
    _send(_sprite_name(), 'looks_hide', {})

def go_to_layer(layer):
    """Move sprite to 'front' or 'back' layer."""
    _send(_sprite_name(), 'looks_gotofrontback', {'FRONT_BACK': layer})

def change_layer(direction, amount):
    """Change layer position. direction: 'forward' or 'backward'."""
    _send(_sprite_name(), 'looks_goforwardbackwardlayers', {'FORWARD_BACKWARD': direction, 'NUM': amount})

def get_costume():
    """Return the name of the current costume."""
    return _parse_val(_send(_sprite_name(), 'looks_costumenumbername', {'NUMBER_NAME': 'name'}))

def get_backdrop():
    """Return the name of the current backdrop."""
    return _parse_val(_send(_sprite_name(), 'looks_backdropnumbername', {'NUMBER_NAME': 'name'}))

def get_sprite_size():
    """Return the sprite's current size as a percentage."""
    return _parse_val(_send(_sprite_name(), 'looks_size', {}))

# Sound
def play_until_done(sound):
    """Play a sound and wait until it finishes."""
    _send(_sprite_name(), 'sound_playuntildone', {'SOUND_MENU': sound})

def play_sound(sound):
    """Start playing a sound without waiting for it to finish."""
    _send(_sprite_name(), 'sound_play', {'SOUND_MENU': sound})

def stop_all_sounds():
    """Stop all sounds that are currently playing."""
    _send(_sprite_name(), 'sound_stopallsounds', {})

def change_sound_effect(effect, change):
    """Change a sound effect. effect: 'pitch' or 'pan left/right'."""
    _send(_sprite_name(), 'sound_changeeffectby', {'EFFECT': effect, 'VALUE': change})

def set_sound_effect(effect, value):
    """Set a sound effect to a value. effect: 'pitch' or 'pan left/right'."""
    _send(_sprite_name(), 'sound_seteffectto', {'EFFECT': effect, 'VALUE': value})

def clear_sound_effects():
    """Reset all sound effects to normal."""
    _send(_sprite_name(), 'sound_cleareffects', {})

def change_volume(change):
    """Change the volume by the given amount."""
    _send(_sprite_name(), 'sound_changevolumeby', {'VOLUME': change})

def set_volume_to(vol):
    """Set the volume to a percentage (0-100)."""
    _send(_sprite_name(), 'sound_setvolumeto', {'VOLUME': vol})

def get_volume():
    """Return the current volume (0-100)."""
    return _parse_val(_send(_sprite_name(), 'sound_volume', {}))

# Control
def create_clone():
    """Create a clone of the current sprite."""
    _send(_sprite_name(), 'control_create_clone_of', {'CLONE_OPTION': '_myself_'})

# Sensing
def is_touching(target_name):
    """Check if the sprite is touching another sprite, 'mouse-pointer', or 'edge'."""
    return _parse_val(_send(_sprite_name(), 'sensing_touchingobject', {'TOUCHINGOBJECTMENU': target_name}))

def is_touching_color(r, g, b, a=255):
    """Check if the sprite is touching a specific color (RGBA 0-255)."""
    return _parse_val(_send(_sprite_name(), 'sensing_touchingcolor', {'COLOR': [r, g, b, a]}))

def distance_to(target_name):
    """Return the distance to another sprite or 'mouse-pointer'."""
    return _parse_val(_send(_sprite_name(), 'sensing_distanceto', {'DISTANCETOMENU': target_name}))

def ask_question(question):
    """Ask the user a question and wait for their answer."""
    return _parse_val(_send(_sprite_name(), 'sensing_askandwait', {'QUESTION': question}))

def get_answer():
    """Return the user's last answer."""
    return _parse_val(_send(_sprite_name(), 'sensing_answer', {}))

def is_key_pressed(key):
    """Check if a keyboard key is pressed. Example: 'space', 'a', 'left arrow'."""
    return _parse_val(_send(_sprite_name(), 'sensing_keypressed', {'KEY_OPTION': key}))

def mouse_x():
    """Return the mouse pointer's x position."""
    return _parse_val(_send(_sprite_name(), 'sensing_mousex', {}))

def mouse_y():
    """Return the mouse pointer's y position."""
    return _parse_val(_send(_sprite_name(), 'sensing_mousey', {}))

def get_loudness():
    """Return the microphone loudness (0-100)."""
    return _parse_val(_send(_sprite_name(), 'sensing_loudness', {}))

def get_timer():
    """Return the number of seconds since the timer was last reset."""
    return _parse_val(_send(_sprite_name(), 'sensing_timer', {}))

def reset_timer():
    """Reset the timer to 0."""
    _send(_sprite_name(), 'sensing_resettimer', {})

def get_sprite_current(prop):
    """Get a property of the current sprite (e.g. 'x position', 'costume name')."""
    return _parse_val(_send(_sprite_name(), 'sensing_of', {'PROPERTY': prop}))

def days_since_2000():
    """Return the number of days since January 1, 2000."""
    return _parse_val(_send(_sprite_name(), 'sensing_dayssince2000', {}))

def get_username():
    """Return the current user's username."""
    return _parse_val(_send(_sprite_name(), 'sensing_username', {}))

# Events
def broadcast_message(message):
    """Send a broadcast message to all sprites and Python handlers."""
    _send(_sprite_name(), 'event_broadcast', {
        'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
    })
    _dispatch_broadcast(message)

def broadcast(message):
    """Send a broadcast message to all sprites and Python handlers."""
    broadcast_message(message)

def broadcast_and_wait(message):
    """Send a broadcast message and wait until all listeners finish."""
    _send(_sprite_name(), 'event_broadcastandwait', {
        'BROADCAST_INPUT': {'BROADCAST_OPTION': {'id': message, 'name': message}}
    })
    _dispatch_broadcast(message)

# Pen (standalone)
def pen_down():
    """Start drawing a trail as the sprite moves."""
    _send(_sprite_name(), 'pen_penDown', {})

def pen_up():
    """Stop drawing a trail."""
    _send(_sprite_name(), 'pen_penUp', {})

def pen_clear():
    """Erase all pen marks from the stage."""
    _send(_sprite_name(), 'pen_clear', {})

def pen_stamp():
    """Stamp the sprite's image onto the stage."""
    _send(_sprite_name(), 'pen_stamp', {})

def pen_set_color(r, g, b, a=255):
    """Set the pen color using RGBA values (0-255)."""
    _send(_sprite_name(), 'pen_setPenColorToColor', {'COLOR': [r, g, b, a]})

def pen_change_color(param, change):
    """Change a pen color parameter. param: 'color', 'saturation', 'brightness', 'transparency'."""
    _send(_sprite_name(), 'pen_changePenColorParamBy', {'COLOR_PARAM': param, 'VALUE': change})

def pen_set_size(size):
    """Set the pen line thickness."""
    _send(_sprite_name(), 'pen_setPenSizeTo', {'SIZE': size})

def pen_change_size(change):
    """Change the pen line thickness by the given amount."""
    _send(_sprite_name(), 'pen_changePenSizeBy', {'SIZE': change})


# ── input() override ─────────────────────────────────────

def input(prompt=''):
    """Ask the user a question using Scratch's ask block."""
    if prompt:
        return ask_question(str(prompt))
    return get_answer()
