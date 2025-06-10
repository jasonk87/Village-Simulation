import curses
import curses.ascii # For checking 'q'
import heapq
import collections
import random
import time

# --- Constants ---
NPC_INITIAL_ENERGY_MIN = 80
NPC_INITIAL_ENERGY_MAX = 100
NPC_MAX_ENERGY = 100
ENERGY_DEPLETION_RATE = 0.1
ENERGY_REPLENISH_RATE = 1.0
LOW_ENERGY_THRESHOLD = 25 # New constant
REST_SPOT_CHAR = 'R'
DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES = 'G'

AI_MODE_ROAMING = "roaming"
AI_MODE_SEEKING_REST = "seeking_rest"
AI_MODE_RESTING = "resting"

# --- NPC Data Structure ---
class Npc:
    def __init__(self, id, y, x, char, color_pair_index):
        self.id = id
        self.y = y
        self.x = x
        self.char = char
        self.color_pair_index = color_pair_index
        self.target_y = None
        self.target_x = None
        self.path = []
        self.energy = random.randint(NPC_INITIAL_ENERGY_MIN, NPC_INITIAL_ENERGY_MAX)
        self.max_energy = NPC_MAX_ENERGY
        self.ai_mode = AI_MODE_ROAMING
        # self.is_idle is effectively replaced by (self.ai_mode == AI_MODE_ROAMING and self.target_y is None and not self.path)

# --- Node Representation (for A*) ---
class Node: # ... (Node class remains the same) ...
    def __init__(self, position, parent=None, g=0, h=0):
        self.position = position
        self.parent = parent
        self.g = g
        self.h = h
        self.f = g + h
    def __eq__(self, other): return self.position == other.position
    def __lt__(self, other): return self.f < other.f
    def __hash__(self): return hash(self.position)

# --- Heuristic Function ---
def manhattan_distance(pos1, pos2): # ... (remains the same) ...
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

# --- Path Reconstruction ---
def reconstruct_path(current_node): # ... (remains the same) ...
    path = []
    while current_node:
        path.append(current_node.position)
        current_node = current_node.parent
    return path[::-1]

# --- A* Function ---
def astar_pathfind(map_data, start_pos, end_pos, walkable_tiles_map_chars=['G', 'W', 'T', ' ']): # ... (remains the same) ...
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
            if map_data[neighbor_pos[0]][neighbor_pos[1]] not in walkable_tiles_map_chars:
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

