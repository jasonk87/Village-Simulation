import curses
import curses.ascii # For checking 'q'
import heapq
import collections
import random # For random roaming
import time

# Node Representation
class Node:
    def __init__(self, position, parent=None, g=0, h=0):
        self.position = position
        self.parent = parent
        self.g = g
        self.h = h
        self.f = g + h

    def __eq__(self, other):
        return self.position == other.position

    def __lt__(self, other):
        return self.f < other.f

    def __hash__(self):
        return hash(self.position)

# Heuristic Function
def manhattan_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

# Path Reconstruction
def reconstruct_path(current_node):
    path = []
    while current_node:
        path.append(current_node.position)
        current_node = current_node.parent
    return path[::-1]

# A* Function
def astar_pathfind(map_data, start_pos, end_pos, walkable_tiles=['G', 'W', '@', 'T']): # 'T' for Target visualization
    map_height = len(map_data)
    map_width = len(map_data[0])

    start_node = Node(position=start_pos, g=0, h=manhattan_distance(start_pos, end_pos))
    end_node = Node(position=end_pos)

    open_list = []
    heapq.heappush(open_list, start_node)

    closed_list_g_costs = {}
    open_list_nodes = {start_node.position: start_node}

    while open_list:
        current_node = heapq.heappop(open_list)

        if current_node.position not in open_list_nodes or open_list_nodes[current_node.position].f < current_node.f:
            continue
        del open_list_nodes[current_node.position]

        if current_node.position == end_node.position:
            return reconstruct_path(current_node)

        closed_list_g_costs[current_node.position] = current_node.g

        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor_pos = (current_node.position[0] + dy, current_node.position[1] + dx)

            if not (0 <= neighbor_pos[0] < map_height and 0 <= neighbor_pos[1] < map_width):
                continue
            # Use the provided walkable_tiles list for A*
            if map_data[neighbor_pos[0]][neighbor_pos[1]] not in walkable_tiles:
                continue

            neighbor_g = current_node.g + 1

            if neighbor_pos in closed_list_g_costs and closed_list_g_costs[neighbor_pos] <= neighbor_g:
                continue

            if neighbor_pos in open_list_nodes and open_list_nodes[neighbor_pos].g <= neighbor_g:
                continue

            neighbor_h = manhattan_distance(neighbor_pos, end_pos)
            neighbor_node = Node(position=neighbor_pos, parent=current_node, g=neighbor_g, h=neighbor_h)

            heapq.heappush(open_list, neighbor_node)
            open_list_nodes[neighbor_pos] = neighbor_node

    return None

class GameState:
    def __init__(self, map_data, npc_char, npc_y, npc_x):
        self.map_data = map_data
        self.npc_char = npc_char
        self.npc_y = npc_y
        self.npc_x = npc_x
        self.npc_target_y = None
        self.npc_target_x = None
        self.npc_path = []
        # Define walkable characters for AI logic
        self.walkable_map_chars = ['G', 'W', 'T'] # '@' is where NPC is, 'T' is a generic target marker

def draw_map(stdscr, game_state, color_pairs):
    path_coords_set = set(game_state.npc_path) if game_state.npc_path else set()

    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            color_pair_to_use = color_pairs['default']
            display_char = char_val
            if char_val == 'G':
                color_pair_to_use = color_pairs['grass']
            elif char_val == 'W':
                color_pair_to_use = color_pairs['water']
            elif char_val == '#':
                color_pair_to_use = color_pairs['wall']
            elif char_val == 'T': # Target visualization
                color_pair_to_use = color_pairs['target']

            if (r, c) in path_coords_set and (r,c) != (game_state.npc_y, game_state.npc_x):
                display_char = '.'

            try:
                stdscr.addch(r, c, display_char, color_pair_to_use)
            except curses.error:
                pass

    try:
        stdscr.addch(game_state.npc_y, game_state.npc_x, game_state.npc_char, color_pairs['npc'])
    except curses.error:
        pass

    if game_state.npc_target_y is not None:
        try:
            # Display current target and path length for debugging
            # Ensure this string doesn't exceed screen width
            status_msg = f"Target:({game_state.npc_target_y},{game_state.npc_target_x}) Path:{len(game_state.npc_path)}"
            stdscr.addstr(len(game_state.map_data), 0, status_msg[:curses.COLS-1])
        except curses.error:
            pass


