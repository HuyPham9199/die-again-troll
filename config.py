"""Global constants. Keep values data-only — no logic here."""

# --- Display ---
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 540
FPS_CAP = 120
TITLE = "Die Agail: Troll"
VERSION = "1.0.01"
FPS_REFRESH_SECONDS = 5.0     # how often the on-screen FPS readout updates

# --- World ---
GRID_SIZE = 40           # default; per-level value overrides via JSON
GRAVITY = 2400.0         # px/s^2

# --- Player ---
PLAYER_MOVE_SPEED = 360.0       # px/s
PLAYER_JUMP_VELOCITY = -880.0   # px/s
PLAYER_MAX_FALL = 1600.0        # px/s
PLAYER_COYOTE_TIME = 0.08       # s — forgiveness window after walking off ledge
PLAYER_JUMP_BUFFER = 0.10       # s — buffered jump press before landing

# --- Camera ---
CAMERA_LERP = 8.0
TRAUMA_DECAY = 1.6
TRAUMA_MAX_OFFSET = 24.0

# --- Tile codes (mirrors GDD §4.1, extended) ---
TILE_AIR = 0
TILE_SOLID = 1
TILE_HIDDEN_SPIKE = 2
TILE_INVISIBLE_BLOCK = 3
TILE_FAKE_FLOOR = 4          # looks solid; collapses when stepped on
TILE_CEILING_SPIKE = 5       # hangs from above, drops on the player below
TILE_CRUSHER = 6             # floats up high, slams down when player enters its column
TILE_GROUND_SPIKE = 7        # looks like normal floor; spikes erupt upward on contact
TILE_TIMED_FLOOR = 8         # looks like floor; cracks then disappears after a short delay
TILE_FALLING_BLOCK = 9       # heavy block in the air; instant drop when player walks under

# Per-trap tunables.
GROUND_SPIKE_WIND_UP = 0.08  # seconds before the eruption becomes lethal
TIMED_FLOOR_BREAK_TIME = 0.4 # seconds from first touch to full collapse
FALLING_BLOCK_SPEED = 2000.0 # px/s constant drop velocity

# How long a fake floor stays "crumbling" before disappearing entirely.
# Short enough that a player walking onto it cannot outrun the collapse.
FAKE_FLOOR_CRUMBLE_TIME = 0.06
# Range in tile-widths within which a ceiling spike triggers its drop.
CEILING_SPIKE_TRIGGER_RADIUS = 1.2
# Delay between crusher activation and the actual slam.
CRUSHER_WIND_UP = 0.25
CRUSHER_SPEED = 1400.0       # px/s

# --- Neon Dark palette ---
COLOR_BG = (12, 12, 20)
COLOR_GRID = (28, 28, 44)
COLOR_SOLID = (60, 220, 200)         # cyan-mint
COLOR_SOLID_EDGE = (120, 255, 240)
COLOR_PLAYER = (255, 90, 180)         # neon pink
COLOR_GOAL = (255, 220, 60)           # neon yellow
COLOR_SPIKE = (255, 70, 90)           # neon red
COLOR_TEXT = (240, 240, 250)
COLOR_TEXT_DIM = (140, 140, 170)
COLOR_HINT = (180, 120, 255)          # neon purple (debug-only reveal)

# --- Particle Pool ---
PARTICLE_POOL_SIZE = 200

# --- Save ---
SAVE_FILE = "save.dat"