# --- GameState Class ---
class GameState: # ... (GameState.__init__ remains largely the same, Npc init updated before) ...
    def __init__(self, map_data_strings, npc_definitions):
        self.map_data = []
        self.npcs = []
        self.walkable_map_chars = ['G', 'W', 'T', ' ']
        self.rest_spot_locations = []
        npc_id_counter = 0
        temp_map = [list(row_str) for row_str in map_data_strings]
        print("--- NPC and Feature Initialization ---")
        for r, row_list in enumerate(temp_map):
            for c, char_val in enumerate(row_list):
                if char_val in npc_definitions:
                    npc_def = npc_definitions[char_val]
                    new_npc = Npc(id=npc_id_counter, y=r, x=c, char=char_val, color_pair_index=npc_def['color_pair_index'])
                    self.npcs.append(new_npc)
                    print(f"Initialized NPC ID {new_npc.id} ('{new_npc.char}') at ({new_npc.y},{new_npc.x}), E:{new_npc.energy}, Mode:{new_npc.ai_mode}")
                    npc_id_counter += 1
                    temp_map[r][c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == REST_SPOT_CHAR:
                    self.rest_spot_locations.append((r,c))
                    print(f"Initialized Rest Spot at ({r},{c})")
                    temp_map[r][c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
        self.map_data = ["".join(row_list) for row_list in temp_map]
        print(f"Total NPCs initialized: {len(self.npcs)}")
        print(f"Rest Spot Locations: {self.rest_spot_locations}")
        print("------------------------------------")

# --- Drawing Function ---
def draw_map(stdscr, game_state, color_pairs): # ... (draw_map remains largely the same, status display updated for ai_mode) ...
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            color_pair_to_use = color_pairs.get('default', curses.color_pair(1))
            display_char = char_val
            if char_val == 'G': color_pair_to_use = color_pairs.get('grass', curses.color_pair(1))
            elif char_val == 'W': color_pair_to_use = color_pairs.get('water', curses.color_pair(1))
            elif char_val == '#': color_pair_to_use = color_pairs.get('wall', curses.color_pair(1))
            elif char_val == 'T': color_pair_to_use = color_pairs.get('target', curses.color_pair(1))
            elif char_val == ' ': color_pair_to_use = color_pairs.get('floor', curses.color_pair(1))
            try: stdscr.addch(r, c, display_char, color_pair_to_use)
            except curses.error: pass
    for r_y, r_x in game_state.rest_spot_locations:
        try: stdscr.addch(r_y, r_x, REST_SPOT_CHAR, color_pairs.get('rest_spot', curses.color_pair(1)))
        except curses.error: pass
    if game_state.npcs:
        npc_to_viz_path = game_state.npcs[0]
        if npc_to_viz_path.path:
            for r_path, c_path in npc_to_viz_path.path:
                if (r_path, c_path) != (npc_to_viz_path.y, npc_to_viz_path.x):
                    try: stdscr.addch(r_path, c_path, '.', color_pairs.get('path', curses.color_pair(1)))
                    except curses.error: pass
    for npc in game_state.npcs:
        try: stdscr.addch(npc.y, npc.x, npc.char, curses.color_pair(npc.color_pair_index))
        except curses.error: pass
    for i, npc_to_display in enumerate(game_state.npcs[:min(3, len(game_state.npcs))]):
        status_line_y_pos = len(game_state.map_data) + i
        if status_line_y_pos < curses.LINES -1 :
            target_info = "No Target"
            if npc_to_display.target_y is not None: target_info = f"T:({npc_to_display.target_y},{npc_to_display.target_x})"
            path_info = f"P:{len(npc_to_display.path)}"
            mode_info = npc_to_display.ai_mode.capitalize()
            energy_info = f"E:{int(npc_to_display.energy)}/{npc_to_display.max_energy}" # Display energy as int
            status_msg = f"NPC{npc_to_display.id}({npc_to_display.char})@({npc_to_display.y},{npc_to_display.x}) {target_info} {path_info} {energy_info} {mode_info}"
            try: stdscr.addstr(status_line_y_pos, 0, status_msg[:curses.COLS-1])
            except curses.error: pass

# --- Main Game Logic ---
def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    color_pairs = {
        'default': curses.color_pair(1), 'grass': curses.color_pair(2),
        'water': curses.color_pair(3), 'npc_yellow': curses.color_pair(4),
        'wall': curses.color_pair(5), 'target': curses.color_pair(6),
        'npc_cyan': curses.color_pair(7), 'rest_spot': curses.color_pair(8),
        'path': curses.color_pair(9), 'floor': curses.color_pair(1)
    }
    # ... (init_pair calls remain the same) ...
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK); curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK); curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE); curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_CYAN, curses.COLOR_BLACK); curses.init_pair(8, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(9, curses.COLOR_CYAN, curses.COLOR_BLACK)

    initial_map_data_strings = [
        "####################", "#G@GRGGGGGGGGGGGGRT#", "#G#####%#####R####G#", "#G#GGGGGRGGGGGGGG#G#",
        "#G#G###########G#G#", "#G#G#RGGGGGG#G#G#G#", "#G#G#G#####G#G#G#G#", "#G#G#GGGGGGG#G#G#G#",
        "#G#GR##########G#G#", "#GGGGGGGGGGGGGGGGG#", "####################"
    ]
    npc_definitions_on_map = {'@': {'color_pair_index': 4}, '%': {'color_pair_index': 7}}
    game_state = GameState(map_data_strings=initial_map_data_strings, npc_definitions=npc_definitions_on_map)

    all_walkable_coords = []
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            if char_val in game_state.walkable_map_chars: all_walkable_coords.append((r,c))

    stdscr.nodelay(True)
    loop_counter = 0
    astar_walkable_map_tiles = game_state.walkable_map_chars
    NPC_MOVE_FREQUENCY = 3

    while True:
        stdscr.clear()
        loop_counter += 1

        if loop_counter % 200 == 0: print(f"\n--- Game Loop Tick {loop_counter} ---") # Reduced log frequency

        for npc in game_state.npcs:
            current_npc_id_char = f"NPC {npc.id} ('{npc.char}') E:{int(npc.energy)}"

            # 1. Energy Depletion (unless resting)
            if npc.ai_mode != AI_MODE_RESTING:
                npc.energy = max(0, npc.energy - ENERGY_DEPLETION_RATE)

            # 2. AI Mode Logic
            if npc.ai_mode == AI_MODE_ROAMING:
                if npc.energy < LOW_ENERGY_THRESHOLD:
                    npc.ai_mode = AI_MODE_SEEKING_REST
                    npc.target_y, npc.target_x, npc.path = None, None, [] # Clear old target/path
                    print(f"{current_npc_id_char} low energy, now {AI_MODE_SEEKING_REST}.")
                    # Finding nearest rest spot moved to SEEKING_REST block if no target
                elif npc.target_y is None and not npc.path: # Standard roaming idle check
                    if all_walkable_coords:
                        possible_targets = [crd for crd in all_walkable_coords if crd != (npc.y, npc.x)]
                        if not possible_targets: possible_targets = all_walkable_coords
                        if possible_targets:
                            npc.target_y, npc.target_x = random.choice(possible_targets)
                            print(f"{current_npc_id_char} {AI_MODE_ROAMING}, new random target: ({npc.target_y}, {npc.target_x})")

            elif npc.ai_mode == AI_MODE_SEEKING_REST:
                if npc.target_y is None: # Only find new rest spot if one isn't already targeted
                    best_target_spot = None
                    shortest_path_len = float('inf')
                    if not game_state.rest_spot_locations:
                        print(f"{current_npc_id_char} wants to rest, but no rest spots defined!")
                        npc.ai_mode = AI_MODE_ROAMING # Fallback: no rest spots, go back to roaming
                    else:
                        for spot_y, spot_x in game_state.rest_spot_locations:
                            # Ensure target is not current location if already at a rest spot
                            if (npc.y, npc.x) == (spot_y, spot_x):
                                best_target_spot = (spot_y, spot_x) # Already at a rest spot
                                npc.path = [] # Clear path as we are there
                                print(f"{current_npc_id_char} is already at a rest spot ({spot_y},{spot_x}).")
                                break

                            path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (spot_y, spot_x), astar_walkable_map_tiles)
                            if path:
                                if len(path) < shortest_path_len:
                                    shortest_path_len = len(path)
                                    best_target_spot = (spot_y, spot_x)

                        if best_target_spot:
                            npc.target_y, npc.target_x = best_target_spot
                            # Path will be calculated in the pathfinding section below
                            print(f"{current_npc_id_char} seeking rest, best target: ({npc.target_y}, {npc.target_x}) with path len {shortest_path_len if shortest_path_len != float('inf') else 'N/A'}")
                        else:
                            print(f"{current_npc_id_char} {AI_MODE_SEEKING_REST}, no reachable rest spot found! Will roam instead.")
                            npc.ai_mode = AI_MODE_ROAMING # Fallback if no spot is reachable

                # Check for arrival at rest spot (target_y is set by above block or previous iteration)
                if npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x):
                    # Verify it's a rest spot
                    if (npc.y, npc.x) in game_state.rest_spot_locations:
                        npc.ai_mode = AI_MODE_RESTING
                        npc.path = [] # Clear path upon arrival for resting
                        print(f"{current_npc_id_char} reached rest spot at ({npc.y},{npc.x}) and is now {AI_MODE_RESTING}.")
                    else: # Arrived at a target that isn't a rest spot (shouldn't happen in SEEKING_REST)
                        print(f"{current_npc_id_char} arrived at target ({npc.y},{npc.x}) which is NOT a rest spot. Switching to Roaming.")
                        npc.ai_mode = AI_MODE_ROAMING
                        npc.target_y, npc.target_x, npc.path = None, None, []


            elif npc.ai_mode == AI_MODE_RESTING:
                npc.energy = min(NPC_MAX_ENERGY, npc.energy + ENERGY_REPLENISH_RATE)
                if loop_counter % 20 == 0: # Log resting progress periodically
                     print(f"{current_npc_id_char} is {AI_MODE_RESTING} at ({npc.y},{npc.x}). Energy: {int(npc.energy)}")
                if npc.energy >= NPC_MAX_ENERGY:
                    npc.ai_mode = AI_MODE_ROAMING
                    npc.target_y, npc.target_x, npc.path = None, None, [] # Clear target/path
                    print(f"{current_npc_id_char} fully rested, now {AI_MODE_ROAMING}.")

            # Path Calculation (common for ROAMING and SEEKING_REST if target set and no path)
            if npc.target_y is not None and not npc.path and npc.ai_mode != AI_MODE_RESTING:
                calculated_path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (npc.target_y, npc.target_x), astar_walkable_map_tiles)
                if calculated_path:
                    npc.path = calculated_path
                    print(f"Path found for {current_npc_id_char} to ({npc.target_y},{npc.target_x}), length: {len(npc.path)}")
                    if npc.path and npc.path[0] == (npc.y, npc.x): npc.path.pop(0)
                else:
                    print(f"No path for {current_npc_id_char} to target ({npc.target_y},{npc.target_x}). Mode: {npc.ai_mode}. Clearing target.")
                    npc.target_y, npc.target_x = None, None
                    if npc.ai_mode == AI_MODE_SEEKING_REST: # If couldn't path to chosen rest spot, try finding another next tick
                        pass # Stays in SEEKING_REST, will try to find another spot
                    else: # Roaming and path failed
                        npc.ai_mode = AI_MODE_ROAMING # Ensure it can pick a new random target

            # Movement Logic
            if loop_counter % NPC_MOVE_FREQUENCY == 0:
                if npc.path and npc.ai_mode != AI_MODE_RESTING:
                    next_y, next_x = npc.path.pop(0)
                    is_next_step_occupied = any(o.id != npc.id and o.y == next_y and o.x == next_x for o in game_state.npcs)
                    if not is_next_step_occupied:
                        old_y, old_x = npc.y, npc.x
                        npc.y, npc.x = next_y, next_x
                        # print(f"{current_npc_id_char} moved from ({old_y},{old_x}) to ({npc.y},{npc.x})") # Verbose
                    else:
                        npc.path.insert(0, (next_y, next_x))
                        # print(f"{current_npc_id_char} path blocked by another NPC at ({next_y},{next_x}). Waiting.")

                    # Arrival Check (after moving)
                    if npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x):
                        print(f"{current_npc_id_char} arrived at target ({npc.y},{npc.x}) in mode {npc.ai_mode}.")
                        # Specific arrival logic for modes (e.g. start resting)
                        if npc.ai_mode == AI_MODE_SEEKING_REST:
                             if (npc.y, npc.x) in game_state.rest_spot_locations:
                                npc.ai_mode = AI_MODE_RESTING
                                print(f"{current_npc_id_char} started {AI_MODE_RESTING}.")
                             else: # Arrived at a target that wasn't a rest spot (error in logic?)
                                npc.ai_mode = AI_MODE_ROAMING
                                print(f"{current_npc_id_char} arrived at non-rest-spot while seeking rest. Roaming.")
                        else: # e.g. arrived at roaming target
                            npc.ai_mode = AI_MODE_ROAMING # Default to roaming after reaching other targets

                        npc.target_y, npc.target_x, npc.path = None, None, []
                    elif not npc.path and npc.target_y is not None: # Path ended, but not at target
                        print(f"{current_npc_id_char} path ended, not at target. C:({npc.y},{npc.x}) T:({npc.target_y},{npc.target_x}). Re-evaluating.")
                        npc.target_y, npc.target_x = None, None # Clear target to force re-evaluation

        draw_map(stdscr, game_state, color_pairs)
        stdscr.refresh()
        curses.napms(100)

        key = stdscr.getch()
        if key != curses.ERR and (key == ord('q') or key == curses.ascii.ESC): break

if __name__ == "__main__":
    try: curses.wrapper(main)
    except Exception as e: print(f"An error occurred: {e}"); traceback.print_exc()
    finally:
        try: curses.endwin()
        except: pass
        print("Game ended."); sys.stdout.flush(); sys.stderr.flush()