def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    color_pairs = {
        'default': curses.color_pair(1), 'grass': curses.color_pair(2),
        'water': curses.color_pair(3), 'npc': curses.color_pair(4),
        'wall': curses.color_pair(5), 'target': curses.color_pair(6)
    }
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK) # NPC
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)   # Wall
    curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)    # Target 'T'

    # Using a slightly modified map for better testing of random roaming
    initial_map_data = [
        "####################",
        "#G@GGGGGGGGGGGGGGGT#", # NPC start, T is a potential target spot
        "#G################G#",
        "#G#GGGGGGGGGGGGGG#G#",
        "#G#G###########G#G#",
        "#G#G#GGGGGGG#G#G#G#",
        "#G#G#G#####G#G#G#G#",
        "#G#G#GGGGGGG#G#G#G#",
        "#G#G###########G#G#",
        "#GGGGGGGGGGGGGGGGG#",
        "####################"
    ]

    npc_initial_y, npc_initial_x = 1, 2
    for r, row in enumerate(initial_map_data):
        if '@' in row:
            npc_initial_y, npc_initial_x = r, row.find('@')
            map_list = list(row)
            map_list[npc_initial_x] = 'G'
            initial_map_data[r] = "".join(map_list)
            break

    game_state = GameState(map_data=initial_map_data, npc_char='@', npc_y=npc_initial_y, npc_x=npc_initial_x)

    # Initial target can be None to trigger random roaming, or set one for initial movement.
    # game_state.npc_target_y, game_state.npc_target_x = 1, 18 # Example: 'T' on the map

    stdscr.nodelay(True)
    loop_counter = 0
    # Define walkable characters for A* to include generic targets like 'T' if used on map
    astar_walkable_tiles = game_state.walkable_map_chars + [game_state.npc_char]


    while True:
        stdscr.clear()

        # 1. Identify Idle State & 2. Implement Random Target Selection
        if game_state.npc_target_y is None and not game_state.npc_path:
            print("NPC is idle, selecting new random target...") # For non-curses debugging
            walkable_tiles_coords = []
            for r, row_str in enumerate(game_state.map_data):
                for c, char_val in enumerate(row_str):
                    if char_val in game_state.walkable_map_chars: # Use GameState's definition
                        # Ensure NPC doesn't target its own current spot if it's the only option
                        if (r,c) != (game_state.npc_y, game_state.npc_x):
                             walkable_tiles_coords.append((r, c))

            if not walkable_tiles_coords and (game_state.npc_y, game_state.npc_x) not in walkable_tiles_coords:
                 # Only current spot is walkable, or no walkable spots at all (edge case)
                 # Add current spot back if it was excluded and is the only option.
                 current_tile_char = game_state.map_data[game_state.npc_y][game_state.npc_x]
                 if current_tile_char in game_state.walkable_map_chars:
                     walkable_tiles_coords.append((game_state.npc_y, game_state.npc_x))

            if walkable_tiles_coords:
                new_target_y, new_target_x = random.choice(walkable_tiles_coords)
                game_state.npc_target_y = new_target_y
                game_state.npc_target_x = new_target_x
                print(f"NPC new random target: ({game_state.npc_target_y}, {game_state.npc_target_x})")
            else:
                print("No walkable tiles found for random target.") # Should not happen with current map

        # Path Calculation (if target is set and no path)
        if game_state.npc_target_y is not None and not game_state.npc_path:
            path = astar_pathfind(game_state.map_data,
                                  (game_state.npc_y, game_state.npc_x),
                                  (game_state.npc_target_y, game_state.npc_target_x),
                                  astar_walkable_tiles)
            if path:
                game_state.npc_path = path
                print(f"Path found to ({game_state.npc_target_y},{game_state.npc_target_x}): {game_state.npc_path}")
                if game_state.npc_path and game_state.npc_path[0] == (game_state.npc_y, game_state.npc_x):
                    game_state.npc_path.pop(0)
            else:
                print(f"No path found to target ({game_state.npc_target_y},{game_state.npc_target_x}). Clearing target.")
                game_state.npc_target_y = None
                game_state.npc_target_x = None

        # Movement Along Path
        loop_counter += 1
        if loop_counter % 3 == 0:
            if game_state.npc_path:
                next_step = game_state.npc_path.pop(0)
                game_state.npc_y, game_state.npc_x = next_step

                if (game_state.npc_y, game_state.npc_x) == (game_state.npc_target_y, game_state.npc_target_x):
                    print(f"NPC reached target at ({game_state.npc_y}, {game_state.npc_x}).")
                    game_state.npc_target_y = None
                    game_state.npc_target_x = None
                    game_state.npc_path = []

        draw_map(stdscr, game_state, color_pairs)
        stdscr.refresh()
        curses.napms(100) # Game speed

        key = stdscr.getch()

        if key != curses.ERR:
            if key == ord('q') or key == curses.ascii.ESC:
                break

            # Player control only if NPC has no AI target (i.e., not actively pursuing a random target)
            if game_state.npc_target_y is None:
                new_npc_y, new_npc_x = game_state.npc_y, game_state.npc_x
                if key == curses.KEY_UP: new_npc_y -= 1
                elif key == curses.KEY_DOWN: new_npc_y += 1
                elif key == curses.KEY_LEFT: new_npc_x -= 1
                elif key == curses.KEY_RIGHT: new_npc_x += 1

                map_height = len(game_state.map_data)
                map_width = len(game_state.map_data[0])
                current_tile_char = game_state.map_data[new_npc_y][new_npc_x] if (0 <= new_npc_y < map_height and 0 <= new_npc_x < map_width) else '#'

                if 0 <= new_npc_y < map_height and \
                   0 <= new_npc_x < map_width and \
                   current_tile_char != '#': # Check against map walls
                    game_state.npc_y, game_state.npc_x = new_npc_y, new_npc_x
                    game_state.npc_path = [] # Clear AI path if player moves NPC manually
                    print(f"NPC moved by player to: ({game_state.npc_y}, {game_state.npc_x})")


if __name__ == "__main__":
    # Wrap a try-except to catch potential curses errors during development
    # and print them if curses.wrapper doesn't handle them cleanly for stdout.
    try:
        curses.wrapper(main)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure terminal is reset if wrapper didn't exit cleanly (though wrapper should handle this)
        # This is more of a safeguard during development if wrapper itself errors out.
        try:
            curses.endwin()
        except: # nosemgrep: bare-except
            pass # endwin may fail if curses never initialized
        print("Game ended.") # This will print after curses has ended.
