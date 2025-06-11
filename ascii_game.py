import curses
import curses.ascii # For checking 'q'
import heapq
import collections
import random
import time

# --- Constants ---
NPC_INITIAL_ENERGY_MIN = 80; NPC_INITIAL_ENERGY_MAX = 100; NPC_MAX_ENERGY = 100
ENERGY_DEPLETION_RATE = 0.1; ENERGY_REPLENISH_RATE = 1.0; LOW_ENERGY_THRESHOLD = 25
REST_SPOT_CHAR = 'R'; RESOURCE_WOOD_CHAR = 'W'; RESOURCE_STONE_CHAR = 'S'
DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES = ' '
WATER_CHAR_SOURCE = '~'; WATER_ANIMATION_CHARS = ['~', '≈', '≋']; WATER_ANIMATION_SPEED = 20
GATHER_AMOUNT = 1; RESOURCE_TYPES = ["wood", "stone"]; GATHER_TIME_TICKS = 5
CHANCE_TO_SEEK_RESOURCE = 0.3
ORIGINAL_GRASS_CHAR = 'G'; GRASS_CHARS = [ORIGINAL_GRASS_CHAR, '.', ',', '`']; GRASS_VARIATION_PROBABILITY = 0.15
ORIGINAL_FLOOR_CHAR = ' '; FLOOR_CHARS = [ORIGINAL_FLOOR_CHAR, '·']; FLOOR_VARIATION_PROBABILITY = 0.05
DEFAULT_NPC_PERCEPTION_RANGE = 5; ENCOUNTER_DURATION_TICKS = 30
NPC_POSSIBLE_PERSONALITIES = ["friendly", "neutral", "gruff", "timid", "suspicious"]
VALID_ENCOUNTER_ACTIONS = ["[Talk]", "[Ignore]", "[Flee]", "[Threaten]", "[Offer_Gift]", "[Ask_For_Help]"]

AI_MODE_ROAMING = "roaming"; AI_MODE_SEEKING_REST = "seeking_rest"; AI_MODE_RESTING = "resting"
AI_MODE_SEEKING_RESOURCE = "seeking_resource"; AI_MODE_GATHERING_RESOURCE = "gathering_resource"
AI_MODE_PATROLLING = "patrolling"; AI_MODE_ENCOUNTER = "encounter"

# --- NPC Data Structure ---
class Npc: # ... (Npc class remains the same) ...
    def __init__(self, id, y, x, char, color_pair_index):
        self.id = id; self.y = y; self.x = x; self.char = char
        self.color_pair_index = color_pair_index
        self.target_y = None; self.target_x = None; self.path = []
        self.energy = random.randint(NPC_INITIAL_ENERGY_MIN, NPC_INITIAL_ENERGY_MAX)
        self.max_energy = NPC_MAX_ENERGY; self.ai_mode = AI_MODE_ROAMING
        self.inventory = {"wood": 0, "stone": 0}
        self.current_resource_target_type = None; self.gathering_timer = 0
        self.patrol_path_id = None; self.current_patrol_waypoint_index = 0
        self.interrupted_patrol_path_id = None; self.interrupted_waypoint_index = 0
        self.perception_range = DEFAULT_NPC_PERCEPTION_RANGE
        self.detected_encounter_partner_id_this_tick = None
        self.encounter_partner_id = None; self.encounter_timer = 0
        self.personality = random.choice(NPC_POSSIBLE_PERSONALITIES); self.relationships = {}
        self.previous_ai_mode = None; self.llm_raw_response = None; self.llm_parsed_action = None

# --- Node, Heuristic, Path Reconstruction, A* (remain the same) ---
class Node:
    def __init__(self, position, parent=None, g=0, h=0):
        self.position = position; self.parent = parent; self.g = g; self.h = h; self.f = g + h
    def __eq__(self, other): return self.position == other.position
    def __lt__(self, other): return self.f < other.f
    def __hash__(self): return hash(self.position)
def manhattan_distance_coords(y1, x1, y2, x2): return abs(y1 - y2) + abs(x1 - x2)
def manhattan_distance_tuples(pos1, pos2): return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
def reconstruct_path(current_node):
    path = [];
    while current_node: path.append(current_node.position); current_node = current_node.parent
    return path[::-1]
def astar_pathfind(map_data, start_pos, end_pos, walkable_tiles_map_chars=None):
    if walkable_tiles_map_chars is None:
        walkable_tiles_map_chars = GRASS_CHARS + FLOOR_CHARS + ['T']
        if DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES not in walkable_tiles_map_chars:
             walkable_tiles_map_chars.append(DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES)
    map_height = len(map_data); map_width = len(map_data[0])
    start_node = Node(position=start_pos, g=0, h=manhattan_distance_tuples(start_pos, end_pos))
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
            neighbor_h = manhattan_distance_tuples(neighbor_pos, end_pos)
            neighbor_node = Node(position=neighbor_pos, parent=current_node, g=neighbor_g, h=neighbor_h)
            heapq.heappush(open_list, neighbor_node); open_list_nodes[neighbor_pos] = neighbor_node
    return None

