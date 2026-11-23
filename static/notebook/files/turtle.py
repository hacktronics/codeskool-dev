"""Turtle graphics for CodeSkool.

A practical subset of Python's standard ``turtle`` module, drawn on the
Scratch stage by moving the turtle sprite::

    import turtle

    t = turtle.Turtle()
    t.pendown()
    t.forward(100)
    t.right(90)

Every drawing call routes through codeskool's synchronous-XHR bridge to
the same VM opcodes the Turtle blocks use, so blocks and typed code drive
one and the same turtle.

The common turtle commands are implemented for real. Anything CodeSkool
does not implement (custom shapes, undo, the Tk canvas, screen event
handlers, ...) is accepted as a harmless no-op so ordinary turtle
programs never crash on a missing name. For key / mouse interaction use
the sprite's normal event blocks ("when key pressed", "when this sprite
clicked").
"""

import math

from codeskool import _send, _sprite_name, _parse_val, ask_question


# ── Movement ──────────────────────────────────────────────

def forward(steps):
    """Move the turtle forward by the given number of steps."""
    _send(_sprite_name(), 'turtle_forward', {'STEPS': steps})


def backward(steps):
    """Move the turtle backward by the given number of steps."""
    _send(_sprite_name(), 'turtle_back', {'STEPS': steps})


def right(angle):
    """Turn the turtle clockwise by the given number of degrees."""
    _send(_sprite_name(), 'turtle_turnRight', {'DEG': angle})


def left(angle):
    """Turn the turtle counter-clockwise by the given number of degrees."""
    _send(_sprite_name(), 'turtle_turnLeft', {'DEG': angle})


fd = forward
back = backward
bk = backward
rt = right
lt = left


# ── Position ──────────────────────────────────────────────

def goto(x, y=None):
    """Move the turtle to an absolute (x, y) position."""
    if y is None and isinstance(x, (tuple, list)):
        x, y = x[0], x[1]
    _send(_sprite_name(), 'turtle_goTo', {'X': x, 'Y': y})


def setx(x):
    """Set only the turtle's x coordinate."""
    goto(x, ycor())


def sety(y):
    """Set only the turtle's y coordinate."""
    goto(xcor(), y)


def setheading(angle):
    """Point the turtle at an absolute heading (0 = east, 90 = north)."""
    _send(_sprite_name(), 'turtle_setHeading', {'DEG': angle})


def home():
    """Send the turtle back to (0, 0) facing east."""
    _send(_sprite_name(), 'turtle_home', {})


setpos = goto
setposition = goto
seth = setheading


# ── Pen ───────────────────────────────────────────────────

def penup():
    """Lift the pen — the turtle moves without drawing."""
    _send(_sprite_name(), 'turtle_penUp', {})


def pendown():
    """Lower the pen — the turtle draws a trail as it moves."""
    _send(_sprite_name(), 'turtle_penDown', {})


def pencolor(color):
    """Set the pen colour (a CSS colour string, e.g. "red" or "#ff0000")."""
    _send(_sprite_name(), 'turtle_setPenColor', {'COLOR': color})


def color(*args):
    """Set the pen colour. A second (fill) colour argument is accepted for
    compatibility, but CodeSkool uses one colour for both pen and fill."""
    if args:
        pencolor(args[0])


def fillcolor(*args):
    """Set the fill colour. CodeSkool uses one colour for both pen and
    fill, so this sets that shared colour."""
    if args:
        pencolor(args[0])


def pensize(width):
    """Set the pen thickness in stage units."""
    _send(_sprite_name(), 'turtle_setPenSize', {'SIZE': width})


pu = penup
up = penup
pd = pendown
down = pendown
width = pensize


# ── Marks ─────────────────────────────────────────────────

def stamp():
    """Leave an imprint of the turtle on the stage."""
    _send(_sprite_name(), 'turtle_stamp', {})


def dot(size=None):
    """Draw a filled dot at the turtle's current position."""
    _send(_sprite_name(), 'turtle_dot', {'SIZE': 0 if size is None else size})


def clear():
    """Erase everything the turtle has drawn."""
    _send(_sprite_name(), 'turtle_clear', {})


def bgcolor(color):
    """Paint the whole background a colour, e.g. 'black' or '#202020'."""
    _send(_sprite_name(), 'turtle_setBackground', {'COLOR': color})


# ── Shapes + fill ─────────────────────────────────────────

def circle(radius, extent=None, steps=None):
    """Draw a circle or arc of the given radius.

    Positive radius curves to the turtle's left (counter-clockwise),
    negative to the right. Pass ``extent`` (in degrees) for a partial arc,
    and ``steps`` to control how many straight segments approximate it.
    """
    # Whole circle, default smoothness — let the VM draw it in one call.
    if steps is None and (extent is None or abs(extent) >= 360):
        _send(_sprite_name(), 'turtle_circle', {'RADIUS': radius})
        return
    # Arc (or explicit step count) — walk it as small forward/turn steps,
    # the same way the standard turtle module does.
    if extent is None:
        extent = 360
    if steps is None:
        frac = abs(extent) / 360.0
        steps = 1 + int(min(11.0 + (abs(radius) / 6.0), 59.0) * frac)
    steps = max(1, int(steps))
    w = float(extent) / steps
    w2 = 0.5 * w
    length = 2.0 * radius * math.sin(math.radians(w2))
    if radius < 0:
        length, w, w2 = -length, -w, -w2
    left(w2)
    for _ in range(steps):
        forward(length)
        left(w)
    left(-w2)


