3D WORLD PROJECTS

Open 3D and XR Studio, then File > Learn > Examples > 3D.

Forest Rescue: arrow keys; reach all three hikers.
Voxel Treasure Hunt: arrow keys; find the gold chest.
Checkpoint Circuit: Up drives, Left/Right steer; pass the three gates in order. Grass makes the car skid, a gate post makes it crash.
Circuit Time Trial (opens with a new 3D project; guide CircuitTimeTrial.txt): a full timed lap with the same road rules.
Traffic Race: the same road rules, with a taxi, a police car and a van to overtake (TrafficRace.txt).
Robot Football Practice: arrows drive; stand behind the ball and press Space to kick.
Robot Gate Trail: arrows; visit the three numbered gates.
Obstacle Explorer: arrows; explore and reach the three gates.
Sky Patrol: arrows steer/climb; Space fires. The existing GamePad BLE Android controller is optional.

Each world is a Stage environment. To rebuild an example, select Stage in the lower-right panel, open Choose an Environment, and select the named world. Use Choose a 3D Object only for gameplay actors such as characters, cars, balls and gates. The saved project stores the Stage ground setting separately from actor sprites; all rules remain ordinary editable blocks. Every project except Robot Football Practice starts with the existing World set-fog block for light haze.

Build instructions: ForestRescue.txt, VoxelTreasure.txt, CheckpointCircuit.txt, RobotFootball.txt, RobotSensorTrail.txt (Robot Gate Trail), ObstacleExplorer.txt, sky-patrol.md in this folder. Each guide lists the Stage environment, actor library models, sizes, starting coordinates, variables and visible block recipes; sky-patrol.md builds the game in five parts that you can test one by one.

Stage environments and thumbnails: /static/models/3d/world-content/environments/manifest.json. Actor models: /static/models/3d/world-content/sprites/manifest.json. Environment choice applies the Stage scale automatically. Set actor sizes with Transform > set all scale and actor positions with Transform > go to x/y/z, in position units (36 per world unit). Library aliases include Red Race Car (renamed Red Racing Car in Checkpoint Circuit), Hiker (Hiker 1/2/3), Gold Chest (Treasure Chest), and Robot Car (Trail Robot or Football Robot).