# --- GameState Class (remains the same) ---
class GameState: # ... (GameState remains the same) ...
    def __init__(self, map_data_strings, npc_definitions):
        self.map_data = []
        self.npcs = []
        self.walkable_map_chars_for_roaming = GRASS_CHARS + FLOOR_CHARS + ['T']
        if DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES not in self.walkable_map_chars_for_roaming:
             self.walkable_map_chars_for_roaming.append(DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES)
        self.rest_spot_locations = []
        self.resource_locations = {"wood": [], "stone": []}
        self.water_tile_locations = []
        self.game_tick_counter = 0
        self.patrol_paths = {
            "route_gate_patrol": [ (1, 1), (1, 3), (1, 5), (1,7) ],
            "route_resource_patrol": [ (9, 1), (9, 4), (9,8), (9,11) ],
            "route_mid_cross": [ (3,8), (5,8), (5,10), (3,10) ]
        }
        npc_id_counter = 0
        processed_map_rows = []
        for r, row_str in enumerate(map_data_strings):
            current_row_chars = list(row_str)
            for c, char_val in enumerate(current_row_chars):
                chosen_char_for_map_data = char_val
                if char_val == ORIGINAL_GRASS_CHAR:
                    if random.random() < GRASS_VARIATION_PROBABILITY: chosen_char_for_map_data = random.choice(GRASS_CHARS[1:])
                    else: chosen_char_for_map_data = GRASS_CHARS[0]
                elif char_val == ORIGINAL_FLOOR_CHAR:
                    if random.random() < FLOOR_VARIATION_PROBABILITY: chosen_char_for_map_data = random.choice(FLOOR_CHARS[1:])
                    else: chosen_char_for_map_data = FLOOR_CHARS[0]
                current_row_chars[c] = chosen_char_for_map_data
                if char_val in npc_definitions:
                    npc_def = npc_definitions[char_val]
                    new_npc = Npc(id=npc_id_counter, y=r, x=c, char=char_val, color_pair_index=npc_def['color_pair_index'])
                    if char_val == '@' and "route_gate_patrol" in self.patrol_paths: new_npc.patrol_path_id = "route_gate_patrol"
                    elif char_val == '%' and "route_resource_patrol" in self.patrol_paths: new_npc.patrol_path_id = "route_resource_patrol"
                    elif char_val == '&' and "route_mid_cross" in self.patrol_paths: new_npc.patrol_path_id = "route_mid_cross"
                    self.npcs.append(new_npc)
                    npc_id_counter += 1
                    current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == REST_SPOT_CHAR:
                    self.rest_spot_locations.append((r,c)); current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == RESOURCE_WOOD_CHAR:
                    self.resource_locations["wood"].append((r,c)); current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == RESOURCE_STONE_CHAR:
                    self.resource_locations["stone"].append((r,c)); current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == WATER_CHAR_SOURCE:
                    self.water_tile_locations.append((r,c))
                    current_row_chars[c] = WATER_CHAR_SOURCE
            processed_map_rows.append("".join(current_row_chars))
        self.map_data = processed_map_rows

# --- Encounter Prompt Generation ---
def generate_encounter_prompt(npc_self, npc_other, game_state, previous_ai_mode_for_prompt): # ... (remains the same) ...
    energy_status = "high";
    if npc_self.energy < LOW_ENERGY_THRESHOLD: energy_status = "low"
    elif npc_self.energy < (NPC_MAX_ENERGY / 2): energy_status = "medium"
    inventory_summary = "nothing"
    if any(v > 0 for v in npc_self.inventory.values()):
        items = [f"{count} {item}" for item, count in npc_self.inventory.items() if count > 0]
        inventory_summary = ", ".join(items)
    activity_description = "behaving erratically"
    if previous_ai_mode_for_prompt == AI_MODE_ROAMING: activity_description = "randomly roaming"
    elif previous_ai_mode_for_prompt == AI_MODE_PATROLLING:
        patrol_id_to_report = npc_self.interrupted_patrol_path_id or npc_self.patrol_path_id
        activity_description = f"patrolling route {patrol_id_to_report or 'an unknown route'}"
    elif previous_ai_mode_for_prompt == AI_MODE_SEEKING_REST: activity_description = "seeking a place to rest"
    elif previous_ai_mode_for_prompt == AI_MODE_SEEKING_RESOURCE: activity_description = f"seeking to gather {npc_self.current_resource_target_type or 'resources'}"
    elif previous_ai_mode_for_prompt == AI_MODE_GATHERING_RESOURCE: activity_description = f"gathering {npc_self.current_resource_target_type or 'resources'}"
    prompt = f"You are NPC {npc_self.id} ('{npc_self.char}'), a villager with a '{npc_self.personality}' personality. "
    prompt += f"Your energy is currently {energy_status}. You are carrying {inventory_summary}. "
    prompt += f"You were just {activity_description} when you encountered NPC {npc_other.id} ('{npc_other.char}'), "
    prompt += f"who has a '{npc_other.personality}' personality.\n\n"
    prompt += "What is your immediate reaction? Choose ONE action from the following list:\n"
    prompt += "- [Talk] (Initiate a conversation)\n"; prompt += "- [Ignore] (Continue with your previous general intention if possible, or find something new to do)\n"
    prompt += "- [Flee] (Move away from the other NPC)\n"; prompt += "- [Threaten] (Issue a verbal threat)\n"
    if npc_self.inventory.get("wood", 0) > 0 or npc_self.inventory.get("stone", 0) > 0:
        prompt += "- [Offer_Gift] (Offer one of your items as a gift)\n"
    if energy_status == "low":
        prompt += "- [Ask_For_Help] (Plead for assistance due to your low energy)\n"
    prompt += f"\nYour chosen action (respond with only one phrase from the list above):"
    return prompt