def begin_fill():
    """Start tracking the turtle's path for a filled shape."""
    _send(_sprite_name(), 'turtle_beginFill', {})


def end_fill():
    """Fill the shape traced since begin_fill()."""
    _send(_sprite_name(), 'turtle_endFill', {})


# ── Turtle state ──────────────────────────────────────────

# Standard turtle accepts a 0-10 number for speed; map it to CodeSkool's
# named speeds so both ``turtle.speed(0)`` and ``turtle.speed('fast')`` work.
_SPEED_WORDS = {
    0: 'instant', 1: 'slowest', 2: 'slowest', 3: 'slow', 4: 'slow',
    5: 'normal', 6: 'normal', 7: 'normal', 8: 'fast', 9: 'fast', 10: 'fastest'
}


def speed(value):
    """Set the animation speed.

    Accepts a CodeSkool speed name ('instant', 'slowest', 'slow',
    'normal', 'fast', 'fastest') or a standard-turtle 0-10 number.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = _SPEED_WORDS.get(int(value), 'normal')
    _send(_sprite_name(), 'turtle_setSpeed', {'SPEED': value})


def showturtle():
    """Make the turtle sprite visible."""
    _send(_sprite_name(), 'turtle_showTurtle', {})


def hideturtle():
    """Hide the turtle sprite — its trail stays on the stage."""
    _send(_sprite_name(), 'turtle_hideTurtle', {})


st = showturtle
ht = hideturtle


# ── Reporters ─────────────────────────────────────────────

def xcor():
    """Return the turtle's x coordinate."""
    return _parse_val(_send(_sprite_name(), 'turtle_xPosition', {}))


def ycor():
    """Return the turtle's y coordinate."""
    return _parse_val(_send(_sprite_name(), 'turtle_yPosition', {}))


def heading():
    """Return the turtle's heading in degrees (0 = east)."""
    return _parse_val(_send(_sprite_name(), 'turtle_heading', {}))


def position():
    """Return the turtle's (x, y) position as a tuple."""
    return (xcor(), ycor())


pos = position


def towards(x, y=None):
    """Return the heading from the turtle toward (x, y), in degrees."""
    if y is None and isinstance(x, (tuple, list)):
        x, y = x[0], x[1]
    dx = (x or 0) - (xcor() or 0)
    dy = (y or 0) - (ycor() or 0)
    return math.degrees(math.atan2(dy, dx)) % 360.0


def distance(x, y=None):
    """Return the distance from the turtle to (x, y)."""
    if y is None and isinstance(x, (tuple, list)):
        x, y = x[0], x[1]
    return math.hypot((x or 0) - (xcor() or 0), (y or 0) - (ycor() or 0))


# ── Window / screen info ──────────────────────────────────

def window_width():
    """Return the stage width in steps."""
    return 480


def window_height():
    """Return the stage height in steps."""
    return 360


def textinput(title, prompt):
    """Ask the user for text — uses CodeSkool's ask box."""
    return ask_question(prompt)


def numinput(title, prompt, default=None, minval=None, maxval=None):
    """Ask the user for a number — uses CodeSkool's ask box."""
    answer = ask_question(prompt)
    try:
        return float(answer)
    except (TypeError, ValueError):
        return default


def reset():
    """Erase the drawing and send the turtle home (centre, facing east)."""
    clear()
    penup()
    goto(0, 0)
    setheading(0)
    pendown()


# ── End-of-program helpers (no-ops on CodeSkool) ──────────
# Standard turtle needs done() / mainloop() to keep the window open. On
# CodeSkool the drawing is already on the stage, so these just return.

def done(*args, **kwargs):
    """End the turtle program. No-op on CodeSkool — the drawing stays."""
    pass


mainloop = done


def exitonclick(*args, **kwargs):
    """Standard turtle waits for a click, then closes. No-op on CodeSkool."""
    pass


def bye(*args, **kwargs):
    """Close the turtle screen. No-op on CodeSkool."""
    pass


# ── Catch-all ─────────────────────────────────────────────
# Any turtle feature CodeSkool does not implement becomes a harmless
# no-op, so ordinary turtle programs never crash on a missing name.

def __getattr__(name):
    """Return a do-nothing callable for unimplemented turtle names."""
    if name.startswith('__') and name.endswith('__'):
        raise AttributeError(name)

    def _noop(*args, **kwargs):
        return None

    return _noop


# ── Screen ────────────────────────────────────────────────
# CodeSkool draws on the Scratch stage, so window controls are accepted
# but do nothing.

