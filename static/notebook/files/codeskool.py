"""CodeSkool — Scratch-style Python sprites.

Uses synchronous XMLHttpRequest through the service worker to send
commands to scratch-vm via the parent page. No ``await`` needed.

Methods send scratch-vm opcodes directly so the bridge can use
getOpcodeFunction() to execute them — same engine as block execution.

Works in both notebook mode (JupyterLite) and editor mode (Pyodide worker).
"""

import json
import time
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

# Per-hat-dispatch target pin. Set by _run_hat_handlers when the VM emits
# HAT_STARTED with a specific targetId (e.g. control_start_as_clone fires
# once per clone). When non-None, _send threads it to the main thread so
# sprite API calls route to the exact target, not the first name-matching
# one. Clones share sprite.name with their original — without this,
# `self.change_x(50)` inside a when_start_as_clone body would mutate the
# original sprite.
__TARGET_ID__ = None


def _make_cmd(sprite_name, action, params):
    global _cmd_id
    _cmd_id += 1
    return json.dumps({
        "_codeskool": True,
        "id": f"cs-{_cmd_id}",
        "sprite": sprite_name,
        "action": action,
        "params": params,
        "targetId": __TARGET_ID__,
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
        _check_incoming_hats(resp)
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
    global _dispatching, __TARGET_ID__
    if _dispatching:
        _broadcast_queue.append(message)
        return
    _dispatching = True
    # Broadcasts don't carry a specific target — they fire across every sprite
    # that registered the message. If a surrounding hat dispatcher has pinned
    # __TARGET_ID__ (e.g. when_start_as_clone is running) the broadcast handlers
    # would inherit that pin and route _send calls to the wrong sprite. Reset
    # here so the handlers fall back to name-based routing, restore afterwards
    # so the outer hat still resumes with its pin intact.
    prev_target_id = __TARGET_ID__
    __TARGET_ID__ = None
    try:
        for handler in _broadcast_handlers.get(message.lower(), []):
            handler()
        # Process any broadcasts that arrived during handler execution
        while _broadcast_queue:
            queued = _broadcast_queue.pop(0)
            for handler in _broadcast_handlers.get(queued.lower(), []):
                handler()
    finally:
        __TARGET_ID__ = prev_target_id
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


# ── Hat event registry ────────────────────────────────────
# Generic mechanism for every hat block that isn't a broadcast. The VM emits
# ``HAT_STARTED`` for every startHats() call; the main thread relays those
# into the worker, which piggy-backs them on the next XHR response as
# ``_hats``. One dispatcher handles every hat; the public decorators
# (``when_flag_clicked``, ``when_key_pressed``, ...) are thin wrappers.

_hat_handlers = {}            # {(opcode, field_name_or_None, field_value_or_None): [fns...]}
_hat_dispatching = False      # reentrancy guard (independent of _dispatching)
_hat_queue = []               # queued hats arriving during dispatch


def _normalise_hat_value(value):
    """Fields arrive uppercased from startHats; lowercase strings for matching."""
    return value.lower() if isinstance(value, str) else value


def _when_hat(opcode, field=None, value=None):
    """Generic hat-registration decorator. Prefer the public wrappers below."""
    key = (opcode, field, _normalise_hat_value(value))
    def decorator(fn):
        _hat_handlers.setdefault(key, []).append(fn)
        return fn
    return decorator


def when_flag_clicked(fn):
    """Decorator: run when the green flag is clicked."""
    return _when_hat('event_whenflagclicked')(fn)


def when_key_pressed(key):
    """Decorator: run when a key is pressed. Example: ``@when_key_pressed("space")``."""
    return _when_hat('event_whenkeypressed', 'KEY_OPTION', key)


def when_sprite_clicked(fn):
    """Decorator: run when this sprite is clicked."""
    return _when_hat('event_whenthisspriteclicked')(fn)


def when_stage_clicked(fn):
    """Decorator: run when the stage is clicked."""
    return _when_hat('event_whenstageclicked')(fn)


def when_backdrop_switches_to(backdrop):
    """Decorator: run when the stage switches to a specific backdrop."""
    return _when_hat('event_whenbackdropswitchesto', 'BACKDROP', backdrop)


def when_greater_than(property_name, threshold=0):
    """Decorator: run when loudness or timer exceeds a threshold.

    ``property_name`` is ``"LOUDNESS"`` or ``"TIMER"``. The threshold comes from
    the block and is preserved for documentation only — matching is on the
    property name, exactly like the block behaves.
    """
    del threshold  # accepted for symmetry with the block; VM handles the predicate
    return _when_hat('event_whengreaterthan', 'WHENGREATERTHANMENU', property_name)


def when_start_as_clone(fn):
    """Decorator: run on each clone when it is created."""
    return _when_hat('control_start_as_clone')(fn)


def _hat_keys_for(opcode, fields):
    """Yield every (opcode, field, value) key that a triggered hat matches.

    A single VM ``HAT_STARTED`` event may match handlers registered with a
    specific field (``@when_key_pressed("space")``) AND handlers that ignore
    fields entirely — emit both keys so nothing is missed.
    """
    yield (opcode, None, None)
    if not fields:
        return
    for field_name, field_value in fields.items():
        yield (opcode, field_name, _normalise_hat_value(field_value))


def _dispatch_hat(payload):
    """Dispatch a single hat event to all matching registered handlers."""
    global _hat_dispatching
    if _hat_dispatching:
        _hat_queue.append(payload)
        return
    _hat_dispatching = True
    try:
        _run_hat_handlers(payload)
        while _hat_queue:
            _run_hat_handlers(_hat_queue.pop(0))
    finally:
        _hat_dispatching = False
        _hat_queue.clear()


def _run_hat_handlers(payload):
    global __TARGET_ID__
    opcode = payload.get('opcode')
    fields = payload.get('fields') or {}
    target_id = payload.get('targetId')
    # Pin the current target for the duration of this hat's handler stack
    # so nested sprite API calls route to the exact VM target instead of
    # collapsing to the first name match. Matters most for clones.
    prev = __TARGET_ID__
    if target_id:
        __TARGET_ID__ = target_id
    try:
        seen = set()
        for key in _hat_keys_for(opcode, fields):
            if key in seen:
                continue
            seen.add(key)
            for handler in _hat_handlers.get(key, []):
                handler()
    finally:
        __TARGET_ID__ = prev


def _clear_hat_handlers():
    """Clear all registered hat handlers. Called between executions."""
    _hat_handlers.clear()
    _hat_queue.clear()


def _check_incoming_hats(resp):
    """Check response for Scratch hat events and dispatch to Python handlers."""
    if not resp:
        return
    try:
        data = json.loads(resp)
        for payload in data.get('_hats', []):
            _dispatch_hat(payload)
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


# ── OceanQuest class ────────────────────────────────────────

class OceanQuest:
    """Controls the OceanQuest extension.

    Create with ``sub = OceanQuest()`` or ``sub = OceanQuest('SpriteName')``.
    """

    def __init__(self, sprite_name=None):
        """Create a OceanQuest controller for the given sprite."""
        self.sprite_name = sprite_name or __SPRITE_NAME__

    def move_north(self, steps=1):
        """Move north (up) by the given number of steps."""
        _send(self.sprite_name, 'oceanQuest_moveNorth', {'STEPS': steps})

    def move_south(self, steps=1):
        """Move south (down) by the given number of steps."""
        _send(self.sprite_name, 'oceanQuest_moveSouth', {'STEPS': steps})

    def move_east(self, steps=1):
        """Move east (right) by the given number of steps."""
        _send(self.sprite_name, 'oceanQuest_moveEast', {'STEPS': steps})

    def move_west(self, steps=1):
        """Move west (left) by the given number of steps."""
        _send(self.sprite_name, 'oceanQuest_moveWest', {'STEPS': steps})


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
def say(message, secs=None):
    """Show a speech bubble with the message.

    Pass ``secs`` to automatically clear the bubble after that many seconds
    (mirrors the "say ... for ... seconds" block).
    """
    if secs is None:
        _send(_sprite_name(), 'looks_say', {'MESSAGE': str(message)})
    else:
        _send(_sprite_name(), 'looks_sayforsecs', {'MESSAGE': str(message), 'SECS': secs})

def think(message, secs=None):
    """Show a thought bubble with the message. Pass ``secs`` for the timed variant."""
    if secs is None:
        _send(_sprite_name(), 'looks_think', {'MESSAGE': str(message)})
    else:
        _send(_sprite_name(), 'looks_thinkforsecs', {'MESSAGE': str(message), 'SECS': secs})

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

def show():
    """Make the sprite visible."""
    _send(_sprite_name(), 'looks_show', {})

def hide():
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

def size():
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

def current(prop):
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


# ── Draw (module-level) ──────────────────────────────────
# Declarative shapes on a dedicated stage layer. Coords are top-left
# origin, y-down (matches Canvas2D / p5.js / every web tutorial), so a
# kid Googling "draw a rectangle in p5" gets a transferable answer.
# Colours accept any CSS string ("#00b0f0", "yellow", "rgb(0,128,255)").
# circle uses RADIUS (CodeGuppy convention), not diameter.

def fill(color):
    """Set the fill colour for subsequent shapes (CSS colour string)."""
    _send(_sprite_name(), 'draw_fill', {'COLOR': color})


def noFill():
    """Disable filling — subsequent shapes draw outlined only."""
    _send(_sprite_name(), 'draw_noFill', {})


def stroke(color):
    """Set the stroke (outline) colour for subsequent shapes."""
    _send(_sprite_name(), 'draw_stroke', {'COLOR': color})


def noStroke():
    """Disable stroking — subsequent shapes draw filled only."""
    _send(_sprite_name(), 'draw_noStroke', {})


def strokeWeight(w):
    """Set the stroke thickness in pixels."""
    _send(_sprite_name(), 'draw_strokeWeight', {'W': w})


def rect(x, y, w, h):
    """Draw a rectangle. (x, y) is the top-left corner."""
    _send(_sprite_name(), 'draw_rect', {'X': x, 'Y': y, 'W': w, 'H': h})


def square(x, y, s):
    """Draw a square at (x, y) with side length s."""
    _send(_sprite_name(), 'draw_square', {'X': x, 'Y': y, 'S': s})


def circle(x, y, r):
    """Draw a circle. Third argument is the RADIUS (CodeGuppy convention)."""
    _send(_sprite_name(), 'draw_circle', {'X': x, 'Y': y, 'R': r})


def line(x1, y1, x2, y2):
    """Draw a straight line between two points."""
    _send(_sprite_name(), 'draw_line', {'X1': x1, 'Y1': y1, 'X2': x2, 'Y2': y2})


def triangle(x1, y1, x2, y2, x3, y3):
    """Draw a triangle from three points."""
    _send(_sprite_name(), 'draw_triangle',
          {'X1': x1, 'Y1': y1, 'X2': x2, 'Y2': y2, 'X3': x3, 'Y3': y3})


def background(color):
    """Paint the whole Draw layer with a colour."""
    _send(_sprite_name(), 'draw_background', {'COLOR': color})


def clear():
    """Erase everything drawn on the Draw layer."""
    _send(_sprite_name(), 'draw_clear', {})


# Stage 2 — extra primitives + cap/join + free-form polygon builder.

def ellipse(x, y, w, h):
    """Draw an ellipse. (x, y) is the centre, (w, h) the bounding box."""
    _send(_sprite_name(), 'draw_ellipse', {'X': x, 'Y': y, 'W': w, 'H': h})


def point(x, y):
    """Draw a single dot — diameter equals the current strokeWeight."""
    _send(_sprite_name(), 'draw_point', {'X': x, 'Y': y})


def arc(x, y, r, start_deg, end_deg):
    """Draw a partial circle. Angles in degrees, clockwise from 3 o'clock."""
    _send(_sprite_name(), 'draw_arc',
          {'X': x, 'Y': y, 'R': r, 'START': start_deg, 'END': end_deg})


def quad(x1, y1, x2, y2, x3, y3, x4, y4):
    """Draw a quadrilateral from four points."""
    _send(_sprite_name(), 'draw_quad',
          {'X1': x1, 'Y1': y1, 'X2': x2, 'Y2': y2,
           'X3': x3, 'Y3': y3, 'X4': x4, 'Y4': y4})


def beginShape():
    """Start collecting vertices for a free-form polygon."""
    _send(_sprite_name(), 'draw_beginShape', {})


def vertex(x, y):
    """Add a vertex to the polygon currently being built."""
    _send(_sprite_name(), 'draw_vertex', {'X': x, 'Y': y})


def endShape():
    """Close and render the polygon built with beginShape / vertex."""
    _send(_sprite_name(), 'draw_endShape', {})


def strokeCap(cap):
    """Set the line-end style ('butt' | 'round' | 'square')."""
    _send(_sprite_name(), 'draw_strokeCap', {'CAP': cap})


def strokeJoin(join):
    """Set the line-corner style ('miter' | 'round' | 'bevel')."""
    _send(_sprite_name(), 'draw_strokeJoin', {'JOIN': join})


# Stage 2 — colour helpers. Pure Python — return CSS strings consumable
# by fill / stroke / background. No round-trip to the main thread.

def rgb(r, g, b):
    """Build a CSS rgb() colour string from 0-255 components."""
    def _c(v):
        return max(0, min(255, int(round(float(v)))))
    return f"rgb({_c(r)}, {_c(g)}, {_c(b)})"


def rgba(r, g, b, a):
    """Build a CSS rgba() colour string. a is 0.0-1.0."""
    def _c(v):
        return max(0, min(255, int(round(float(v)))))
    ac = max(0.0, min(1.0, float(a)))
    return f"rgba({_c(r)}, {_c(g)}, {_c(b)}, {ac})"


def hsl(h, s, l):
    """Build a CSS hsl() colour string. h is degrees, s/l are percent (0-100)."""
    return f"hsl({float(h)}, {float(s)}%, {float(l)}%)"


# Stage 3 — text.

def text(s, x, y):
    """Draw a string at (x, y) using the current fill / stroke / textSize / textFont state."""
    _send(_sprite_name(), 'draw_text', {'STR': str(s), 'X': x, 'Y': y})


def textSize(size):
    """Set the text size (font height) in pixels."""
    _send(_sprite_name(), 'draw_textSize', {'SIZE': size})


def textFont(font):
    """Set the text font family (any CSS font-family string)."""
    _send(_sprite_name(), 'draw_textFont', {'FONT': font})


def textAlign(h, v='top'):
    """Set horizontal ('left'|'center'|'right') and vertical ('top'|'middle'|'bottom') alignment."""
    _send(_sprite_name(), 'draw_textAlign', {'H': h, 'V': v})


def textWidth(s):
    """Return the rendered width of the string in pixels at the current text size + font."""
    return _parse_val(_send(_sprite_name(), 'draw_textWidth', {'STR': str(s)}))


# Stage 4 — transforms.

def push():
    """Save current transform + style state. Pair with pop()."""
    _send(_sprite_name(), 'draw_push', {})


def pop():
    """Restore the state saved by the most recent push()."""
    _send(_sprite_name(), 'draw_pop', {})


def translate(x, y):
    """Move the drawing origin by (x, y)."""
    _send(_sprite_name(), 'draw_translate', {'X': x, 'Y': y})


def rotate(a):
    """Rotate subsequent drawing (degrees by default; switch via angleMode())."""
    _send(_sprite_name(), 'draw_rotate', {'A': a})


def scale(sx, sy=None):
    """Scale subsequent drawing. If sy is omitted, scales uniformly."""
    if sy is None:
        sy = sx
    _send(_sprite_name(), 'draw_scale', {'SX': sx, 'SY': sy})


def resetMatrix():
    """Reset the transform matrix to identity."""
    _send(_sprite_name(), 'draw_resetMatrix', {})


def angleMode(mode):
    """Switch angle interpretation between 'DEGREES' (default) and 'RADIANS'."""
    _send(_sprite_name(), 'draw_angleMode', {'MODE': mode})


# True while any mouse button is currently held down. New capability —
# codeskool didn't expose sensing_mousedown before; mouse_x() and
# mouse_y() were already there.

def mouse_is_pressed():
    """True while any mouse button is currently held down."""
    return _parse_val(_send(_sprite_name(), 'sensing_mousedown', {})) is True


# Collision detection. Pure Python — no round-trip needed.

def collisionPointCircle(px, py, cx, cy, cr):
    dx, dy = px - cx, py - cy
    return (dx * dx + dy * dy) <= (cr * cr)


def collisionCircleCircle(c1x, c1y, c1r, c2x, c2y, c2r):
    dx, dy = c1x - c2x, c1y - c2y
    r = c1r + c2r
    return (dx * dx + dy * dy) <= (r * r)


def collisionPointRect(px, py, rx, ry, rw, rh):
    return rx <= px <= rx + rw and ry <= py <= ry + rh


def collisionRectRect(r1x, r1y, r1w, r1h, r2x, r2y, r2w, r2h):
    return not (r1x + r1w < r2x or r2x + r2w < r1x or
                r1y + r1h < r2y or r2y + r2h < r1y)


def collisionCircleRect(cx, cy, cr, rx, ry, rw, rh):
    tx = max(rx, min(cx, rx + rw))
    ty = max(ry, min(cy, ry + rh))
    dx, dy = cx - tx, cy - ty
    return (dx * dx + dy * dy) <= (cr * cr)


def collisionPointLine(px, py, x1, y1, x2, y2, tolerance=1):
    A, B, C, D = px - x1, py - y1, x2 - x1, y2 - y1
    dot = A * C + B * D
    len2 = C * C + D * D
    t = 0 if len2 == 0 else dot / len2
    t = max(0, min(1, t))
    proj_x = x1 + t * C
    proj_y = y1 + t * D
    dx, dy = px - proj_x, py - proj_y
    return (dx * dx + dy * dy) <= (tolerance * tolerance)


# ── input() override ─────────────────────────────────────

def input(prompt=''):
    """Ask the user a question using Scratch's ask block."""
    if prompt:
        return ask_question(str(prompt))
    return get_answer()
