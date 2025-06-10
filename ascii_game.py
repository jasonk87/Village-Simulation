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
LOW_ENERGY_THRESHOLD = 25
REST_SPOT_CHAR = 'R'
DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES = 'G'

RESOURCE_WOOD_CHAR = 'W'
RESOURCE_STONE_CHAR = 'S'
GATHER_AMOUNT = 1
RESOURCE_TYPES = ["wood", "stone"]
GATHER_TIME_TICKS = 5
CHANCE_TO_SEEK_RESOURCE = 0.3

AI_MODE_ROAMING = "roaming"
AI_MODE_SEEKING_REST = "seeking_rest"
AI_MODE_RESTING = "resting"
AI_MODE_SEEKING_RESOURCE = "seeking_resource"
AI_MODE_GATHERING_RESOURCE = "gathering_resource"
AI_MODE_PATROLLING = "patrolling"

# --- NPC Data Structure ---
class Npc:
    def __init__(self, id, y, x, char, color_pair_index):
        self.id = id; self.y = y; self.x = x; self.char = char
        self.color_pair_index = color_pair_index
        self.target_y = None; self.target_x = None; self.path = []
        self.energy = random.randint(NPC_INITIAL_ENERGY_MIN, NPC_INITIAL_ENERGY_MAX)
        self.max_energy = NPC_MAX_ENERGY
        self.ai_mode = AI_MODE_ROAMING
        self.inventory = {"wood": 0, "stone": 0}
        self.current_resource_target_type = None
        self.gathering_timer = 0
        self.patrol_path_id = None
        self.current_patrol_waypoint_index = 0
        self.interrupted_patrol_path_id = None
        self.interrupted_waypoint_index = 0

# --- Node, Heuristic, Path Reconstruction, A* (remain the same) ---
class Node:
    def __init__(self, position, parent=None, g=0, h=0):
        self.position = position; self.parent = parent; self.g = g; self.h = h; self.f = g + h
    def __eq__(self, other): return self.position == other.position
    def __lt__(self, other): return self.f < other.f
    def __hash__(self): return hash(self.position)
def manhattan_distance(pos1, pos2): return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
def reconstruct_path(current_node):
    path = [];
    while current_node: path.append(current_node.position); current_node = current_node.parent
    return path[::-1]
def astar_pathfind(map_data, start_pos, end_pos, walkable_tiles_map_chars=['G', ' ', 'T']):
    map_height = len(map_data); map_width = len(map_data[0])
    start_node = Node(position=start_pos, g=0, h=manhattan_distance(start_pos, end_pos))
    end_node = Node(position=end_pos)
    open_list = []; heapq.heappush(open_list, start_node)
    closed_list_g_costs = {}; open_list_nodes = {start_node.position: start_node}
    while open_list:
        current_node = heapq.heappop(open_list)
        if current_node.position not in open_list_nodes or open_list_nodes[current_node.position].f < current_node.f: continue
        del open_list_nodes[current_node.position]
        if current_node.position == end_node.position: return reconstruct_path(current_node)
        closed_list_g_costs[current_node.position] = current_node.g
        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor_pos = (current_node.position[0] + dy, current_node.position[1] + dx)
            if not (0 <= neighbor_pos[0] < map_height and 0 <= neighbor_pos[1] < map_width): continue
            if map_data[neighbor_pos[0]][neighbor_pos[1]] not in walkable_tiles_map_chars: continue
            neighbor_g = current_node.g + 1
            if neighbor_pos in closed_list_g_costs and closed_list_g_costs[neighbor_pos] <= neighbor_g: continue
            if neighbor_pos in open_list_nodes and open_list_nodes[neighbor_pos].g <= neighbor_g: continue
            neighbor_h = manhattan_distance(neighbor_pos, end_pos)
            neighbor_node = Node(position=neighbor_pos, parent=current_node, g=neighbor_g, h=neighbor_h)
            heapq.heappush(open_list, neighbor_node); open_list_nodes[neighbor_pos] = neighbor_node
    return None