class _Screen:
    """The turtle screen. Window controls are no-ops on CodeSkool."""

    def bgcolor(self, *args, **kwargs):
        if args:
            bgcolor(args[0])

    def clear(self, *args, **kwargs):
        clear()

    def clearscreen(self, *args, **kwargs):
        clear()

    def reset(self, *args, **kwargs):
        reset()

    def resetscreen(self, *args, **kwargs):
        reset()

    def window_width(self, *args, **kwargs):
        return 480

    def window_height(self, *args, **kwargs):
        return 360

    def textinput(self, title, prompt):
        return ask_question(prompt)

    def numinput(self, title, prompt, *args, **kwargs):
        answer = ask_question(prompt)
        try:
            return float(answer)
        except (TypeError, ValueError):
            return None

    def __getattr__(self, name):
        """Window controls CodeSkool does not implement are no-ops."""
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)

        def _noop(*args, **kwargs):
            return None

        return _noop


_screen = _Screen()


def Screen():
    """Return the turtle screen object."""
    return _screen


def getscreen():
    """Return the turtle screen object."""
    return _screen


# ── Turtle class ──────────────────────────────────────────
# CodeSkool runs one turtle — the current sprite. For now every Turtle()
# drives that same turtle; multiple independent turtles are a future
# addition. Creating a Turtle() sends it home (centre, facing east, pen
# down) so code reads the same as standard Python turtle.

class Turtle:
    """A turtle you can move and draw with — ``t = turtle.Turtle()``."""

    def __init__(self, *args, **kwargs):
        penup()
        goto(0, 0)
        setheading(0)
        pendown()

    def forward(self, steps):
        """Move forward by the given number of steps."""
        forward(steps)

    def backward(self, steps):
        """Move backward by the given number of steps."""
        backward(steps)

    def right(self, angle):
        """Turn clockwise by the given number of degrees."""
        right(angle)

    def left(self, angle):
        """Turn counter-clockwise by the given number of degrees."""
        left(angle)

    def goto(self, x, y=None):
        """Move to an absolute (x, y) position."""
        goto(x, y)

    def setx(self, x):
        """Set only the x coordinate."""
        setx(x)

    def sety(self, y):
        """Set only the y coordinate."""
        sety(y)

    def setheading(self, angle):
        """Point at an absolute heading (0 = east)."""
        setheading(angle)

    def home(self):
        """Return to the centre, facing east."""
        home()

    def penup(self):
        """Lift the pen — move without drawing."""
        penup()

    def pendown(self):
        """Lower the pen — draw while moving."""
        pendown()

    def pencolor(self, color):
        """Set the pen colour."""
        pencolor(color)

    def color(self, *args):
        """Set this turtle's pen colour."""
        color(*args)

    def fillcolor(self, *args):
        """Set this turtle's fill colour."""
        fillcolor(*args)

    def pensize(self, size):
        """Set the pen thickness."""
        pensize(size)

    def stamp(self):
        """Leave an imprint of the turtle."""
        stamp()

    def dot(self, size=None):
        """Draw a filled dot at the turtle's position."""
        dot(size)

    def clear(self):
        """Erase everything drawn so far."""
        clear()

    def circle(self, radius, extent=None, steps=None):
        """Walk a circle or arc of the given radius."""
        circle(radius, extent, steps)

    def begin_fill(self):
        """Start a filled shape."""
        begin_fill()

    def end_fill(self):
        """Fill the shape traced since begin_fill()."""
        end_fill()

    def speed(self, value):
        """Set the turtle speed."""
        speed(value)

    def showturtle(self):
        """Make the turtle visible."""
        showturtle()

    def hideturtle(self):
        """Hide the turtle."""
        hideturtle()

    def xcor(self):
        """Return the x coordinate."""
        return xcor()

    def ycor(self):
        """Return the y coordinate."""
        return ycor()

    def heading(self):
        """Return the heading in degrees (0 = east)."""
        return heading()

    def position(self):
        """Return the (x, y) position as a tuple."""
        return position()

    def towards(self, x, y=None):
        """Return the heading toward (x, y)."""
        return towards(x, y)

    def distance(self, x, y=None):
        """Return the distance to (x, y)."""
        return distance(x, y)

    def reset(self):
        """Erase this turtle's drawing and send it home."""
        reset()

    def __getattr__(self, name):
        """Turtle features CodeSkool does not implement are no-ops."""
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)

        def _noop(*args, **kwargs):
            return None

        return _noop

    # Short aliases, matching the standard turtle module.
    fd = forward
    bk = backward
    back = backward
    rt = right
    lt = left
    setpos = goto
    setposition = goto
    seth = setheading
    pu = penup
    up = penup
    pd = pendown
    down = pendown
    width = pensize
    st = showturtle
    ht = hideturtle
    pos = position


# Standard turtle exposes Pen / RawTurtle as aliases of Turtle.
Pen = Turtle
RawTurtle = Turtle
