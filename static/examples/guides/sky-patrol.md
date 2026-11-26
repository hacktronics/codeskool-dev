# Sky Patrol

Fly a blue propeller plane above eight islands, shoot three incoming raiders, and pass the bonus ring. The example has six independent sprites and 214 ordinary editable blocks. You build it in five small parts, and each part ends with something you can try.

## Controls

Left/right arrows turn and bank. Up/down arrows change altitude. Hold Space to fire repeated shots. The plane flies forward continuously. Green flag restarts the mission.

Optional phone remote: add the existing **GamePad BLE** extension, use its **Download Android Gamepad App** button (cc.codeskool.gamepadapp). Put that Android app in its BLE controller mode. On the computer, click the GamePad BLE palette's connection-status button, select the phone in the browser Bluetooth chooser, then use Connect in the normal device dialog. Refresh can reopen device discovery if needed. The app's steering x/y values are tested against -10 and 10 in the visible scripts. Cross or button A fires. This uses the existing Android/Bluetooth feature. It does not add a browser phone remote or claim iPhone support. Physical phone/Bluetooth hardware has not been tested for this example; adjust the threshold or swap the signs if your app's steering direction differs. Keyboard control works without connecting a phone.

## Before you start

1. Enter **3D and XR Studio** and start a blank 3D project. Select **Stage** in the lower-right panel, open **Choose an Environment**, and select **Sky Archipelago**. The chooser applies the island landscape to Stage at 80000% scale. Use **Choose a 3D Object** for the six actor rows below, including three copies of **Red Enemy Plane**, and rename those sprites exactly as listed.
2. In Scene Editor, select Ambient Light in the scene list, then set its Properties > Intensity to 1.2.
3. Set each actor's size with **Transform > set all scale** and position with **Transform > go to x/y/z**. Use the actor table's block coordinates; 36 position units equal one world unit, so a plane at 60 units high is y 2160.
4. In Variables create every variable below **for all sprites**. Add the existing **AI**, **World** and **GamePad BLE** extensions if their palettes are not visible. The AI proximity blocks compare the named sprites' positions in 3D.
5. Create each listed My Block on its named sprite, with no inputs and **Run without screen refresh unchecked**. No JavaScript, Python, custom controller, or changed block is required.

| Sprite name | Pick this from the 3D library | x | y | z | Scale % |
|---|---|---:|---:|---:|---:|
| Blue Patrol | Blue Propeller Plane | 0 | 2160 | 5400 | 820 |
| Red Raider | Red Enemy Plane | 0 | 2160 | 1800 | 820 |
| Crimson Ace | Red Enemy Plane | -792 | 2304 | 180 | 820 |
| Scarlet Wing | Red Enemy Plane | 900 | 2016 | -1440 | 820 |
| Patrol Bolt | Energy Bolt | 36000 | 36000 | 0 | 160 |
| Bonus Ring | Flight Ring | 0 | 1980 | 3600 | 1000 |

Apply the actor rows with Transform blocks, then remove those temporary setup blocks: actor placement and scale stay in the saved model settings. The islands belong to Stage and have no sprite or scripts. The Stage environment uses 80000% scale for its 700 x 800 world-unit scene. Aircraft point along local -Z, so Heading 0 flies toward decreasing z with the follow camera behind the plane. The hidden bolt starts parked far away and its script hides it until fired.

## Variables

| Name | Starting value |
|---|---:|
| Score | 0 |
| Health | 3 |
| Raiders Left | 3 |
| Heading | 0 |
| Bank | 0 |
| Flight x | 0 |
| Flight y | 2160 |
| Flight z | 5400 |
| Shot heading | 0 |

Numbers are input values; square brackets name dropdown choices. Set **x rotation to 0** throughout: climbing changes y position, and the plane banks around z. Every procedure definition remains separate from its green-flag stack.

## Part 1: fly the plane (Blue Patrol)

The first block, `set fog to`, adds a light haze so far islands fade into the distance. It is the World extension's block and nothing else depends on it.

```text
when green flag clicked
set fog to [#d5e6ee] at distance (650)
set [Heading] to 0
go to x: 0 y: 2160 z: 5400
show sprite
set [Flight x] to 0
set [Flight y] to 2160
set [Flight z] to 5400
follow [Blue Patrol] at distance (900)
forever
  Steer aircraft
  Fly forward
  wait (0.03) seconds
```

```text
define Steer aircraft
set [Bank] to 0
if <(<key [left arrow] pressed?> or ((steering angle [x]) < -10))> then
  change [Heading] by (3)
  set [Bank] to 25
if <(<key [right arrow] pressed?> or ((steering angle [x]) > 10))> then
  change [Heading] by (-3)
  set [Bank] to -25
if <(<key [up arrow] pressed?> or ((steering angle [y]) < -10))> then
  change [y] position by 18
if <(<key [down arrow] pressed?> or ((steering angle [y]) > 10))> then
  change [y] position by -18
set rotation to x: 0 y: (Heading) z: (Bank)
```