# --- GameState Class (remains the same) ---
class GameState:
    def __init__(self, map_data_strings, npc_definitions):
        self.map_data = []
        self.npcs = []
        self.walkable_map_chars = ['G', 'T', ' ']
        if DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES not in self.walkable_map_chars:
             self.walkable_map_chars.append(DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES)
        self.rest_spot_locations = []
        self.resource_locations = {"wood": [], "stone": []}
        self.patrol_paths = {
            "route_gate_patrol": [ (1, 1), (1, 3), (2, 3), (2, 1) ],
            "route_resource_patrol": [ (7, 7), (7, 12), (9, 12), (9, 7) ]
        }
        # print(f"Defined patrol paths: {self.patrol_paths}") # Keep log less verbose for testing
        npc_id_counter = 0
        temp_map = [list(row_str) for row_str in map_data_strings]
        # print("--- NPC, Resource, Feature Initialization ---") # Keep log less verbose
        for r, row_list in enumerate(temp_map):
            for c, char_val in enumerate(row_list):
                if char_val in npc_definitions:
                    npc_def = npc_definitions[char_val]
                    new_npc = Npc(id=npc_id_counter, y=r, x=c, char=char_val, color_pair_index=npc_def['color_pair_index'])
                    if char_val == '@':
                        if "route_gate_patrol" in self.patrol_paths: new_npc.patrol_path_id = "route_gate_patrol"
                    elif char_val == '%':
                         if "route_resource_patrol" in self.patrol_paths: new_npc.patrol_path_id = "route_resource_patrol"
                    self.npcs.append(new_npc)
                    # print(f"Initialized NPC ID {new_npc.id} ('{new_npc.char}') at ({new_npc.y},{new_npc.x}), E:{new_npc.energy}, Mode:{new_npc.ai_mode}, Patrol:{new_npc.patrol_path_id}, Inv:{new_npc.inventory}")
                    npc_id_counter += 1
                    temp_map[r][c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == REST_SPOT_CHAR:
                    self.rest_spot_locations.append((r,c)); temp_map[r][c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == RESOURCE_WOOD_CHAR:
                    self.resource_locations["wood"].append((r,c)); temp_map[r][c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == RESOURCE_STONE_CHAR:
                    self.resource_locations["stone"].append((r,c)); temp_map[r][c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
        self.map_data = ["".join(row_list) for row_list in temp_map]
        # print(f"Total NPCs initialized: {len(self.npcs)}")
        # print("-------------------------------------------")

# --- Drawing Function ---
def draw_map(stdscr, game_state, color_pairs):
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            color_pair_to_use = color_pairs.get('default', curses.color_pair(1))
            display_char = char_val
            if char_val == 'G': color_pair_to_use = color_pairs.get('grass', curses.color_pair(1))
            elif char_val == '#': color_pair_to_use = color_pairs.get('wall', curses.color_pair(1))
            elif char_val == 'T': color_pair_to_use = color_pairs.get('target', curses.color_pair(1))
            elif char_val == ' ': color_pair_to_use = color_pairs.get('floor', curses.color_pair(1))
            try: stdscr.addch(r, c, display_char, color_pair_to_use)
            except curses.error: pass
    for r_y, r_x in game_state.rest_spot_locations:
        try: stdscr.addch(r_y, r_x, REST_SPOT_CHAR, color_pairs.get('rest_spot', curses.color_pair(1)))
        except curses.error: pass
    for r_y, r_x in game_state.resource_locations["wood"]:
        try: stdscr.addch(r_y, r_x, RESOURCE_WOOD_CHAR, color_pairs.get('wood_res', curses.color_pair(1)))
        except curses.error: pass
    for r_y, r_x in game_state.resource_locations["stone"]:
        try: stdscr.addch(r_y, r_x, RESOURCE_STONE_CHAR, color_pairs.get('stone_res', curses.color_pair(1)))
        except curses.error: pass
    for npc_to_viz_path in game_state.npcs:
        if npc_to_viz_path.path and npc_to_viz_path.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE]:
            for r_path, c_path in npc_to_viz_path.path:
                if (r_path, c_path) != (npc_to_viz_path.y, npc_to_viz_path.x):
                    try: stdscr.addch(r_path, c_path, '.', color_pairs.get('path', curses.color_pair(1)))
                    except curses.error: pass
    for npc in game_state.npcs:
        try: stdscr.addch(npc.y, npc.x, npc.char, curses.color_pair(npc.color_pair_index))
        except curses.error: pass

    # Enhanced Status Display
    for i, npc_to_display in enumerate(game_state.npcs[:min(curses.LINES - len(game_state.map_data) - 1, 3)]):
        status_line_y_pos = len(game_state.map_data) + i
        if status_line_y_pos < curses.LINES -1 :
            target_info = "No Target"
            if npc_to_display.target_y is not None:
                target_info = f"T:({npc_to_display.target_y},{npc_to_display.target_x})"
                if npc_to_display.ai_mode == AI_MODE_SEEKING_RESOURCE and npc_to_display.current_resource_target_type:
                    target_info += f" Res:{npc_to_display.current_resource_target_type[:3]}"
                elif npc_to_display.ai_mode == AI_MODE_PATROLLING and npc_to_display.patrol_path_id:
                    target_info += f" Pat:{npc_to_display.patrol_path_id[:7]}"

            path_info = f"P:{len(npc_to_display.path)}"
            mode_info = npc_to_display.ai_mode
            # Mode abbreviations for status line
            if mode_info == AI_MODE_ROAMING: mode_info = "Roam"
            elif mode_info == AI_MODE_SEEKING_REST: mode_info = "SeekR"
            elif mode_info == AI_MODE_RESTING: mode_info = "Rest"
            elif mode_info == AI_MODE_SEEKING_RESOURCE: mode_info = "SeekRes"
            elif mode_info == AI_MODE_GATHERING_RESOURCE: mode_info = f"GathRes({npc_to_display.gathering_timer})"
            elif mode_info == AI_MODE_PATROLLING: mode_info = f"Pat({npc_to_display.current_patrol_waypoint_index})" # Abbreviated

            energy_info = f"E:{int(npc_to_display.energy)}"
            inv_info = f"Inv(W:{npc_to_display.inventory['wood']},S:{npc_to_display.inventory['stone']})"
            status_msg = f"N{npc_to_display.id}({npc_to_display.char})@({npc_to_display.y},{npc_to_display.x}) {target_info} {path_info} {energy_info} {inv_info} {mode_info}"
            try:
                stdscr.move(status_line_y_pos, 0); stdscr.clrtoeol()
                stdscr.addstr(status_line_y_pos, 0, status_msg[:curses.COLS-1])
            except curses.error: pass

# --- Main Game Logic ---
def main(stdscr):
    curses.curs_set(0); curses.start_color()
    color_pairs = {
        'default': curses.color_pair(1), 'grass': curses.color_pair(2), 'water_tile': curses.color_pair(3),
        'npc_yellow': curses.color_pair(4), 'wall': curses.color_pair(5), 'target': curses.color_pair(6),
        'npc_cyan': curses.color_pair(7), 'rest_spot': curses.color_pair(8), 'path': curses.color_pair(9),
        'floor': curses.color_pair(1), 'wood_res': curses.color_pair(10), 'stone_res': curses.color_pair(11)
    }
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK); curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK); curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE); curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_CYAN, curses.COLOR_BLACK); curses.init_pair(8, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(9, curses.COLOR_CYAN, curses.COLOR_BLACK); curses.init_pair(10, curses.COLOR_YELLOW, curses.COLOR_DKGRAY)
    curses.init_pair(11, curses.COLOR_WHITE, curses.COLOR_DKGRAY)
    initial_map_data_strings = [
        "####################", "#G@GRGWGSGGGGGGGRT#", "#G#####%#####R####G#", "#G#GGGGGRGSGGGGGG#G#",
        "#G#G###########G#G#", "#G#G#RGGGGWWS#G#G#G#", "#G#G#G#####G#G#G#G#", "#G#G#GGGGGGG#G#G#G#",
        "#G#GR####S#####G#G#", "#GGGSGGGGGGWGGGGG#", "####################"
    ]
    npc_definitions_on_map = {'@': {'color_pair_index': 4}, '%': {'color_pair_index': 7}}
    game_state = GameState(map_data_strings=initial_map_data_strings, npc_definitions=npc_definitions_on_map)
    all_walkable_coords = []
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            if char_val in game_state.walkable_map_chars: all_walkable_coords.append((r,c))
    stdscr.nodelay(True); loop_counter = 0
    astar_walkable_map_tiles = game_state.walkable_map_chars
    NPC_MOVE_FREQUENCY = 3

    while True:
        stdscr.clear(); loop_counter += 1
        # if loop_counter % 200 == 0: print(f"\n--- Game Loop Tick {loop_counter} ---")

        for npc in game_state.npcs:
            current_npc_log_prefix = f"N{npc.id}({npc.char} E:{int(npc.energy)} M:{npc.ai_mode[:5]})" # Shorter prefix
            npc_is_effectively_idle = (npc.target_y is None and not npc.path)

            if npc.ai_mode != AI_MODE_RESTING and npc.energy > 0 :
                npc.energy = max(0, npc.energy - ENERGY_DEPLETION_RATE)

            # --- AI Mode Logic ---
            if npc.ai_mode == AI_MODE_RESTING:
                npc.energy = min(NPC_MAX_ENERGY, npc.energy + ENERGY_REPLENISH_RATE)
                # if loop_counter % 20 == 0: print(f"{current_npc_log_prefix} is RESTING. New E: {int(npc.energy)}") # Less frequent log
                if npc.energy >= NPC_MAX_ENERGY:
                    npc.target_y, npc.target_x, npc.path = None, None, []
                    if npc.interrupted_patrol_path_id:
                        npc.ai_mode = AI_MODE_PATROLLING; npc.patrol_path_id = npc.interrupted_patrol_path_id
                        npc.current_patrol_waypoint_index = npc.interrupted_waypoint_index
                        npc.interrupted_patrol_path_id, npc.interrupted_waypoint_index = None, 0
                        print(f"{current_npc_log_prefix} rested, resuming PATROL {npc.patrol_path_id} WP{npc.current_patrol_waypoint_index}")
                    elif npc.patrol_path_id:
                        npc.ai_mode = AI_MODE_PATROLLING
                        print(f"{current_npc_log_prefix} rested, starting PATROL {npc.patrol_path_id}")
                    else:
                        npc.ai_mode = AI_MODE_ROAMING; print(f"{current_npc_log_prefix} rested, now ROAMING.")

            elif npc.energy < LOW_ENERGY_THRESHOLD and npc.ai_mode != AI_MODE_SEEKING_REST:
                interrupted_task = False
                if npc.ai_mode == AI_MODE_PATROLLING and npc.patrol_path_id:
                    npc.interrupted_patrol_path_id = npc.patrol_path_id
                    npc.interrupted_waypoint_index = npc.current_patrol_waypoint_index
                    interrupted_task = True; print(f"{current_npc_log_prefix} low E, interrupting PATROL {npc.patrol_path_id} WP{npc.current_patrol_waypoint_index}")
                elif npc.ai_mode in [AI_MODE_SEEKING_RESOURCE, AI_MODE_GATHERING_RESOURCE]:
                     interrupted_task = True; print(f"{current_npc_log_prefix} low E, interrupting RESOURCE task ({npc.current_resource_target_type}).")

                npc.ai_mode = AI_MODE_SEEKING_REST
                npc.target_y, npc.target_x, npc.path = None, None, []
                npc.current_resource_target_type = None; npc.gathering_timer = 0
                if interrupted_task: npc.patrol_path_id = None # Clear active patrol if it was interrupted
                # print(f"{current_npc_log_prefix} now SEEKING_REST.") # Logged by seeking rest logic if no target

            elif npc.ai_mode == AI_MODE_SEEKING_REST:
                if npc_is_effectively_idle :
                    best_target_spot, shortest_path_len = None, float('inf')
                    if not game_state.rest_spot_locations: print(f"{current_npc_log_prefix} wants rest, NO REST SPOTS! Roaming."); npc.ai_mode = AI_MODE_ROAMING
                    else:
                        for spot_y, spot_x in game_state.rest_spot_locations:
                            if (npc.y, npc.x) == (spot_y, spot_x): best_target_spot=(spot_y,spot_x);npc.path=[];shortest_path_len=0;break
                            path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (spot_y, spot_x), astar_walkable_map_tiles)
                            if path and len(path) < shortest_path_len: shortest_path_len = len(path); best_target_spot = (spot_y, spot_x)
                        if best_target_spot:
                            npc.target_y, npc.target_x = best_target_spot
                            # print(f"{current_npc_log_prefix} SEEKING_REST, best T: {best_target_spot} (Path len: {shortest_path_len if shortest_path_len != float('inf') else 'N/A'})")
                            if (npc.y, npc.x) == best_target_spot: npc.ai_mode = AI_MODE_RESTING; npc.path = [] ; # print(f"{current_npc_log_prefix} is AT chosen rest spot, now RESTING.")
                        else: print(f"{current_npc_log_prefix} SEEKING_REST, NO PATH to any rest spot! Roaming."); npc.ai_mode = AI_MODE_ROAMING
                # Arrival at rest spot handled in movement logic

            elif npc.ai_mode == AI_MODE_PATROLLING:
                if npc.patrol_path_id and (npc_is_effectively_idle or (npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x))):
                    route = game_state.patrol_paths.get(npc.patrol_path_id)
                    if route:
                        if (npc.y, npc.x) == (npc.target_y, npc.target_x): # Arrived at previous waypoint
                            npc.current_patrol_waypoint_index = (npc.current_patrol_waypoint_index + 1) % len(route)
                            print(f"{current_npc_log_prefix} reached Patrol WP. Next WP idx: {npc.current_patrol_waypoint_index}")

                        npc.target_y, npc.target_x = route[npc.current_patrol_waypoint_index]
                        npc.path = []
                        # print(f"{current_npc_log_prefix} PATROLLING {npc.patrol_path_id}, next WP {npc.current_patrol_waypoint_index}: ({npc.target_y},{npc.target_x})")
                    else:
                        print(f"{current_npc_log_prefix} invalid patrol_path_id '{npc.patrol_path_id}'. Roaming."); npc.ai_mode = AI_MODE_ROAMING; npc.patrol_path_id = None

            elif npc.ai_mode == AI_MODE_GATHERING_RESOURCE:
                npc.gathering_timer -= 1
                # if loop_counter % 10 == 0: print(f"{current_npc_log_prefix} GATHERING for {npc.current_resource_target_type}. Timer: {npc.gathering_timer}")
                if npc.gathering_timer <= 0:
                    res_type = npc.current_resource_target_type
                    if res_type in npc.inventory:
                        npc.inventory[res_type] += GATHER_AMOUNT
                        print(f"{current_npc_log_prefix} gathered {GATHER_AMOUNT} {res_type}. Inv: {npc.inventory}")
                    else: print(f"{current_npc_log_prefix} ERR: Invalid res_type {res_type}.")
                    npc.ai_mode = AI_MODE_ROAMING; npc.target_y,npc.target_x,npc.path = None,None,[]; npc.current_resource_target_type = None
                    # print(f"{current_npc_log_prefix} finished gathering, now ROAMING.")

            elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE:
                if npc_is_effectively_idle:
                    # This means target was cleared or path failed, find the resource again.
                    resource_locations_of_type = game_state.resource_locations.get(npc.current_resource_target_type, [])
                    best_target_resource_spot, shortest_path_len = None, float('inf')
                    if not resource_locations_of_type:
                        print(f"{current_npc_log_prefix} wants {npc.current_resource_target_type}, but NO SPOTS! Roaming."); npc.ai_mode = AI_MODE_ROAMING; npc.current_resource_target_type = None
                    else:
                        for spot_y, spot_x in resource_locations_of_type:
                            path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (spot_y, spot_x), astar_walkable_map_tiles)
                            if path and len(path) < shortest_path_len: shortest_path_len = len(path); best_target_resource_spot = (spot_y, spot_x)
                        if best_target_resource_spot:
                            npc.target_y, npc.target_x = best_target_resource_spot
                            # print(f"{current_npc_log_prefix} {AI_MODE_SEEKING_RESOURCE} for {npc.current_resource_target_type}, target: {best_target_resource_spot}")
                        else:
                            print(f"{current_npc_log_prefix} {AI_MODE_SEEKING_RESOURCE}, NO PATH to any {npc.current_resource_target_type}! Roaming."); npc.ai_mode = AI_MODE_ROAMING; npc.current_resource_target_type = None
                # Arrival at resource spot handled in movement logic

            elif npc.ai_mode == AI_MODE_ROAMING:
                if npc_is_effectively_idle:
                    if npc.patrol_path_id:
                        npc.ai_mode = AI_MODE_PATROLLING
                        # print(f"{current_npc_log_prefix} ROAMING, has patrol_id, switching to PATROLLING.")
                    elif random.random() < CHANCE_TO_SEEK_RESOURCE and any(game_state.resource_locations.get(res_type) for res_type in RESOURCE_TYPES):
                        chosen_res_type = random.choice(RESOURCE_TYPES)
                        if game_state.resource_locations.get(chosen_res_type):
                            npc.ai_mode = AI_MODE_SEEKING_RESOURCE; npc.current_resource_target_type = chosen_res_type
                            npc.target_y, npc.target_x, npc.path = None, None, []
                            # print(f"{current_npc_log_prefix} ROAMING decided to seek resource: {chosen_res_type}.")
                    elif all_walkable_coords:
                        pc = [crd for crd in all_walkable_coords if crd != (npc.y, npc.x)]
                        if not pc: pc = all_walkable_coords
                        if pc: npc.target_y, npc.target_x = random.choice(pc)
                        # print(f"{current_npc_log_prefix} ROAMING, new random T: ({npc.target_y if npc.target_y is not None else 'N/A'}, {npc.target_x if npc.target_x is not None else 'N/A'})")

            # --- Path Calculation ---
            if npc.target_y is not None and not npc.path and npc.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE]:
                calculated_path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (npc.target_y, npc.target_x), astar_walkable_map_tiles)
                if calculated_path:
                    npc.path = calculated_path
                    if npc.path and npc.path[0] == (npc.y, npc.x): npc.path.pop(0)
                else:
                    # print(f"No path for {current_npc_log_prefix} to T:({npc.target_y},{npc.target_x}). Mode:{npc.ai_mode}. Clear T.")
                    npc.target_y, npc.target_x = None, None
                    if npc.ai_mode == AI_MODE_SEEKING_REST: pass
                    elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE: npc.current_resource_target_type = None; npc.ai_mode = AI_MODE_ROAMING
                    elif npc.ai_mode == AI_MODE_PATROLLING:
                        npc.current_patrol_waypoint_index = (npc.current_patrol_waypoint_index + 1) % len(game_state.patrol_paths.get(npc.patrol_path_id, [(0,0)]))
                    else: npc.ai_mode = AI_MODE_ROAMING

            # --- Movement & Arrival Logic ---
            if loop_counter % NPC_MOVE_FREQUENCY == 0:
                if npc.path and npc.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE]:
                    next_y, next_x = npc.path.pop(0)
                    is_next_step_occupied = any(o.id != npc.id and o.y == next_y and o.x == next_x for o in game_state.npcs)
                    if not is_next_step_occupied:
                        npc.y, npc.x = next_y, next_x
                    else:
                        npc.path.insert(0, (next_y, next_x))

                    if npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x):
                        # print(f"{current_npc_log_prefix} arrived T:({npc.y},{npc.x}) mode:{npc.ai_mode}.")
                        if npc.ai_mode == AI_MODE_SEEKING_REST and (npc.y,npc.x) in game_state.rest_spot_locations:
                            npc.ai_mode = AI_MODE_RESTING; print(f"{current_npc_log_prefix} started RESTING.")
                        elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE:
                            npc.ai_mode = AI_MODE_GATHERING_RESOURCE; npc.gathering_timer = GATHER_TIME_TICKS
                            print(f"{current_npc_log_prefix} started GATHERING for {npc.current_resource_target_type} at ({npc.y},{npc.x}).")
                        elif npc.ai_mode == AI_MODE_PATROLLING:
                            print(f"{current_npc_log_prefix} reached Patrol WP {npc.current_patrol_waypoint_index} at ({npc.y},{npc.x}).")
                            # Target for next waypoint will be set in Patrolling logic block
                        else:
                            npc.ai_mode = AI_MODE_ROAMING
                        # Clear target only if not patrolling (patrolling handles its own target updates)
                        if npc.ai_mode != AI_MODE_PATROLLING:
                            npc.target_y, npc.target_x = None, None
                        npc.path = [] # Path is consumed or target reached
                    elif not npc.path and npc.target_y is not None: # Path ended, but not at target (e.g. blocked and cleared)
                        print(f"{current_npc_log_prefix} path end, not at T. C:({npc.y},{npc.x}) T:({npc.target_y},{npc.target_x}). Clearing T.")
                        npc.target_y, npc.target_x = None, None

        draw_map(stdscr, game_state, color_pairs)
        stdscr.refresh()
        curses.napms(100)

        key = stdscr.getch()
        if key != curses.ERR and (key == ord('q') or key == curses.ascii.ESC): break

if __name__ == "__main__":
    try: curses.wrapper(main)
    except Exception as e: print(f"ERR: {e}"); traceback.print_exc()
    finally:
        try: curses.endwin()
        except: pass
        print("Game ended."); sys.stdout.flush(); sys.stderr.flush()