# --- LLM Response Function ---
def get_llm_encounter_response(prompt_string, npc_id, current_game_tick): # ... (remains the same) ...
    global USE_MOCK_LLM, OLLAMA_DEFAULT_MODEL
    if USE_MOCK_LLM:
        action_index = (current_game_tick // (ENCOUNTER_DURATION_TICKS // 2) + npc_id) % len(VALID_ENCOUNTER_ACTIONS)
        chosen_action = VALID_ENCOUNTER_ACTIONS[action_index]
        return chosen_action
    else:
        try:
            from ollama_client import call_model as actual_ollama_call
            response = actual_ollama_call(prompt_string, model_name=OLLAMA_DEFAULT_MODEL)
            if isinstance(response, dict) and "response" in response: return response["response"].strip()
            return str(response).strip()
        except ImportError: print("ERROR: ollama_client could not be imported. Falling back to mock response."); return "[Ignore]"
        except Exception as e: print(f"ERROR: Real LLM call failed for NPC {npc_id}: {e}. Falling back to mock."); return "[Ignore]"

# --- Drawing Function ---
def draw_map(stdscr, game_state, color_pairs):
    for r, row_str in enumerate(game_state.map_data): # ... (base map drawing as before) ...
        for c, char_val in enumerate(row_str):
            color_pair_to_use = color_pairs.get('default', curses.color_pair(1))
            display_char = char_val
            if char_val in GRASS_CHARS: color_pair_to_use = color_pairs.get('grass', curses.color_pair(1))
            elif char_val in FLOOR_CHARS: color_pair_to_use = color_pairs.get('floor', curses.color_pair(1))
            elif char_val == '#': color_pair_to_use = color_pairs.get('wall', curses.color_pair(1))
            elif char_val == 'T': color_pair_to_use = color_pairs.get('target', curses.color_pair(1))
            elif char_val == WATER_CHAR_SOURCE: continue
            try: stdscr.addch(r, c, display_char, color_pair_to_use)
            except curses.error: pass
    num_frames = len(WATER_ANIMATION_CHARS); current_frame_index = (game_state.game_tick_counter // WATER_ANIMATION_SPEED) % num_frames
    char_to_draw_water = WATER_ANIMATION_CHARS[current_frame_index]; water_color = color_pairs.get('water_anim', curses.color_pair(1))
    for r_w, c_w in game_state.water_tile_locations: # ... (water drawing as before) ...
        try: stdscr.addch(r_w, c_w, char_to_draw_water, water_color)
        except curses.error: pass
    for r_y, r_x in game_state.rest_spot_locations: # ... (rest spot drawing as before) ...
        try: stdscr.addch(r_y, r_x, REST_SPOT_CHAR, color_pairs.get('rest_spot', curses.color_pair(1)))
        except curses.error: pass
    for r_y, r_x in game_state.resource_locations["wood"]: # ... (wood drawing as before) ...
        try: stdscr.addch(r_y, r_x, RESOURCE_WOOD_CHAR, color_pairs.get('wood_res', curses.color_pair(1)))
        except curses.error: pass
    for r_y, r_x in game_state.resource_locations["stone"]: # ... (stone drawing as before) ...
        try: stdscr.addch(r_y, r_x, RESOURCE_STONE_CHAR, color_pairs.get('stone_res', curses.color_pair(1)))
        except curses.error: pass
    for npc_to_viz_path in game_state.npcs: # ... (path drawing as before) ...
        if npc_to_viz_path.path and npc_to_viz_path.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE, AI_MODE_ENCOUNTER]:
            for r_path, c_path in npc_to_viz_path.path:
                if (r_path, c_path) != (npc_to_viz_path.y, npc_to_viz_path.x):
                    try: stdscr.addch(r_path, c_path, '.', color_pairs.get('path', curses.color_pair(1)))
                    except curses.error: pass
    for npc in game_state.npcs: # ... (NPC drawing as before) ...
        try: stdscr.addch(npc.y, npc.x, npc.char, curses.color_pair(npc.color_pair_index))
        except curses.error: pass

    # Enhanced Status Display (Verified and Updated)
    for i, npc_to_display in enumerate(game_state.npcs[:min(curses.LINES - len(game_state.map_data) - 1, 3)]):
        status_line_y_pos = len(game_state.map_data) + i
        if status_line_y_pos < curses.LINES -1 :
            target_info = "No Target"; _patrol_id_str = npc_to_display.patrol_path_id
            if npc_to_display.target_y is not None:
                target_info = f"T:({npc_to_display.target_y},{npc_to_display.target_x})"
                if npc_to_display.ai_mode == AI_MODE_SEEKING_RESOURCE and npc_to_display.current_resource_target_type: target_info += f" Res:{npc_to_display.current_resource_target_type[:3]}"
                elif npc_to_display.ai_mode == AI_MODE_PATROLLING and _patrol_id_str: target_info += f" Pat:{_patrol_id_str[:7]}"

            path_info = f"P:{len(npc_to_display.path)}"
            mode_info_str = npc_to_display.ai_mode
            pers_info = npc_to_display.personality[:4]

            if mode_info_str == AI_MODE_ROAMING: mode_info = "Roam"
            elif mode_info_str == AI_MODE_SEEKING_REST: mode_info = "SeekR"
            elif mode_info_str == AI_MODE_RESTING: mode_info = "Rest"
            elif mode_info_str == AI_MODE_SEEKING_RESOURCE: mode_info = "SeekRes"
            elif mode_info_str == AI_MODE_GATHERING_RESOURCE: mode_info = f"GathRes({npc_to_display.gathering_timer})"
            elif mode_info_str == AI_MODE_PATROLLING: mode_info = f"Patrol({npc_to_display.current_patrol_waypoint_index})"
            elif mode_info_str == AI_MODE_ENCOUNTER:
                action_str = npc_to_display.llm_parsed_action[:4] if npc_to_display.llm_parsed_action else "Wait"
                mode_info = f"Enc({action_str})[{npc_to_display.encounter_timer}]" # Updated display
            else: mode_info = mode_info_str[:7] # Fallback for other modes

            energy_info = f"E:{int(npc_to_display.energy)}"
            inv_info = f"Inv(W:{npc_to_display.inventory['wood']},S:{npc_to_display.inventory['stone']})"
            encounter_partner_info = f" EP:{npc_to_display.encounter_partner_id}" if npc_to_display.encounter_partner_id is not None and npc_to_display.ai_mode == AI_MODE_ENCOUNTER else ""

            status_msg = f"N{npc_to_display.id}({npc_to_display.char} {pers_info})@({npc_to_display.y},{npc_to_display.x}) {target_info} {path_info} {energy_info} {inv_info} {mode_info}{encounter_partner_info}"
            try:
                stdscr.move(status_line_y_pos, 0); stdscr.clrtoeol()
                stdscr.addstr(status_line_y_pos, 0, status_msg[:curses.COLS-1])
            except curses.error: pass

# --- Main Game Logic ---
loop_counter = 0
def main(stdscr):
    global loop_counter, USE_MOCK_LLM, OLLAMA_DEFAULT_MODEL
    curses.curs_set(0); curses.start_color()
    # ... (color_pairs and init_pair calls as before) ...
    color_pairs = {
        'default': curses.color_pair(1), 'grass': curses.color_pair(2), 'water_anim': curses.color_pair(3),
        'npc_yellow': curses.color_pair(4), 'wall': curses.color_pair(5), 'target': curses.color_pair(6),
        'npc_cyan': curses.color_pair(7), 'rest_spot': curses.color_pair(8), 'path': curses.color_pair(9),
        'floor': curses.color_pair(1), 'wood_res': curses.color_pair(10), 'stone_res': curses.color_pair(11),
        'npc_magenta': curses.color_pair(12)
    }
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK); curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK); curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE); curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_CYAN, curses.COLOR_BLACK); curses.init_pair(8, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(9, curses.COLOR_CYAN, curses.COLOR_BLACK); curses.init_pair(10, curses.COLOR_YELLOW, curses.COLOR_DKGRAY)
    curses.init_pair(11, curses.COLOR_WHITE, curses.COLOR_DKGRAY); curses.init_pair(12, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    initial_map_data_strings = [
        "####################", "#G@GRGWGS~GGGG~~GRT#", "#G#####%##&~~R####G#", "#G#GGGGGRGS~GGGG~#G#",
        "#G#G##~########G#G#", "#G#G#RGGGGWWS#G#G#G#", "#G#G#G#####G#G#G#G#", "#G#G#GGGGGGG#G#G#G#",
        "#G#GR####S##~##G#G#", "#GGGSGGGGGGWGG~GG#", "####################"
    ]
    npc_definitions_on_map = {'@': {'color_pair_index': 4}, '%': {'color_pair_index': 7}, '&': {'color_pair_index': 12} }
    if loop_counter == 0: print("--- Initial GameState Call (from main) ---")
    game_state = GameState(map_data_strings=initial_map_data_strings, npc_definitions=npc_definitions_on_map)
    astar_walkable_map_tiles = GRASS_CHARS + FLOOR_CHARS + ['T']
    if DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES not in astar_walkable_map_tiles:
        astar_walkable_map_tiles.append(DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES)
    all_walkable_coords_for_roaming = []
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            if char_val in game_state.walkable_map_chars_for_roaming: all_walkable_coords_for_roaming.append((r,c))
    stdscr.nodelay(True); NPC_MOVE_FREQUENCY = 3
    game_running_duration = 700
    if loop_counter == 0:
        for npc_init_log in game_state.npcs: print(f"Initial: NPC {npc_init_log.id} ('{npc_init_log.char}') at ({npc_init_log.y},{npc_init_log.x}), E:{npc_init_log.energy}, Mode:{npc_init_log.ai_mode}, Pers:{npc_init_log.personality}, Patrol:{npc_init_log.patrol_path_id}, Inv:{npc_init_log.inventory}, PerceptR:{npc_init_log.perception_range}")
        print(f"--- Starting Main Loop (USE_MOCK_LLM={USE_MOCK_LLM}) ---")

    while True:
        stdscr.clear(); loop_counter += 1; game_state.game_tick_counter +=1

        for npc_obj in game_state.npcs: npc_obj.detected_encounter_partner_id_this_tick = None
        processed_encounter_pairs_this_tick = set()
        if len(game_state.npcs) >= 2:
            for i in range(len(game_state.npcs)):
                npc_a = game_state.npcs[i]
                if npc_a.ai_mode in [AI_MODE_ENCOUNTER, AI_MODE_RESTING]: continue
                for j in range(i + 1, len(game_state.npcs)):
                    npc_b = game_state.npcs[j]
                    if npc_b.ai_mode in [AI_MODE_ENCOUNTER, AI_MODE_RESTING]: continue
                    pair_key = tuple(sorted((npc_a.id, npc_b.id)))
                    if pair_key in processed_encounter_pairs_this_tick: continue
                    dist = manhattan_distance_coords(npc_a.y, npc_a.x, npc_b.y, npc_b.x)
                    if dist <= npc_a.perception_range and dist <= npc_b.perception_range:
                        npc_a.detected_encounter_partner_id_this_tick = npc_b.id
                        npc_b.detected_encounter_partner_id_this_tick = npc_a.id
                        processed_encounter_pairs_this_tick.add(pair_key)

        for npc in game_state.npcs:
            current_npc_log_prefix = f"N{npc.id}({npc.char} E:{int(npc.energy)} M:{npc.ai_mode[:7]})"
            npc_is_effectively_idle = (npc.target_y is None and not npc.path)
            if npc.ai_mode != AI_MODE_RESTING and npc.energy > 0 : npc.energy = max(0, npc.energy - ENERGY_DEPLETION_RATE)

            # --- AI Mode Logic ---
            if npc.ai_mode == AI_MODE_ENCOUNTER:
                # LLM Response Parsing & Placeholder Action (if response just received)
                if npc.llm_raw_response:
                    parsed_action = npc.llm_raw_response.strip()
                    if parsed_action not in VALID_ENCOUNTER_ACTIONS:
                        print(f"LOG: {current_npc_log_prefix} LLM response '{parsed_action}' invalid. Defaulting to [Ignore].")
                        parsed_action = "[Ignore]"
                    npc.llm_parsed_action = parsed_action
                    print(f"LOG: {current_npc_log_prefix} Parsed LLM Action: {npc.llm_parsed_action}")
                    npc.llm_raw_response = None # Clear after parsing

                    # Implement placeholder actions
                    if npc.llm_parsed_action == "[Talk]":
                        print(f"LOG: {current_npc_log_prefix} action: [Talk] with {npc.encounter_partner_id}. Timer set to {ENCOUNTER_DURATION_TICKS}.")
                        npc.encounter_timer = ENCOUNTER_DURATION_TICKS
                    elif npc.llm_parsed_action == "[Ignore]":
                        print(f"LOG: {current_npc_log_prefix} action: [Ignore] {npc.encounter_partner_id}. Timer set to 0.")
                        npc.encounter_timer = 0
                    elif npc.llm_parsed_action == "[Flee]":
                        other_npc = next((n for n in game_state.npcs if n.id == npc.encounter_partner_id), None)
                        flee_target_y, flee_target_x = npc.y, npc.x
                        if other_npc:
                            if other_npc.y < npc.y: flee_target_y = min(len(game_state.map_data) - 1, npc.y + 3)
                            else: flee_target_y = max(0, npc.y - 3)
                            if other_npc.x < npc.x: flee_target_x = min(len(game_state.map_data[0]) - 1, npc.x + 3)
                            else: flee_target_x = max(0, npc.x - 3)
                        print(f"LOG: {current_npc_log_prefix} action: [Flee] from {npc.encounter_partner_id}. Target: ({flee_target_y},{flee_target_x}). Timer set to 0.")
                        npc.target_y, npc.target_x = flee_target_y, flee_target_x ; npc.path = []
                        npc.encounter_timer = 0; npc.ai_mode = AI_MODE_ROAMING; npc.encounter_partner_id = None
                    elif npc.llm_parsed_action == "[Threaten]":
                        print(f"LOG: {current_npc_log_prefix} action: [Threaten] {npc.encounter_partner_id}. Timer set to {ENCOUNTER_DURATION_TICKS // 2}.")
                        npc.encounter_timer = max(1, ENCOUNTER_DURATION_TICKS // 2)
                    elif npc.llm_parsed_action == "[Offer_Gift]":
                        item_offered = "nothing"
                        if npc.inventory["wood"] > 0: item_offered = "wood"
                        elif npc.inventory["stone"] > 0: item_offered = "stone"
                        print(f"LOG: {current_npc_log_prefix} action: [Offer_Gift] ({item_offered}) to {npc.encounter_partner_id}. Timer set to {ENCOUNTER_DURATION_TICKS}.")
                        npc.encounter_timer = ENCOUNTER_DURATION_TICKS
                    elif npc.llm_parsed_action == "[Ask_For_Help]":
                        print(f"LOG: {current_npc_log_prefix} action: [Ask_For_Help] from {npc.encounter_partner_id}. Timer set to {ENCOUNTER_DURATION_TICKS}.")
                        npc.encounter_timer = ENCOUNTER_DURATION_TICKS

                # Standard timer decrement and exit logic
                if npc.encounter_timer > 0: npc.encounter_timer -= 1
                else:
                    prev_partner = npc.encounter_partner_id
                    npc.encounter_partner_id = None ; npc.target_y, npc.target_x, npc.path = None, None, []
                    npc.previous_ai_mode = None; npc.llm_parsed_action = None # Clear parsed action on exit
                    log_msg_suffix = f"after enc with {prev_partner}."
                    if npc.interrupted_patrol_path_id is not None:
                        npc.ai_mode = AI_MODE_PATROLLING; npc.patrol_path_id = npc.interrupted_patrol_path_id; npc.current_patrol_waypoint_index = npc.interrupted_waypoint_index; npc.interrupted_patrol_path_id, npc.interrupted_waypoint_index = None,0; print(f"{current_npc_log_prefix} resuming PATROL {log_msg_suffix}")
                    elif npc.patrol_path_id: npc.ai_mode = AI_MODE_PATROLLING; print(f"{current_npc_log_prefix} starting PATROL {log_msg_suffix}")
                    else: npc.ai_mode = AI_MODE_ROAMING; print(f"{current_npc_log_prefix} now ROAMING {log_msg_suffix}")
                if npc.ai_mode == AI_MODE_ENCOUNTER and npc.encounter_timer > 0: continue
            elif npc.ai_mode == AI_MODE_RESTING: # ... (Resting logic) ...
                npc.energy = min(NPC_MAX_ENERGY, npc.energy + ENERGY_REPLENISH_RATE)
                if npc.energy >= NPC_MAX_ENERGY:
                    npc.target_y,npc.target_x,npc.path = None,None,[]; npc.previous_ai_mode = None
                    if npc.interrupted_patrol_path_id: npc.ai_mode = AI_MODE_PATROLLING; npc.patrol_path_id = npc.interrupted_patrol_path_id; npc.current_patrol_waypoint_index = npc.interrupted_waypoint_index; npc.interrupted_patrol_path_id, npc.interrupted_waypoint_index = None,0;
                    elif npc.patrol_path_id: npc.ai_mode = AI_MODE_PATROLLING;
                    else: npc.ai_mode = AI_MODE_ROAMING;
                continue
            elif npc.detected_encounter_partner_id_this_tick is not None: # New Encounter Initiation
                interruptible_modes = [AI_MODE_ROAMING, AI_MODE_PATROLLING, AI_MODE_SEEKING_RESOURCE, AI_MODE_SEEKING_REST]
                if npc.ai_mode in interruptible_modes:
                    npc.previous_ai_mode = npc.ai_mode
                    if npc.ai_mode == AI_MODE_PATROLLING and npc.patrol_path_id is not None: npc.interrupted_patrol_path_id = npc.patrol_path_id; npc.interrupted_waypoint_index = npc.current_patrol_waypoint_index;
                    npc.target_y,npc.target_x,npc.path = None,None,[]; npc.ai_mode = AI_MODE_ENCOUNTER; npc.encounter_partner_id = npc.detected_encounter_partner_id_this_tick; npc.encounter_timer = ENCOUNTER_DURATION_TICKS
                    other_npc_obj = next((n for n in game_state.npcs if n.id == npc.encounter_partner_id), None)
                    if other_npc_obj:
                        prompt = generate_encounter_prompt(npc, other_npc_obj, game_state, npc.previous_ai_mode)
                        npc.llm_raw_response = get_llm_encounter_response(prompt, npc.id, game_state.game_tick_counter) # LLM call happens here
                        print(f"{current_npc_log_prefix} entered ENCOUNTER with {npc.encounter_partner_id}. PrevM: {npc.previous_ai_mode}. LLM_Raw: '{npc.llm_raw_response}'")
                    if npc.ai_mode == AI_MODE_ENCOUNTER : continue
            elif npc.energy < LOW_ENERGY_THRESHOLD and npc.ai_mode != AI_MODE_SEEKING_REST : # Low Energy Check
                npc.previous_ai_mode = npc.ai_mode
                if npc.ai_mode == AI_MODE_PATROLLING and npc.patrol_path_id: npc.interrupted_patrol_path_id = npc.patrol_path_id; npc.interrupted_waypoint_index = npc.current_patrol_waypoint_index; npc.patrol_path_id = None
                npc.ai_mode = AI_MODE_SEEKING_REST; npc.target_y,npc.target_x,npc.path = None,None,[]; npc.current_resource_target_type = None; npc.gathering_timer = 0; # print(f"{current_npc_log_prefix} low E (PrevM:{npc.previous_ai_mode}), now SEEKING_REST.")
            # ... (Other AI states: SEEKING_REST, PATROLLING, GATHERING_RESOURCE, SEEKING_RESOURCE, ROAMING as before, ensure logs are not too verbose) ...
            elif npc.ai_mode == AI_MODE_SEEKING_REST:
                if npc_is_effectively_idle: best_target_spot, shortest_path_len = None, float('inf')
                    if not game_state.rest_spot_locations: npc.ai_mode = AI_MODE_ROAMING
                    else:
                        for spot_y, spot_x in game_state.rest_spot_locations:
                            if (npc.y, npc.x) == (spot_y, spot_x): best_target_spot=(spot_y,spot_x);npc.path=[];shortest_path_len=0;break
                            path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (spot_y, spot_x), astar_walkable_map_tiles)
                            if path and len(path) < shortest_path_len: shortest_path_len = len(path); best_target_spot = (spot_y, spot_x)
                        if best_target_spot: npc.target_y, npc.target_x = best_target_spot
                            if (npc.y, npc.x) == best_target_spot: npc.ai_mode = AI_MODE_RESTING; npc.path = []
                        else: npc.ai_mode = AI_MODE_ROAMING
            elif npc.ai_mode == AI_MODE_PATROLLING:
                if npc.patrol_path_id and (npc_is_effectively_idle or (npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x))):
                    route = game_state.patrol_paths.get(npc.patrol_path_id)
                    if route:
                        if npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x): npc.current_patrol_waypoint_index = (npc.current_patrol_waypoint_index + 1) % len(route);
                        npc.target_y, npc.target_x = route[npc.current_patrol_waypoint_index]; npc.path = []
                    else: npc.ai_mode = AI_MODE_ROAMING; npc.patrol_path_id = None
            elif npc.ai_mode == AI_MODE_GATHERING_RESOURCE:
                npc.gathering_timer -= 1
                if npc.gathering_timer <= 0: res_type = npc.current_resource_target_type
                    if res_type in npc.inventory: npc.inventory[res_type] += GATHER_AMOUNT
                    npc.ai_mode = AI_MODE_ROAMING; npc.target_y,npc.target_x,npc.path = None,None,[]; npc.current_resource_target_type = None
            elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE:
                if npc_is_effectively_idle:
                    resource_locations_of_type = game_state.resource_locations.get(npc.current_resource_target_type, [])
                    best_target_resource_spot, shortest_path_len = None, float('inf')
                    if not resource_locations_of_type: npc.ai_mode = AI_MODE_ROAMING; npc.current_resource_target_type = None
                    else:
                        for spot_y, spot_x in resource_locations_of_type:
                            path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (spot_y, spot_x), astar_walkable_map_tiles)
                            if path and len(path) < shortest_path_len: shortest_path_len = len(path); best_target_resource_spot = (spot_y, spot_x)
                        if best_target_resource_spot: npc.target_y, npc.target_x = best_target_resource_spot
                        else: npc.ai_mode = AI_MODE_ROAMING; npc.current_resource_target_type = None
            elif npc.ai_mode == AI_MODE_ROAMING:
                if npc_is_effectively_idle:
                    if npc.patrol_path_id: npc.ai_mode = AI_MODE_PATROLLING
                    elif random.random() < CHANCE_TO_SEEK_RESOURCE and any(game_state.resource_locations.get(res_type) for res_type in RESOURCE_TYPES):
                        chosen_res_type = random.choice(list(filter(lambda rt: game_state.resource_locations.get(rt), RESOURCE_TYPES)))
                        if chosen_res_type: npc.ai_mode = AI_MODE_SEEKING_RESOURCE; npc.current_resource_target_type = chosen_res_type; npc.target_y,npc.target_x,npc.path = None,None,[]
                    elif all_walkable_coords_for_roaming:
                        pc = [crd for crd in all_walkable_coords_for_roaming if crd != (npc.y, npc.x)];
                        if not pc: pc = all_walkable_coords_for_roaming
                        if pc: npc.target_y, npc.target_x = random.choice(pc)

            if npc.target_y is not None and not npc.path and npc.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE, AI_MODE_ENCOUNTER]:
                calculated_path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (npc.target_y, npc.target_x), astar_walkable_map_tiles)
                if calculated_path: npc.path = calculated_path;
                    if npc.path and npc.path[0] == (npc.y, npc.x): npc.path.pop(0)
                else:
                    npc.target_y, npc.target_x = None, None
                    if npc.ai_mode == AI_MODE_SEEKING_REST: pass
                    elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE: npc.current_resource_target_type = None; npc.ai_mode = AI_MODE_ROAMING
                    elif npc.ai_mode == AI_MODE_PATROLLING:
                        if npc.patrol_path_id and game_state.patrol_paths.get(npc.patrol_path_id) and game_state.patrol_paths[npc.patrol_path_id]: npc.current_patrol_waypoint_index = (npc.current_patrol_waypoint_index + 1) % len(game_state.patrol_paths[npc.patrol_path_id]) ;
                        else: npc.ai_mode = AI_MODE_ROAMING; npc.patrol_path_id = None
                    else: npc.ai_mode = AI_MODE_ROAMING
            if loop_counter % NPC_MOVE_FREQUENCY == 0:
                if npc.path and npc.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE, AI_MODE_ENCOUNTER]:
                    next_y, next_x = npc.path.pop(0)
                    is_next_step_occupied = any(o.id != npc.id and o.y == next_y and o.x == next_x for o in game_state.npcs)
                    if not is_next_step_occupied: npc.y, npc.x = next_y, next_x
                    else: npc.path.insert(0, (next_y, next_x))
                    if npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x):
                        previous_ai_mode_for_arrival = npc.ai_mode
                        if npc.ai_mode == AI_MODE_SEEKING_REST and (npc.y,npc.x) in game_state.rest_spot_locations: npc.ai_mode = AI_MODE_RESTING; npc.path=[]
                        elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE: npc.ai_mode = AI_MODE_GATHERING_RESOURCE; npc.gathering_timer = GATHER_TIME_TICKS; npc.path=[]
                        elif npc.ai_mode == AI_MODE_PATROLLING: pass
                        else: npc.ai_mode = AI_MODE_ROAMING
                        if previous_ai_mode_for_arrival != AI_MODE_PATROLLING : npc.target_y, npc.target_x, npc.path = None, None, []
                        elif npc.ai_mode == AI_MODE_PATROLLING : npc.path = []
                    elif not npc.path and npc.target_y is not None: npc.target_y, npc.target_x = None, None

        draw_map(stdscr, game_state, color_pairs)
        stdscr.refresh()
        curses.napms(100)
        if game_running_duration and loop_counter > game_running_duration : print(f"Test duration ({game_running_duration} ticks) reached."); break
        key = stdscr.getch()
        if key != curses.ERR and (key == ord('q') or key == curses.ascii.ESC): break
if __name__ == "__main__":
    try: curses.wrapper(main)
    except Exception as e: print(f"ERR: {e}"); traceback.print_exc()
    finally:
        try: curses.endwin()
        except: pass
        print("Game ended."); sys.stdout.flush(); sys.stderr.flush()