```text
define Fly forward
move (36) steps forward
if <((y position) < 1080)> then
  set [y] position to (1080)
if <((y position) > 6480)> then
  set [y] position to (6480)
if <((([abs] of (x position)) > 11520) or (([abs] of (z position)) > 13320))> then
  go to x: 0 y: 2160 z: 5400
  set [Heading] to 0
set [Flight x] to (x position)
set [Flight y] to (y position)
set [Flight z] to (z position)
```

**Try it:** click the flag. The plane flies forward by itself, left/right turn and bank it, up/down climb and dive. Flying off the edge of the world puts it back at the start.

## Part 2: shoot (Patrol Bolt)

One reusable sprite makes repeated shots; it is hidden and parked when it is not flying.

```text
when green flag clicked
hide sprite
go to x: 36000 y: 36000 z: 0
forever
  wait until <(<key [space] pressed?> or (<is [cross] pressed?> or <is [buttonA] pressed?>))>
  Fire one bolt
  wait (0.15) seconds
```

```text
define Fire one bolt
set [Shot heading] to (Heading)
go to x: (Flight x) y: (Flight y) z: (Flight z)
set rotation to x: 0 y: (Shot heading) z: 0
show sprite
repeat (30)
  move (180) steps forward
  wait (0.03) seconds
hide sprite
go to x: 36000 y: 36000 z: 0
```

**Try it:** click the flag and hold Space. Bolts fly straight ahead from the plane, even while it turns.

## Part 3: the raiders (Red Raider, Crimson Ace, Scarlet Wing)

Build **Red Raider** first. Its start spot and the parking spot after a hit are the only differences between the three raiders.

```text
when green flag clicked
go to x: 0 y: 2160 z: 1800
show sprite
wait (3) seconds
forever
  move [Red Raider] towards [Blue Patrol] at speed (450)
  Check contacts
  wait (0.03) seconds
```

```text
define Check contacts
if <<is [Red Raider] within (216) of [Patrol Bolt]?>> then
  change [Score] by (10)
  change [Raiders Left] by (-1)
  hide sprite
  go to x: -36000 y: 36000 z: 0
  stop [this script]
if <<is [Red Raider] within (216) of [Blue Patrol]?>> then
  change [Health] by (-1)
  move [Red Raider] away from [Blue Patrol] at speed (108000)
  wait (0.8) seconds
```

**Try it:** click the flag. The raider chases the plane. A bolt that touches it hides it; touching the plane costs health.

Now copy both scripts to the other two raiders (drag them onto the sprite in the sprite list) and change three things in each copy: the sprite's own name inside the blocks, the `go to` start spot, and the park spot after a hit.

| Sprite | Start spot (x, y, z) | Park spot after a hit (x, y, z) |
|---|---|---|
| Red Raider | 0, 2160, 1800 | -36000, 36000, 0 |
| Crimson Ace | -792, 2304, 180 | -36000, 39600, 0 |
| Scarlet Wing | 900, 2016, -1440 | -36000, 43200, 0 |

## Part 4: score, health and the bonus ring

Add three lines at the top of Blue Patrol's first green-flag script, right after the `set fog` block:

```text
set [Score] to 0
set [Health] to 3
set [Raiders Left] to 3
```

Then give Blue Patrol a second green-flag script that shows the mission text and ends the game:

```text
when green flag clicked
wait (0.2) seconds
create text [Sky Patrol] named [Mission]
attach [Mission] to [Blue Patrol]
set offset of [Mission] to x: (0) y: (216) z: (0)
set font size of [Mission] to (64)
set billboard of [Mission] [on]
forever
  set text of [Mission] to ((Score  join (Score)) join (  Health  join (Health)))
  if <((Raiders Left) = 0)> then
    set text of [Mission] to Mission complete! All three raiders defeated.
    stop [all]
  if <((Health) < 1)> then
    set text of [Mission] to Mission over. Click the green flag to try again.
    stop [all]
  wait (0.1) seconds
```

Finally the **Bonus Ring** sprite:

```text
when green flag clicked
go to x: 0 y: 1980 z: 3600
show sprite
wait (0.2) seconds
wait until <<is [Blue Patrol] within (264) of [Bonus Ring]?>>
change [Score] by (5)
hide sprite
go to x: -36000 y: 57600 z: 0
```

**Try it:** play the whole game. Score 10 for each raider, plus 5 for the ring. A raider within 6 world units costs one health. Win by defeating all three before Health reaches zero. Save using File > Save to your computer.

## Part 5 (optional): phone controller

The optional phone remote in Controls uses the same Steer aircraft and Fire one bolt scripts: nothing more to build.

## How it works

**Steer aircraft** checks either the keyboard or the existing BLE steering reporters. **Fly forward** uses sine and cosine of Heading; altitude stays between 30 and 180 world units. Leaving the world boundary returns the aircraft to the start.

**Fire one bolt** copies the heading at launch, so a shot stays straight while the plane turns.

Each raider waits three seconds, then uses the AI move-towards block, which turns it to face the player. **Check contacts** uses the existing AI within-distance reporter. A hit hides and parks a defeated raider far away.

Try changing the raider speed 450 to 700, the flight step 36 to 48, or the steering thresholds 10 and -10. Every model comes from the 3D library, so a saved project reloads them from the library and stays small.
