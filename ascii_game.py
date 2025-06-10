import curses
import curses.ascii # For checking 'q'

# 1. Define GameState
class GameState:
    def __init__(self, map_data, npc_char, npc_y, npc_x):
        self.map_data = map_data
        self.npc_char = npc_char
        self.npc_y = npc_y
        self.npc_x = npc_x

        # Optional: Store color pair indices if desired
        # These are defined in main() for now, but could be moved here
        # self.npc_color_pair = 4
        # self.wall_color_pair = 5
        # self.grass_color_pair = 2
        # self.water_color_pair = 3
        # self.default_color_pair = 1

# Drawing Function - Modified to accept game_state
def draw_map(stdscr, game_state, color_pairs):
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            color_pair_to_use = color_pairs['default']
            if char_val == 'G':
                color_pair_to_use = color_pairs['grass']
            elif char_val == 'W':
                color_pair_to_use = color_pairs['water']
            elif char_val == '#':
                color_pair_to_use = color_pairs['wall']

            try:
                stdscr.addch(r, c, char_val, color_pair_to_use)
            except curses.error:
                pass

    # Draw NPC
    try:
        stdscr.addch(game_state.npc_y, game_state.npc_x, game_state.npc_char, color_pairs['npc'])
    except curses.error:
        pass

def main(stdscr):
    # Initialization
    curses.curs_set(0)  # Hide the cursor

    # Initialize colors
    curses.start_color()
    # Store color pairs in a dictionary for easier access via GameState or direct passing
    color_pairs = {
        'default': curses.color_pair(1),
        'grass': curses.color_pair(2),
        'water': curses.color_pair(3),
        'npc': curses.color_pair(4),
        'wall': curses.color_pair(5)
    }
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Default
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Grass (G)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)   # Water (W)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK) # NPC (@)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Wall (#)

    # Define initial map data
    initial_map_data = [
        "####################",
        "#GGGGGGGGGGGGGGGGGG#",
        "#GGGGWWWWWWWWGGGGGG#",
        "#GGGGWGGGGGGWGGGGGG#",
        "#GGGGWGGGGGGWGGGGGG#",
        "#GGGGWGGGGGGWWWWGGG#",
        "#GGGGWGGGGGGGGGGGGG#",
        "#GGGGGGGGGGGGGGGGGG#",
        "#GGGGGGGGGGGGGGGGGG#",
        "####################"
    ]

    # 2. Instantiate GameState
    game_state = GameState(
        map_data=initial_map_data,
        npc_char='@',
        npc_y=2,
        npc_x=2
    )

    # Game Loop
    stdscr.nodelay(True)  # Make getch() non-blocking

    while True:
        stdscr.clear()
        # 3. Update Function Calls and Logic
        draw_map(stdscr, game_state, color_pairs) # Pass game_state and color_pairs
        stdscr.refresh()

        curses.napms(100)  # Pause for 100ms

        key = stdscr.getch()

        if key != curses.ERR: # A key was pressed
            if key == ord('q') or key == curses.ascii.ESC: # 'q' or Escape to quit
                break

            # Use game_state for current NPC position
            new_npc_y, new_npc_x = game_state.npc_y, game_state.npc_x

            if key == curses.KEY_UP:
                new_npc_y -= 1
            elif key == curses.KEY_DOWN:
                new_npc_y += 1
            elif key == curses.KEY_LEFT:
                new_npc_x -= 1
            elif key == curses.KEY_RIGHT:
                new_npc_x += 1

            # Collision Detection/Boundary Checks using game_state
            map_height = len(game_state.map_data)
            map_width = len(game_state.map_data[0])

            if 0 <= new_npc_y < map_height and \
               0 <= new_npc_x < map_width and \
               game_state.map_data[new_npc_y][new_npc_x] != '#':
                # Update NPC position in game_state
                game_state.npc_y, game_state.npc_x = new_npc_y, new_npc_x

# Main Execution Block
if __name__ == "__main__":
    curses.wrapper(main)
