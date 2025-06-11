import curses
import curses.ascii # For checking 'q'
import heapq
import collections
import random
import time
import requests
import sys # Added for sys.stdout.flush()
import traceback # Added for traceback.print_exc()

# Attempt to import config, use defaults if not found or specific values missing
try:
    import config
    USE_MOCK_LLM = getattr(config, 'USE_MOCK_LLM', True)
    OLLAMA_DEFAULT_MODEL = getattr(config, 'OLLAMA_DEFAULT_MODEL', "gemma:2b")
except ImportError:
    USE_MOCK_LLM = True
    OLLAMA_DEFAULT_MODEL = "gemma:2b"

ollama_client_available = False
actual_ollama_call = None
if not USE_MOCK_LLM:
    try:
        from ollama_client import call_model
        actual_ollama_call = call_model
        ollama_client_available = True
    except ImportError:
        USE_MOCK_LLM = True
else:
    pass

# --- Constants ---
# NPC Attributes
NPC_INITIAL_ENERGY_MIN = 80
NPC_INITIAL_ENERGY_MAX = 100
NPC_MAX_ENERGY = 100
ENERGY_DEPLETION_RATE = 0.05
ENERGY_REPLENISH_RATE = 1.0
LOW_ENERGY_THRESHOLD = 25
DEFAULT_NPC_PERCEPTION_RANGE = 5
NPC_POSSIBLE_PERSONALITIES = ["friendly", "neutral", "gruff", "timid", "suspicious"]

# Map Characters
REST_SPOT_CHAR = 'R'
RESOURCE_WOOD_CHAR = 'W'
RESOURCE_STONE_CHAR = 'S'
WATER_CHAR_SOURCE = '~'
ORIGINAL_GRASS_CHAR = 'G'
ORIGINAL_FLOOR_CHAR = ' '
DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES = ' ' # Character to replace features like NPCs, resources on map_data

# Map Visuals
WATER_ANIMATION_CHARS = ['~', '≈', '≋']
WATER_ANIMATION_SPEED = 20 # Lower is faster
GRASS_CHARS = [ORIGINAL_GRASS_CHAR, '.', ',', '`']
GRASS_VARIATION_PROBABILITY = 0.15
FLOOR_CHARS = [ORIGINAL_FLOOR_CHAR, '·']
FLOOR_VARIATION_PROBABILITY = 0.05

# Resource Gathering
GATHER_AMOUNT = 1
RESOURCE_TYPES = ["wood", "stone"]
GATHER_TIME_TICKS = 5 # How long it takes to gather a resource
CHANCE_TO_SEEK_RESOURCE = 0.1

# Encounter & Dialogue
ENCOUNTER_DURATION_TICKS = 30
MAX_DIALOGUE_EXCHANGES = 2 # Max exchanges per NPC in a single dialogue
VALID_ENCOUNTER_ACTIONS = ["[Talk]", "[Ignore]", "[Flee]", "[Threaten]", "[Offer_Gift]", "[Ask_For_Help]"]

# AI Modes
AI_MODE_ROAMING = "roaming"
AI_MODE_SEEKING_REST = "seeking_rest"
AI_MODE_RESTING = "resting"
AI_MODE_SEEKING_RESOURCE = "seeking_resource"
AI_MODE_GATHERING_RESOURCE = "gathering_resource"
AI_MODE_PATROLLING = "patrolling"
AI_MODE_ENCOUNTER = "encounter"
ENCOUNTER_SUBMODE_TALKING = "talking" # Sub-mode for AI_MODE_ENCOUNTER

# Relationship Scores
RELATIONSHIP_SCORE_MAX = 10
RELATIONSHIP_SCORE_MIN = -10
RELATIONSHIP_SCORE_NEUTRAL = 0
DEFAULT_RELATIONSHIP_SCORE_CHANGE_POSITIVE = 1
DEFAULT_RELATIONSHIP_SCORE_CHANGE_NEGATIVE = -1
STRONG_RELATIONSHIP_SCORE_CHANGE_POSITIVE = 3
STRONG_RELATIONSHIP_SCORE_CHANGE_NEGATIVE = -3

# Interaction Type Constants (used for logging and context)
INTERACTION_TYPE_I_TALKED_TO_THEM = "I_TALKED_TO_THEM"
INTERACTION_TYPE_TALKED_TO_BY_ME = "TALKED_TO_BY_ME"
# ... (other interaction types will be reviewed and potentially moved/grouped)

# --- Relationship Descriptor Helper ---
def get_relationship_descriptor(score: int) -> str:
    """Returns a string descriptor for a given relationship score."""
    # Defines thresholds for relationship descriptors.
    # Example: score <= -7 is "very negative", -6 to -3 is "negative", etc.
    if score <= RELATIONSHIP_SCORE_MIN + 3:
        return "very negative"
    elif score <= -3:
        return "negative"
    elif score < 0:
        return "slightly negative"
    elif score == 0:
        return "neutral"
    elif score < 3:
        return "slightly positive"
    elif score < RELATIONSHIP_SCORE_MAX - 2:
        return "positive"
    else: # score >= RELATIONSHIP_SCORE_MAX - 2
        return "very positive"

# Further Interaction Type Constants
INTERACTION_TYPE_DIALOGUE_EXCHANGE = "DIALOGUE_EXCHANGE"
INTERACTION_TYPE_IGNORED_ME = "IGNORED_ME"
INTERACTION_TYPE_I_IGNORED_THEM = "I_IGNORED_THEM"
INTERACTION_TYPE_THREATENED_ME = "THREATENED_ME"
INTERACTION_TYPE_I_THREATENED_THEM = "I_THREATENED_THEM"
INTERACTION_TYPE_FLED_FROM_ME = "FLED_FROM_ME"
INTERACTION_TYPE_I_FLED_FROM_THEM = "I_FLED_FROM_THEM"
INTERACTION_TYPE_OFFERED_GIFT_TO_ME = "OFFERED_GIFT_TO_ME"
INTERACTION_TYPE_I_OFFERED_GIFT_TO_THEM = "I_OFFERED_GIFT_TO_THEM"
INTERACTION_TYPE_ASKED_FOR_HELP_FROM_ME = "ASKED_FOR_HELP_FROM_ME"
INTERACTION_TYPE_I_ASKED_FOR_HELP_FROM_THEM = "I_ASKED_FOR_HELP_FROM_THEM"

# --- NPC Data Structure ---
class Npc:
    """
    Represents a Non-Player Character in the game.
    Manages NPC state including position, energy, AI mode, inventory, relationships, etc.
    """
    def __init__(self, npc_id: int, y: int, x: int, char: str, color_pair_index: int):
        """
        Initializes an NPC.

        Args:
            npc_id: Unique identifier for the NPC.
            y: Initial Y-coordinate.
            x: Initial X-coordinate.
            char: Character representing the NPC on the map.
            color_pair_index: Curses color pair index for the NPC.
        """
        self.id = npc_id
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

        self.inventory = {"wood": 0, "stone": 0} # Example: {"item_name": count}
        self.current_resource_target_type = None
        self.gathering_timer = 0

        self.patrol_path_id = None # ID of the patrol path from GameState.patrol_paths
        self.current_patrol_waypoint_index = 0
        self.interrupted_patrol_path_id = None # To resume patrol after interruption
        self.interrupted_waypoint_index = 0

        self.perception_range = DEFAULT_NPC_PERCEPTION_RANGE
        self.detected_encounter_partner_id_this_tick = None # Temp storage for detected NPC ID
        self.encounter_partner_id = None # ID of NPC currently in encounter with
        self.encounter_timer = 0 # Ticks remaining in current encounter interaction

        self.personality = random.choice(NPC_POSSIBLE_PERSONALITIES)
        self.relationships = {} # Key: target_npc_id, Value: dict of relationship data

        # LLM related attributes
        self.previous_ai_mode = None # Store AI mode before starting an encounter
        self.llm_raw_response = None # Raw text from LLM
        self.llm_parsed_action = None # Parsed action like "[Talk]" from LLM response

        # Dialogue specific attributes
        self.encounter_submode = None # e.g., ENCOUNTER_SUBMODE_TALKING
        self.dialogue_turn_taker_id = None # Whose turn it is to speak in a dialogue
        self.dialogue_history = [] # List of dicts: {'speaker_id': id, 'line': text}
        self.dialogue_exchange_count = 0 # Number of back-and-forths in current dialogue

    def reset_encounter_state(self):
        """Resets NPC attributes related to encounters and dialogue."""
        self.target_y, self.target_x, self.path = None, None, []
        self.encounter_partner_id = None
        # self.previous_ai_mode is preserved to be restored by the main loop
        self.llm_parsed_action = None
        self.llm_raw_response = None
        self.encounter_submode = None
        self.dialogue_history = []
        self.dialogue_exchange_count = 0
        self.dialogue_turn_taker_id = None
        self.encounter_timer = 0 # Explicitly set timer to 0 to signify end of encounter activities

    def get_or_initialize_relationship(self, target_npc_id: int) -> dict:
        """
        Retrieves or initializes relationship data for a target NPC.
        Ensures 'interaction_count' and 'last_interaction_type' keys exist.

        Args:
            target_npc_id: The ID of the other NPC.

        Returns:
            A dictionary containing relationship data.
        """
        if target_npc_id not in self.relationships:
            self.relationships[target_npc_id] = {
                'score': RELATIONSHIP_SCORE_NEUTRAL,
                'last_interaction_type': None,
                'interaction_count': 0
            }
        # Ensure essential keys are present for older save formats or unforeseen states
        self.relationships[target_npc_id].setdefault('interaction_count', 0)
        self.relationships[target_npc_id].setdefault('last_interaction_type', None)
        return self.relationships[target_npc_id]

    def update_relationship_towards(self, target_npc_id: int, score_change: int, interaction_type_string: str):
        """
        Updates the relationship score and interaction history with another NPC.

        Args:
            target_npc_id: The ID of the other NPC.
            score_change: The amount to change the relationship score by.
            interaction_type_string: A string describing the type of interaction.
        """
        rel = self.get_or_initialize_relationship(target_npc_id)
        old_score = rel['score']

        new_score = old_score + score_change
        rel['score'] = max(RELATIONSHIP_SCORE_MIN, min(RELATIONSHIP_SCORE_MAX, new_score))

        rel['last_interaction_type'] = interaction_type_string
        rel['interaction_count'] += 1

        # Consider replacing with a logging system if too verbose for production
        print(f"LOG_REL: NPC {self.id} -> NPC {target_npc_id}: Score {old_score}({'+' if score_change >=0 else ''}{score_change})->{rel['score']}, LastInt: '{rel['last_interaction_type']}', Count: {rel['interaction_count']}")

# --- Pathfinding ---
class Node:
    """A node class for A* Pathfinding."""
    def __init__(self, position: tuple[int, int], parent=None, g: int = 0, h: int = 0):
        """
        Initializes a Node.

        Args:
            position: (y, x) coordinates of the node.
            parent: Parent node in the path.
            g: Cost from start to current node.
            h: Heuristic cost from current node to end.
        """
        self.position = position
        self.parent = parent
        self.g = g  # Cost from start to this node
        self.h = h  # Heuristic cost from this node to end
        self.f = g + h  # Total estimated cost

    def __eq__(self, other):
        return self.position == other.position

    def __lt__(self, other):
        # For heapq comparison: prioritize lower f-cost, then lower h-cost (tie-breaker)
        if self.f == other.f:
            return self.h < other.h
        return self.f < other.f

    def __hash__(self):
        return hash(self.position)

def manhattan_distance_coords(y1: int, x1: int, y2: int, x2: int) -> int:
    """Calculates Manhattan distance between two points given their coordinates."""
    return abs(y1 - y2) + abs(x1 - x2)

def manhattan_distance_tuples(pos1: tuple[int, int], pos2: tuple[int, int]) -> int:
    """Calculates Manhattan distance between two points given as tuples."""
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

def reconstruct_path(current_node: Node) -> list[tuple[int, int]]:
    """Reconstructs the path from the end node back to the start."""
    path = []
    while current_node:
        path.append(current_node.position)
        current_node = current_node.parent
    return path[::-1] # Return reversed path (start to end)

# Pre-calculate default walkable tiles for A* to avoid re-computation
DEFAULT_ASTAR_WALKABLE_TILES = GRASS_CHARS + FLOOR_CHARS + ['T']
if DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES not in DEFAULT_ASTAR_WALKABLE_TILES:
    DEFAULT_ASTAR_WALKABLE_TILES.append(DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES)

def astar_pathfind(map_data: list[str], start_pos: tuple[int, int], end_pos: tuple[int, int],
                   walkable_tiles_map_chars: list[str] = None) -> list[tuple[int, int]] | None:
    """
    Finds a path from start_pos to end_pos using the A* algorithm.

    Args:
        map_data: A list of strings representing the map.
        start_pos: (y, x) tuple for the start position.
        end_pos: (y, x) tuple for the end position.
        walkable_tiles_map_chars: A list of characters considered walkable.
                                  Defaults to pre-calculated common walkable tiles.

    Returns:
        A list of (y, x) tuples representing the path from start to end,
        or None if no path is found.
    """
    if walkable_tiles_map_chars is None:
        walkable_tiles_map_chars = DEFAULT_ASTAR_WALKABLE_TILES

    map_height = len(map_data)
    map_width = len(map_data[0])

    start_node = Node(position=start_pos, g=0, h=manhattan_distance_tuples(start_pos, end_pos))
    end_node = Node(position=end_pos) # Only used for comparing positions

    open_list_heap = [start_node]  # Min-heap of nodes to visit
    # Using a dictionary for faster lookups and updates of nodes in the open_list_heap
    open_list_nodes = {start_node.position: start_node}

    # Using a dictionary to store the g-cost of visited nodes (closed list)
    # This helps avoid reprocessing nodes that have already been visited with a shorter or equal path.
    closed_list_g_costs = {}

    while open_list_heap:
        current_node = heapq.heappop(open_list_heap)

        # If this node's position is no longer in open_list_nodes, or if a better path
        # to this node was found and this instance is outdated, skip it.
        if current_node.position not in open_list_nodes or \
           open_list_nodes[current_node.position].f < current_node.f:
            continue

        del open_list_nodes[current_node.position] # Remove from active consideration

        if current_node.position == end_node.position:
            return reconstruct_path(current_node)

        closed_list_g_costs[current_node.position] = current_node.g

        # Explore neighbors (Up, Down, Left, Right)
        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor_pos = (current_node.position[0] + dy, current_node.position[1] + dx)

            # Boundary checks
            if not (0 <= neighbor_pos[0] < map_height and 0 <= neighbor_pos[1] < map_width):
                continue

            # Walkable check
            if map_data[neighbor_pos[0]][neighbor_pos[1]] not in walkable_tiles_map_chars:
                continue

            neighbor_g = current_node.g + 1

            # If neighbor is in closed list and we've found a path to it that's not better, skip
            if neighbor_pos in closed_list_g_costs and closed_list_g_costs[neighbor_pos] <= neighbor_g:
                continue

            # If neighbor is in open list but this new path isn't better, skip
            if neighbor_pos in open_list_nodes and open_list_nodes[neighbor_pos].g <= neighbor_g:
                continue

            neighbor_h = manhattan_distance_tuples(neighbor_pos, end_pos)
            neighbor_node = Node(position=neighbor_pos, parent=current_node, g=neighbor_g, h=neighbor_h)

            heapq.heappush(open_list_heap, neighbor_node)
            open_list_nodes[neighbor_pos] = neighbor_node

    return None # No path found

# --- Game State ---
class GameState:
    """
    Manages the overall state of the game, including the map, NPCs, and game objects.
    """
    def __init__(self, map_data_strings: list[str], npc_definitions: dict):
        """
        Initializes the game state.

        Args:
            map_data_strings: A list of strings representing the initial map layout.
            npc_definitions: A dictionary defining NPC types and their properties,
                             keyed by the character on the map. Example:
                             {'@': {'color_pair_index': 4, 'patrol_route_id': "route_gate_patrol"}}
        """
        self.map_data: list[str] = [] # The processed map where NPCs and items are replaced by floor/grass
        self.npcs: list[Npc] = []

        # Define walkable characters for NPCs when roaming or pathfinding generically
        self.walkable_map_chars_for_roaming = list(set(GRASS_CHARS + FLOOR_CHARS + ['T'] + [DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES]))


        self.rest_spot_locations: list[tuple[int, int]] = [] # List of (y,x) tuples
        self.resource_locations: dict[str, list[tuple[int, int]]] = {res_type: [] for res_type in RESOURCE_TYPES}
        self.water_tile_locations: list[tuple[int, int]] = [] # For animation

        self.game_tick_counter: int = 0

        # Predefined patrol paths for NPCs
        self.patrol_paths: dict[str, list[tuple[int, int]]] = {
            "route_gate_patrol": [(1, 1), (1, 3), (1, 5), (1, 7)],
            "route_resource_patrol": [(9, 1), (9, 4), (9, 8), (9, 11)],
            "route_mid_cross": [(3, 8), (5, 8), (5, 10), (3, 10)]
        }

        self._initialize_map_and_entities(map_data_strings, npc_definitions)

    def _initialize_map_and_entities(self, map_data_strings: list[str], npc_definitions: dict):
        """Processes the raw map strings to populate map_data, NPCs, and other entities."""
        npc_id_counter = 0
        processed_map_rows = []

        for r, row_str in enumerate(map_data_strings):
            current_row_chars = list(row_str)
            for c, char_val in enumerate(current_row_chars):
                # Handle terrain variation (grass, floor)
                final_map_char = char_val
                if char_val == ORIGINAL_GRASS_CHAR:
                    if random.random() < GRASS_VARIATION_PROBABILITY:
                        final_map_char = random.choice([gc for gc in GRASS_CHARS if gc != ORIGINAL_GRASS_CHAR])
                    else:
                        final_map_char = ORIGINAL_GRASS_CHAR
                elif char_val == ORIGINAL_FLOOR_CHAR:
                    if random.random() < FLOOR_VARIATION_PROBABILITY:
                        final_map_char = random.choice([fc for fc in FLOOR_CHARS if fc != ORIGINAL_FLOOR_CHAR])
                    else:
                        final_map_char = ORIGINAL_FLOOR_CHAR

                current_row_chars[c] = final_map_char # Store the potentially varied char

                # Handle entities
                if char_val in npc_definitions:
                    npc_def = npc_definitions[char_val]
                    new_npc = Npc(npc_id=npc_id_counter, y=r, x=c, char=char_val,
                                  color_pair_index=npc_def['color_pair_index'])

                    # Assign patrol path if defined for this NPC type (e.g. based on its map char)
                    # This could be made more robust, e.g. by npc_def containing a 'patrol_path_id' key
                    if char_val == '@' and "route_gate_patrol" in self.patrol_paths:
                        new_npc.patrol_path_id = "route_gate_patrol"
                    elif char_val == '%' and "route_resource_patrol" in self.patrol_paths:
                        new_npc.patrol_path_id = "route_resource_patrol"
                    elif char_val == '&' and "route_mid_cross" in self.patrol_paths:
                        new_npc.patrol_path_id = "route_mid_cross"

                    self.npcs.append(new_npc)
                    npc_id_counter += 1
                    current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == REST_SPOT_CHAR:
                    self.rest_spot_locations.append((r, c))
                    current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == RESOURCE_WOOD_CHAR:
                    self.resource_locations["wood"].append((r, c))
                    current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == RESOURCE_STONE_CHAR:
                    self.resource_locations["stone"].append((r, c))
                    current_row_chars[c] = DEFAULT_WALKABLE_REPLACEMENT_FOR_FEATURES
                elif char_val == WATER_CHAR_SOURCE:
                    self.water_tile_locations.append((r, c))
                    # Keep WATER_CHAR_SOURCE on map_data for drawing, A* will avoid it unless specified
            processed_map_rows.append("".join(current_row_chars))
        self.map_data = processed_map_rows

# --- Prompt Generation ---
def generate_encounter_prompt(npc_self: Npc, npc_other: Npc, game_state: GameState, previous_ai_mode_for_prompt: str) -> str:
    """Generates a prompt for an NPC deciding its initial action in an encounter."""
    # Determine NPC's energy status string
    if npc_self.energy < LOW_ENERGY_THRESHOLD:
        energy_status = "low"
    elif npc_self.energy < (npc_self.max_energy / 2): # Use npc_self.max_energy
        energy_status = "medium"
    else:
        energy_status = "high"

    # Summarize inventory
    inventory_items = [f"{count} {item}" for item, count in npc_self.inventory.items() if count > 0]
    inventory_summary = ", ".join(inventory_items) if inventory_items else "nothing"

    # Describe previous activity
    activity_description = "wandering" # Default
    if previous_ai_mode_for_prompt:
        activity_description = previous_ai_mode_for_prompt.replace("_", " ") # More readable
        if previous_ai_mode_for_prompt == AI_MODE_PATROLLING:
            patrol_id_to_report = npc_self.interrupted_patrol_path_id or npc_self.patrol_path_id
            activity_description = f"patrolling route '{patrol_id_to_report or 'unknown'}'"
        elif previous_ai_mode_for_prompt == AI_MODE_SEEKING_RESOURCE:
            activity_description = f"seeking {npc_self.current_resource_target_type or 'resources'}"
        elif previous_ai_mode_for_prompt == AI_MODE_GATHERING_RESOURCE:
            activity_description = f"gathering {npc_self.current_resource_target_type or 'resources'}"
        # No specific refinement needed for AI_MODE_SEEKING_REST, "seeking rest" is fine.

    # Build relationship context string
    rel_data_self_to_other = npc_self.get_or_initialize_relationship(npc_other.id)
    relationship_score = rel_data_self_to_other['score']
    last_interaction = rel_data_self_to_other['last_interaction_type']
    interaction_count = rel_data_self_to_other['interaction_count']
    relationship_desc = get_relationship_descriptor(relationship_score)

    relationship_context = (
        f"Your current relationship with NPC {npc_other.id} ('{npc_other.char}') is '{relationship_desc}' "
        f"(score: {relationship_score}). "
    )
    if interaction_count == 0:
        relationship_context += "This is your first encounter. "
    elif last_interaction:
        relationship_context += f"Your last interaction with them was recorded as '{last_interaction.replace('_', ' ')}'. "
    else:
        relationship_context += "You have interacted before, but the specifics of the last interaction are unclear. "

    # Determine available actions and build action options string
    available_actions_for_prompt_list = ["[Talk]", "[Ignore]", "[Flee]", "[Threaten]"]
    action_options_str = (
        "- [Talk] (Initiate a conversation)\n"
        "- [Ignore] (Disengage and try to continue your previous activity or find something new to do)\n"
        "- [Flee] (Quickly move away from this NPC)\n"
        "- [Threaten] (Issue a verbal threat or warning)\n"
    )
    if any(v > 0 for v in npc_self.inventory.values()):
        available_actions_for_prompt_list.append("[Offer_Gift]")
        action_options_str += "- [Offer_Gift] (Offer one of your items as a gift)\n"
    if energy_status == "low": # Only allow asking for help if energy is low
        available_actions_for_prompt_list.append("[Ask_For_Help]")
        action_options_str += "- [Ask_For_Help] (Plead for assistance due to your low energy)\n"

    prompt = (
        f"You are NPC {npc_self.id} ('{npc_self.char}'). Your defining personality trait is '{npc_self.personality}'. "
        f"Let this trait heavily influence your decision. "
        f"You were previously {activity_description}. Your energy is {energy_status}. "
        f"You are carrying {inventory_summary}.\n"
        f"You have just encountered NPC {npc_other.id} ('{npc_other.char}'), who is known for a '{npc_other.personality}' personality.\n"
        f"{relationship_context}\n\n"
        f"Considering your '{npc_self.personality}' nature AND this relationship history, what is your immediate reaction "
        f"to encountering NPC {npc_other.id}? "
        f"Choose ONE action from the following list: {', '.join(available_actions_for_prompt_list)}.\n"
        f"{action_options_str}"
        f"Respond with only the chosen action phrase (e.g., '[Talk]')."
    )
    # Optional: logging for debug purposes
    # print(f"DEBUG_PROMPT_REL: Encounter prompt for NPC {npc_self.id} vs {npc_other.id}. Rel score: {relationship_score}, LastInt: {last_interaction}, Count: {interaction_count}. Context: {relationship_context.strip()}")
    return prompt

def generate_dialogue_initiation_prompt(npc_speaker: Npc, npc_listener: Npc, game_state: GameState) -> str:
    """Generates a prompt for an NPC initiating a dialogue."""
    rel_data = npc_speaker.get_or_initialize_relationship(npc_listener.id)
    last_general_interaction = rel_data.get('last_interaction_type')

    prompt = (
        f"You are NPC {npc_speaker.id} ('{npc_speaker.char}'). Your personality is '{npc_speaker.personality}'. "
        f"You are initiating a conversation with NPC {npc_listener.id} ('{npc_listener.char}'), "
        f"whose personality is '{npc_listener.personality}'. "
    )
    if last_general_interaction:
        prompt += f"Prior to this decision to talk, your last notable interaction with them was '{last_general_interaction.replace('_', ' ')}'. "

    prompt += (
        f"\nStaying true to your '{npc_speaker.personality}' character, what is your opening line or greeting? "
        f"This is the very first thing said. Respond with only your single short sentence, without any action tags like [Talk]."
    )
    # Optional: logging for debug purposes
    # print(f"DEBUG_PROMPT_REL: Dialogue initiation prompt for NPC {npc_speaker.id} to {npc_listener.id}. Last general interaction: '{last_general_interaction}'.")
    return prompt

def generate_dialogue_response_prompt(npc_speaker: Npc, npc_listener: Npc, game_state: GameState, dialogue_history: list[dict]) -> str:
    """Generates a prompt for an NPC responding in a dialogue."""
    # Create a mapping of NPC IDs to their character and personality for easy lookup
    npc_map = {npc.id: npc for npc in game_state.npcs} # Consider passing this in if game_state.npcs is very large and this is called frequently

    history_str = "  (This is the beginning of the conversation.)\n"
    if dialogue_history:
        history_str = ""
        # Show last few lines of dialogue for context (e.g., last 4 entries)
        for entry in dialogue_history[-4:]:
            speaker_id = entry['speaker_id']
            s_npc_details = npc_map.get(speaker_id)
            speaker_char = s_npc_details.char if s_npc_details else '?'
            s_personality = s_npc_details.personality if s_npc_details else "Unknown"
            history_str += f"  NPC {speaker_id} ({speaker_char}, {s_personality}): {entry['line']}\n"

    rel_data = npc_speaker.get_or_initialize_relationship(npc_listener.id)
    last_general_interaction = rel_data.get('last_interaction_type')

    prompt = (
        f"You are NPC {npc_speaker.id} ('{npc_speaker.char}'), and your personality is '{npc_speaker.personality}'. "
        f"Reflect this '{npc_speaker.personality}' nature in your response.\n"
        f"You are conversing with NPC {npc_listener.id} ('{npc_listener.char}') (a '{npc_listener.personality}' individual). "
    )
    if last_general_interaction:
        prompt += f"Remember, your last general interaction with them before this current talk was recorded as '{last_general_interaction.replace('_', ' ')}'. "

    prompt += (
        f"\nRecent conversation history (you are NPC {npc_speaker.id}, most recent line is last):\n{history_str}\n"
        f"Based on the history and your personality, what is your response to the last line? "
        f"Respond with only your single short sentence, without any action tags like [Talk]."
    )
    # Optional: logging for debug purposes
    # print(f"DEBUG_PROMPT_REL: Dialogue response prompt for NPC {npc_speaker.id} to {npc_listener.id}. Last general interaction: '{last_general_interaction}'.")
    return prompt

# --- LLM Interaction ---
def get_llm_encounter_response(prompt_string: str, npc_id: int, current_game_tick: int, context_type: str = "action") -> str:
    """
    Gets a response from the LLM or a mock response.

    Args:
        prompt_string: The prompt to send to the LLM.
        npc_id: ID of the NPC, used for mock response generation.
        current_game_tick: Current game tick, used for mock response generation.
        context_type: Type of response expected ("action", "init_dialogue", "response_dialogue").

    Returns:
        The LLM's response string or a mock/fallback response.
    """
    # Ensure globals are accessible if they are modified or heavily relied upon.
    # However, it's better to pass them as arguments or manage them in a class if possible.
    global USE_MOCK_LLM, OLLAMA_DEFAULT_MODEL, ollama_client_available, actual_ollama_call

    if USE_MOCK_LLM:
        if context_type == "init_dialogue":
            greetings = [f"Well met, other NPC.", f"Greetings.", "What is it?", "A fine day indeed."] # Generic greeting
            return random.choice(greetings)
        elif context_type == "response_dialogue":
            mock_replies = ["Interesting.", "I see.", "Hmm, tell me more.", "Okay.", "What about it?", "Is that so?", "Indeed."]
            return random.choice(mock_replies)
        else: # context_type == "action"
            # Simple mock logic for action selection
            action_index = (current_game_tick // (ENCOUNTER_DURATION_TICKS // 3) + npc_id + random.randint(0,2)) % len(VALID_ENCOUNTER_ACTIONS)
            return VALID_ENCOUNTER_ACTIONS[action_index]

    # Actual LLM call
    if not ollama_client_available or actual_ollama_call is None:
        # Fallback if ollama client is not set up correctly
        if context_type == "init_dialogue": return "Hello (ollama_client missing)."
        if context_type == "response_dialogue": return "Indeed (ollama_client missing)."
        return "[Ignore]" # Default action fallback

    try:
        model_to_use = OLLAMA_DEFAULT_MODEL
        response = actual_ollama_call(prompt_string, model_name=model_to_use) # actual_ollama_call is 'call_model' from ollama_client

        llm_output_text = ""
        if isinstance(response, dict) and "response" in response:
            llm_output_text = response["response"].strip()
        elif isinstance(response, str): # Assuming direct string response from some client versions
            llm_output_text = response.strip()
        else: # Unexpected response format
            # Log this unexpected format
            print(f"WARN: LLM response for NPC {npc_id} was in an unexpected format: {type(response)}")
            if context_type == "init_dialogue": return "What? (unexpected LLM response format)"
            if context_type == "response_dialogue": return "I don't understand that. (unexpected LLM response format)"
            return "[Ignore]"

        if not llm_output_text: # Empty response from LLM
            if context_type == "init_dialogue": return "..." # Placeholder for empty greeting
            if context_type == "response_dialogue": return "..." # Placeholder for empty reply
            return "[Ignore]" # Default action for empty LLM response

        return llm_output_text

    # Specific exceptions from 'requests' library if ollama_client uses it
    except requests.exceptions.ConnectionError:
        # Log this error with more detail if possible
        if context_type == "init_dialogue": return "The ether is silent (Connection Error)."
        if context_type == "response_dialogue": return "Static on the line (Connection Error)."
        return "[Ignore]"
    except requests.exceptions.Timeout:
        if context_type == "init_dialogue": return "Took too long to think (Timeout)."
        if context_type == "response_dialogue": return "My thoughts are slow (Timeout)."
        return "[Ignore]"
    except requests.exceptions.RequestException as e: # Catch other requests-related errors
            print(f"WARN: LLM RequestException in ascii_game for NPC {npc_id}, context {context_type}: {e}")
        if context_type == "init_dialogue": return "A cosmic ray interfered (Request Error)."
        if context_type == "response_dialogue": return "Problem with request (Request Error)."
        return "[Ignore]"
    except ImportError: # Should have been caught by ollama_client_available, but as a safeguard
            # This error is less likely now with the initial check, but good for robustness
            print(f"ERROR: ImportError in get_llm_encounter_response for NPC {npc_id}, context {context_type}: {e}")
        if context_type == "init_dialogue": return "My voice module is offline (Import Error)."
        if context_type == "response_dialogue": return "Can't talk now (Import Error)."
        return "[Ignore]"
    except Exception as e: # Catch-all for other unexpected errors during LLM call
            print(f"ERROR: Unexpected error in get_llm_encounter_response (ascii_game) for NPC {npc_id}, context {context_type}: {e}")
            traceback.print_exc() # Print full traceback for unexpected errors
        if context_type == "init_dialogue": return "I'm speechless (Unexpected Error)."
        if context_type == "response_dialogue": return "I'm at a loss for words (Unexpected Error)."
        return "[Ignore]"

# --- Curses Drawing ---
def draw_map(stdscr, game_state: GameState, color_pairs: dict):
    """Draws the current game state to the curses window."""
    map_height = len(game_state.map_data)
    map_width = len(game_state.map_data[0]) if map_height > 0 else 0

    # Helper to safely add characters to screen
    def safe_addch(y, x, char, color_pair=None):
        if 0 <= y < curses.LINES and 0 <= x < curses.COLS -1: # curses.COLS-1 because writing to the last cell can cause issues
            try:
                if color_pair:
                    stdscr.addch(y, x, char, color_pair)
                else:
                    stdscr.addch(y, x, char)
            except curses.error:
                pass # Ignore errors if trying to draw at the very bottom-right corner, etc.

    # Draw map terrain
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            color_pair_to_use = color_pairs.get('default', curses.color_pair(1))
            display_char = char_val

            if char_val in GRASS_CHARS:
                color_pair_to_use = color_pairs.get('grass', curses.color_pair(1))
            elif char_val in FLOOR_CHARS:
                color_pair_to_use = color_pairs.get('floor', curses.color_pair(1))
            elif char_val == '#': # Wall
                color_pair_to_use = color_pairs.get('wall', curses.color_pair(1))
            elif char_val == 'T': # Target (debug)
                color_pair_to_use = color_pairs.get('target', curses.color_pair(1))
            elif char_val == WATER_CHAR_SOURCE: # Water source tiles are handled by animation
                continue
            safe_addch(r, c, display_char, color_pair_to_use)

    # Animate water
    if WATER_ANIMATION_CHARS and WATER_ANIMATION_SPEED > 0:
        num_frames = len(WATER_ANIMATION_CHARS)
        current_frame_index = (game_state.game_tick_counter // WATER_ANIMATION_SPEED) % num_frames
        char_to_draw_water = WATER_ANIMATION_CHARS[current_frame_index]
        water_color = color_pairs.get('water_anim', curses.color_pair(1))
        for r_w, c_w in game_state.water_tile_locations:
            safe_addch(r_w, c_w, char_to_draw_water, water_color)

    # Draw static features (rest spots, resources)
    for r_y, r_x in game_state.rest_spot_locations:
        safe_addch(r_y, r_x, REST_SPOT_CHAR, color_pairs.get('rest_spot', curses.color_pair(1)))
    for res_type, locations in game_state.resource_locations.items():
        char_to_draw = ''
        color_key = ''
        if res_type == "wood":
            char_to_draw = RESOURCE_WOOD_CHAR
            color_key = 'wood_res'
        elif res_type == "stone":
            char_to_draw = RESOURCE_STONE_CHAR
            color_key = 'stone_res'
        if char_to_draw:
            for r_y, r_x in locations:
                safe_addch(r_y, r_x, char_to_draw, color_pairs.get(color_key, curses.color_pair(1)))

    # Draw NPC paths (optional visualization)
    path_color = color_pairs.get('path', curses.color_pair(1))
    for npc_to_viz_path in game_state.npcs:
        if npc_to_viz_path.path and npc_to_viz_path.ai_mode not in \
           [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE, AI_MODE_ENCOUNTER]:
            for r_path, c_path in npc_to_viz_path.path:
                if (r_path, c_path) != (npc_to_viz_path.y, npc_to_viz_path.x): # Don't draw path dot on NPC itself
                    # Ensure path dot is drawn over map char, not replacing it visually
                    # This requires checking what's already at (r_path, c_path) if it's important
                    # For simplicity, we just draw the dot.
                    safe_addch(r_path, c_path, '.', path_color)

    # Draw NPCs
    for npc in game_state.npcs:
        safe_addch(npc.y, npc.x, npc.char, curses.color_pair(npc.color_pair_index))

    # Draw NPC status lines below the map
    # Max number of status lines to display based on available screen height
    max_status_lines = curses.LINES - map_height - 1 # -1 for the command line/last line buffer

    for i, npc_to_display in enumerate(game_state.npcs[:min(max_status_lines, 3)]): # Display for first few NPCs or up to available space
        status_line_y_pos = map_height + i
        if status_line_y_pos >= curses.LINES -1 : # Ensure status line is within screen bounds
            break

        # Build Target Info
        target_info = "No Target"
        if npc_to_display.target_y is not None:
            target_info = f"T:({npc_to_display.target_y},{npc_to_display.target_x})"
            if npc_to_display.ai_mode == AI_MODE_SEEKING_RESOURCE and npc_to_display.current_resource_target_type:
                target_info += f" Res:{npc_to_display.current_resource_target_type[:3]}"
            elif npc_to_display.ai_mode == AI_MODE_PATROLLING and npc_to_display.patrol_path_id:
                target_info += f" Pat:{npc_to_display.patrol_path_id[:7]}"

        # Build Mode Info
        mode_info_str = npc_to_display.ai_mode
        pers_info = npc_to_display.personality[:4] # Abbreviated personality
        llm_act_disp = npc_to_display.llm_parsed_action.strip("[]")[:4] if npc_to_display.llm_parsed_action else "...."

        submode_disp = ""
        if npc_to_display.encounter_submode == ENCOUNTER_SUBMODE_TALKING:
            turn_char = "My" if npc_to_display.id == npc_to_display.dialogue_turn_taker_id else "Wt"
            submode_disp = f"Talk({turn_char}{npc_to_display.dialogue_exchange_count // 2}/{MAX_DIALOGUE_EXCHANGES})"

        display_mode_map = {
            AI_MODE_ROAMING: "Roam", AI_MODE_SEEKING_REST: "SeekR", AI_MODE_RESTING: "Rest",
            AI_MODE_SEEKING_RESOURCE: "SeekRes",
            AI_MODE_GATHERING_RESOURCE: f"GathRes({npc_to_display.gathering_timer})",
            AI_MODE_PATROLLING: f"Patrol({npc_to_display.current_patrol_waypoint_index})",
            AI_MODE_ENCOUNTER: f"Enc{submode_disp}({llm_act_disp})[{npc_to_display.encounter_timer}]"
        }
        display_mode = display_mode_map.get(mode_info_str, mode_info_str[:7]) # Default to abbreviation if not in map

        # Build Inventory Info
        inv_info = f"Inv(W:{npc_to_display.inventory['wood']},S:{npc_to_display.inventory['stone']})"

        # Build Encounter/Relationship Info
        encounter_partner_info_str = ""
        if npc_to_display.ai_mode == AI_MODE_ENCOUNTER and npc_to_display.encounter_partner_id is not None:
            encounter_partner_info_str = f" EP:{npc_to_display.encounter_partner_id}"
            rel_data = npc_to_display.get_or_initialize_relationship(npc_to_display.encounter_partner_id)
            encounter_partner_info_str += f" RelS:{rel_data['score']}"
        else: # Display general relationship if not in encounter
            # Simplified: shows relationship with the first NPC in its relationship list
            if npc_to_display.relationships:
                first_rel_id = next(iter(npc_to_display.relationships)) # Get first key
                if first_rel_id != npc_to_display.id : # Avoid self-display
                    rel_data_val = npc_to_display.relationships[first_rel_id]
                    encounter_partner_info_str = f" Rel({first_rel_id}):{rel_data_val['score']}({rel_data_val['interaction_count']})"

        status_msg = (
            f"N{npc_to_display.id}({npc_to_display.char} {pers_info})@({npc_to_display.y},{npc_to_display.x}) "
            f"{target_info} P:{len(npc_to_display.path)} E:{int(npc_to_display.energy)} {inv_info} "
            f"{display_mode}{encounter_partner_info_str}"
        )

        # Safely draw the status message
        if status_line_y_pos < curses.LINES: # Ensure y is within bounds
            try:
                stdscr.move(status_line_y_pos, 0)
                stdscr.clrtoeol() # Clear the line before writing
                stdscr.addstr(status_line_y_pos, 0, status_msg[:curses.COLS-1]) # Avoid writing out of bounds
            except curses.error:
                pass # Ignore if it still fails (e.g. last char of screen)

# --- Main Game Setup & Loop ---
loop_counter = 0 # Global, consider moving into a game class or passing around

def main(stdscr): # stdscr is the curses window object
    """Main function to run the game."""
    global loop_counter, USE_MOCK_LLM, OLLAMA_DEFAULT_MODEL, ollama_client_available # Used by get_llm_encounter_response

    # Curses setup
    curses.curs_set(0) # Hide cursor
    curses.start_color()
    curses.use_default_colors() # Allow use of default terminal background color

    # Define color pairs (using -1 for default terminal background/foreground where appropriate)
    # It's good practice to check `curses.COLORS` and `curses.COLOR_PAIRS`
    # to ensure the terminal supports the number of colors/pairs you need.
    curses.init_pair(1, curses.COLOR_WHITE, -1)  # Default
    curses.init_pair(2, curses.COLOR_GREEN, -1)  # Grass
    curses.init_pair(3, curses.COLOR_BLUE, -1)   # Water
    curses.init_pair(4, curses.COLOR_YELLOW, -1) # NPC Yellow
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE) # Wall
    curses.init_pair(6, curses.COLOR_RED, -1)    # Target / Debug
    curses.init_pair(7, curses.COLOR_CYAN, -1)   # NPC Cyan
    curses.init_pair(8, curses.COLOR_MAGENTA, -1)# Rest Spot
    curses.init_pair(9, curses.COLOR_CYAN, -1)   # Path (can be same as NPC Cyan or different)
    # Consider using curses.COLOR_BLACK for background if default (-1) isn't desired for some elements
    curses.init_pair(10, curses.COLOR_YELLOW, curses.COLOR_DKGRAY if curses.COLORS > 8 else curses.COLOR_BLACK) # Wood Resource
    curses.init_pair(11, curses.COLOR_WHITE, curses.COLOR_DKGRAY if curses.COLORS > 8 else curses.COLOR_BLACK)  # Stone Resource
    curses.init_pair(12, curses.COLOR_MAGENTA, -1) # NPC Magenta

    color_pairs = {
        'default': curses.color_pair(1), 'grass': curses.color_pair(2),
        'water_anim': curses.color_pair(3), 'npc_yellow': curses.color_pair(4),
        'wall': curses.color_pair(5), 'target': curses.color_pair(6),
        'npc_cyan': curses.color_pair(7), 'rest_spot': curses.color_pair(8),
        'path': curses.color_pair(9), 'floor': curses.color_pair(1), # Floor uses default
        'wood_res': curses.color_pair(10), 'stone_res': curses.color_pair(11),
        'npc_magenta': curses.color_pair(12)
    }

    # Initial map and NPC setup
    initial_map_data_strings = [
        "####################",
        "#G@GRGWGS~GGGG~~GRT#", # @, %, & are NPC starting positions
        "#G#####%##&~~R####G#", # R is Rest Spot, W is Wood, S is Stone
        "#G#GGGGGRGS~GGGG~#G#", # ~ is Water
        "#G#G##~########G#G#", # G is Grass (original)
        "#G#G#RGGGGWWS#G#G#G#", # ' ' (space) is Floor (original)
        "#G#G#G#####G#G#G#G#",
        "#G#G#GGGGGGG#G#G#G#",
        "#G#GR####S##~##G#G#",
        "#GGGSGGGGGGWGG~GG#",
        "####################"
    ]
    # NPC definitions corresponding to characters on the map
    npc_definitions_on_map = {
        '@': {'color_pair_index': 4, 'patrol_path_id': "route_gate_patrol"}, # Example: assign patrol path
        '%': {'color_pair_index': 7, 'patrol_path_id': "route_resource_patrol"},
        '&': {'color_pair_index': 12, 'patrol_path_id': "route_mid_cross"}
    }

    if loop_counter == 0: # Only print initial messages once if main is ever re-entered (though not typical for curses.wrapper)
        print("--- Initializing GameState ---")

    game_state = GameState(map_data_strings=initial_map_data_strings, npc_definitions=npc_definitions_on_map)

    # A* walkable tiles are now derived from GameState's walkable_map_chars_for_roaming or DEFAULT_ASTAR_WALKABLE_TILES
    # This ensures consistency.
    astar_walkable_map_tiles = game_state.walkable_map_chars_for_roaming

    # Create a list of all walkable coordinates for random roaming, once at the start
    all_walkable_coords_for_roaming = []
    for r_idx, row_str_data in enumerate(game_state.map_data):
        for c_idx, char_val_data in enumerate(row_str_data):
            if char_val_data in game_state.walkable_map_chars_for_roaming:
                all_walkable_coords_for_roaming.append((r_idx, c_idx))

    stdscr.nodelay(True) # Non-blocking input
    NPC_MOVE_FREQUENCY = 3 # NPCs attempt to move every N game ticks
    game_running_duration = 1000 # Max game ticks for this session (for testing)

    if loop_counter == 0:
        for npc_init_log in game_state.npcs:
            print(f"Initial: NPC {npc_init_log.id} ('{npc_init_log.char}') at ({npc_init_log.y},{npc_init_log.x}), "
                  f"E:{npc_init_log.energy}, Mode:{npc_init_log.ai_mode}, Pers:{npc_init_log.personality}, "
                  f"Patrol:{npc_init_log.patrol_path_id}, Inv:{npc_init_log.inventory}, "
                  f"PerceptR:{npc_init_log.perception_range}")
        print(f"--- Starting Main Loop (USE_MOCK_LLM={USE_MOCK_LLM}, OLLAMA_DEFAULT_MODEL='{OLLAMA_DEFAULT_MODEL}') ---")

    # --- Main Game Loop ---
    while True:
        stdscr.clear() # Clear screen at the beginning of each frame
        loop_counter += 1
        game_state.game_tick_counter += 1

        # --- Encounter Detection Phase ---
        # Reset detection from previous tick
        for npc_obj_detect in game_state.npcs:
            npc_obj_detect.detected_encounter_partner_id_this_tick = None

        processed_encounter_pairs_this_tick = set() # Avoid processing same pair twice if detected by both
        if len(game_state.npcs) >= 2:
            for i in range(len(game_state.npcs)):
                npc_a = game_state.npcs[i]
                # NPCs in encounter or resting don't initiate new encounters
                if npc_a.ai_mode in [AI_MODE_ENCOUNTER, AI_MODE_RESTING]:
                    continue
                for j in range(i + 1, len(game_state.npcs)):
                    npc_b = game_state.npcs[j]
                    if npc_b.ai_mode in [AI_MODE_ENCOUNTER, AI_MODE_RESTING]:
                        continue

                    pair_key = tuple(sorted((npc_a.id, npc_b.id))) # Consistent key for the pair
                    if pair_key in processed_encounter_pairs_this_tick:
                        continue

                    dist = manhattan_distance_coords(npc_a.y, npc_a.x, npc_b.y, npc_b.x)
                    # Check if both NPCs can perceive each other
                    if dist <= npc_a.perception_range and dist <= npc_b.perception_range:
                        npc_a.detected_encounter_partner_id_this_tick = npc_b.id
                        npc_b.detected_encounter_partner_id_this_tick = npc_a.id
                        processed_encounter_pairs_this_tick.add(pair_key)
                        # Note: This means both NPCs will try to initiate an encounter.
                        # The AI logic needs to handle who "starts" or if it's mutual.
                        # Current logic: both will switch to ENCOUNTER mode and get an LLM prompt.

        # --- NPC AI Update Loop ---
        for npc in game_state.npcs:
            # current_npc_log_prefix = f"N{npc.id}({npc.char} E:{int(npc.energy)} M:{npc.ai_mode[:7]} P:{npc.personality[:4]})" # For debug prints
            npc_is_effectively_idle = (npc.target_y is None and not npc.path)

            # Deplete energy unless resting
            if npc.ai_mode != AI_MODE_RESTING and npc.energy > 0:
                npc.energy = max(0, npc.energy - ENERGY_DEPLETION_RATE)

            # --- Core AI Mode Logic ---
            # This large conditional block determines NPC behavior based on its current ai_mode.
            # It's effectively a state machine.

            if npc.ai_mode == AI_MODE_ENCOUNTER:
                # Encounter logic is complex.
                other_npc_in_encounter = get_npc_by_id(game_state.npcs, npc.encounter_partner_id)

                # 1. Parse LLM Response (if pending) & Update Relationships based on initial action
                if npc.llm_parsed_action is None and npc.llm_raw_response:
                    parsed_action = npc.llm_raw_response.strip()
                    if parsed_action not in VALID_ENCOUNTER_ACTIONS:
                        print(f"WARN: NPC {npc.id} received invalid action '{parsed_action}', defaulting to [Ignore].")
                        parsed_action = "[Ignore]"
                    npc.llm_parsed_action = parsed_action
                    npc.llm_raw_response = None # Consumed

                    if other_npc_in_encounter: # Ensure target still exists
                        update_relationships_on_encounter_action(npc, other_npc_in_encounter, npc.llm_parsed_action)

                    # Handle immediate consequences of the action (e.g., start dialogue, set flee target)
                    handle_encounter_action_consequences(npc, other_npc_in_encounter, npc.llm_parsed_action, game_state)

                # 2. Handle Ongoing Dialogue (if in TALKING submode and it's this NPC's turn)
                if npc.encounter_submode == ENCOUNTER_SUBMODE_TALKING and \
                   npc.id == npc.dialogue_turn_taker_id and \
                   other_npc_in_encounter: # Ensure partner is still valid for dialogue continuation

                    if npc.dialogue_exchange_count >= MAX_DIALOGUE_EXCHANGES * 2: # Max turns reached
                        npc.encounter_timer = 0 # End this NPC's side of dialogue
                        other_npc_in_encounter.encounter_timer = 0 # Also signal end for other NPC
                    # Check if it's this NPC's turn to speak (last line wasn't by self, or history is empty and self is initiator - handled by initial action)
                    elif npc.dialogue_history and npc.dialogue_history[-1]['speaker_id'] != npc.id:
                        response_prompt = generate_dialogue_response_prompt(npc, other_npc_in_encounter, game_state, npc.dialogue_history)
                        response_line = get_llm_encounter_response(response_prompt, npc.id, game_state.game_tick_counter, context_type="response_dialogue")
                        response_line = response_line.strip().replace('[', '').replace(']', '')

                        npc.dialogue_history.append({'speaker_id': npc.id, 'line': response_line})
                        npc.dialogue_exchange_count += 1
                        other_npc_in_encounter.dialogue_exchange_count = npc.dialogue_exchange_count # Sync

                        # Switch turn
                        npc.dialogue_turn_taker_id = other_npc_in_encounter.id
                        other_npc_in_encounter.dialogue_turn_taker_id = other_npc_in_encounter.id

                        npc.encounter_timer = ENCOUNTER_DURATION_TICKS # Reset timer for this interaction
                        other_npc_in_encounter.encounter_timer = ENCOUNTER_DURATION_TICKS
                    elif not npc.dialogue_history and npc.id == npc.dialogue_turn_taker_id:
                        # This case should ideally be handled by the initial [Talk] action consequence.
                        # If it occurs, it means this NPC initiated talk but didn't say anything.
                        # For robustness, could generate an opening line here or end the encounter.
                        print(f"WARN: NPC {npc.id} is turn taker in new dialogue but has no opening line. Ending encounter.")
                        npc.encounter_timer = 0
                        if other_npc_in_encounter: other_npc_in_encounter.encounter_timer = 0

                # 3. Decrement Encounter Timer and Handle Encounter End
                if npc.encounter_timer > 0:
                    npc.encounter_timer -= 1
                else: # Encounter ends (timer ran out or action set it to 0)
                    # This block resets NPC state after an encounter. Could be a method: npc.end_encounter()
                    prev_partner_id_local = npc.encounter_partner_id # Store before clearing for logging/cleanup

                    npc.encounter_partner_id = None
                    npc.target_y, npc.target_x, npc.path = None, None, [] # Clear any movement targets from encounter
                    # npc.previous_ai_mode is used to restore mode below
                    npc.llm_parsed_action = None
                    npc.llm_raw_response = None
                    npc.encounter_submode = None
                    npc.dialogue_history = []
                    npc.dialogue_exchange_count = 0
                    npc.dialogue_turn_taker_id = None

                    # Ensure the other NPC also exits the encounter fully if this one initiated the end
                    # This is important if, e.g., one NPC flees or ignores, the other should also stop encountering.
                    if prev_partner_id_local is not None:
                        other_npc_to_reset = next((n_other for n_other in game_state.npcs if n_other.id == prev_partner_id_local), None)
                        if other_npc_to_reset and other_npc_to_reset.ai_mode == AI_MODE_ENCOUNTER:
                            other_npc_to_reset.encounter_timer = 0 # This will trigger their cleanup on their next tick
                            # print(f"LOG: NPC {npc.id} ending encounter, also setting timer for NPC {other_npc_to_reset.id} to 0.")


                    # Restore previous AI mode or default to roaming/patrolling
                    # npc.reset_encounter_state() handles most of this.
                    # The main loop then handles restoring previous_ai_mode.
                    npc.reset_encounter_state()

                    # Restore previous AI mode or default to roaming/patrolling
                    if npc.interrupted_patrol_path_id is not None:
                        npc.ai_mode = AI_MODE_PATROLLING
                        npc.patrol_path_id = npc.interrupted_patrol_path_id
                        npc.current_patrol_waypoint_index = npc.interrupted_waypoint_index
                        npc.interrupted_patrol_path_id, npc.interrupted_waypoint_index = None, 0
                    elif npc.patrol_path_id and npc.previous_ai_mode == AI_MODE_PATROLLING:
                        npc.ai_mode = AI_MODE_PATROLLING
                    elif npc.previous_ai_mode: # Restore other previous modes if any
                         npc.ai_mode = npc.previous_ai_mode
                    else: # Default fallback
                        npc.ai_mode = AI_MODE_ROAMING
                    npc.previous_ai_mode = None # Clear previous_ai_mode after restoring

                if npc.ai_mode == AI_MODE_ENCOUNTER and npc.encounter_timer > 0: # If still in encounter, skip other AI logic
                    continue # Important to skip the rest of the AI logic for this tick

            elif npc.ai_mode == AI_MODE_RESTING:
                npc.energy = min(npc.max_energy, npc.energy + ENERGY_REPLENISH_RATE)
                if npc.energy >= npc.max_energy:
                    npc.target_y, npc.target_x, npc.path = None, None, []
                    npc.previous_ai_mode = None # Clear previous mode after resting is complete
                    # Restore interrupted patrol or default to roaming/patrolling
                    if npc.interrupted_patrol_path_id:
                        npc.ai_mode = AI_MODE_PATROLLING
                        npc.patrol_path_id = npc.interrupted_patrol_path_id
                        npc.current_patrol_waypoint_index = npc.interrupted_waypoint_index
                        npc.interrupted_patrol_path_id, npc.interrupted_waypoint_index = None, 0
                    elif npc.patrol_path_id: # If it has a default patrol path
                        npc.ai_mode = AI_MODE_PATROLLING
                    else:
                        npc.ai_mode = AI_MODE_ROAMING
                continue # Skip further AI logic if resting

            # --- Handle New Encounters --- (Moved before Low Energy to prioritize immediate threats/interactions)
            elif npc.detected_encounter_partner_id_this_tick is not None:
                # Check if current mode is interruptible by an encounter
                # NPCs already in an encounter or resting should not typically start a new one this way
                interruptible_modes = [AI_MODE_ROAMING, AI_MODE_PATROLLING, AI_MODE_SEEKING_RESOURCE, AI_MODE_SEEKING_REST]
                if npc.ai_mode in interruptible_modes:
                    npc.previous_ai_mode = npc.ai_mode # Store current mode before changing to encounter
                    if npc.ai_mode == AI_MODE_PATROLLING and npc.patrol_path_id is not None:
                        npc.interrupted_patrol_path_id = npc.patrol_path_id
                        npc.interrupted_waypoint_index = npc.current_patrol_waypoint_index

                    npc.reset_encounter_state() # Clear previous encounter/dialogue states
                    npc.ai_mode = AI_MODE_ENCOUNTER # Change mode
                    npc.encounter_partner_id = npc.detected_encounter_partner_id_this_tick
                    npc.encounter_timer = ENCOUNTER_DURATION_TICKS # Set timer for the new encounter

                    other_npc_for_prompt = get_npc_by_id(game_state.npcs, npc.encounter_partner_id)
                    if other_npc_for_prompt:
                        prompt_str = generate_encounter_prompt(npc, other_npc_for_prompt, game_state, npc.previous_ai_mode)
                        npc.llm_raw_response = get_llm_encounter_response(prompt_str, npc.id, game_state.game_tick_counter, context_type="action")
                    else:
                        # This case should ideally not be reached if detected_encounter_partner_id_this_tick is valid and NPC list is consistent
                        print(f"WARN: NPC {npc.id} detected encounter with non-existent NPC ID {npc.encounter_partner_id}. Reverting.")
                        npc.ai_mode = npc.previous_ai_mode or AI_MODE_ROAMING
                        npc.encounter_partner_id = None
                        npc.previous_ai_mode = None # Clear as the encounter setup failed

                    if npc.ai_mode == AI_MODE_ENCOUNTER:
                        continue # Skip other AI logic for this tick as it just started an encounter

            # --- Handle Low Energy --- (Processed if not starting a new encounter)
            # Note: Encounter logic (new or ongoing) takes precedence over low energy state changes below.
            # Resting state also takes precedence.
            elif npc.energy < LOW_ENERGY_THRESHOLD and \
                 npc.ai_mode not in [AI_MODE_SEEKING_REST, AI_MODE_ENCOUNTER, AI_MODE_RESTING]:
                # Don't interrupt an ongoing encounter for low energy unless critical (not implemented here)
                if npc.ai_mode == AI_MODE_ENCOUNTER:
                    pass # Allow encounter to finish unless energy is 0 (handled elsewhere or implicitly by AI)
                else:
                    npc.previous_ai_mode = npc.ai_mode # Store current task
                    # If patrolling, store interrupted path
                    if npc.ai_mode == AI_MODE_PATROLLING and npc.patrol_path_id:
                        npc.interrupted_patrol_path_id = npc.patrol_path_id
                        npc.interrupted_waypoint_index = npc.current_patrol_waypoint_index
                        npc.patrol_path_id = None # Temporarily remove patrol path while seeking rest

                    # Clear resource gathering state if interrupted
                    # if npc.ai_mode in [AI_MODE_SEEKING_RESOURCE, AI_MODE_GATHERING_RESOURCE]:
                    #    npc.current_resource_target_type = None
                    #    npc.gathering_timer = 0
                    # This is implicitly handled by setting target to None below

                    npc.ai_mode = AI_MODE_SEEKING_REST
                    npc.target_y, npc.target_x, npc.path = None, None, [] # Clear current path/target
                    npc.current_resource_target_type = None # Stop seeking resources
                    npc.gathering_timer = 0 # Stop gathering

            # --- AI Mode Specific Logic ---
            # These functions will modify npc state directly (ai_mode, target_y, target_x, path, etc.)
            if npc.ai_mode == AI_MODE_SEEKING_REST:
                handle_ai_seeking_rest(npc, game_state, astar_walkable_map_tiles, npc_is_effectively_idle)
            elif npc.ai_mode == AI_MODE_PATROLLING:
                handle_ai_patrolling(npc, game_state, npc_is_effectively_idle)
            elif npc.ai_mode == AI_MODE_GATHERING_RESOURCE:
                handle_ai_gathering_resource(npc, game_state)
            elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE:
                handle_ai_seeking_resource(npc, game_state, astar_walkable_map_tiles, npc_is_effectively_idle)
            elif npc.ai_mode == AI_MODE_ROAMING:
                handle_ai_roaming(npc, game_state, all_walkable_coords_for_roaming, npc_is_effectively_idle)

            # --- Pathfinding and Movement (Common to most active AI modes) ---
            # If NPC has a target but no path, and is in a mode that requires movement.
            # Encounter mode handles its own (lack of) movement or special movement like fleeing.
            # Resting and Gathering modes also manage their own (lack of) movement.
            if npc.target_y is not None and not npc.path and \
               npc.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE, AI_MODE_ENCOUNTER]:
                calculated_path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (npc.target_y, npc.target_x), walkable_tiles_map_chars=astar_walkable_map_tiles)
                if calculated_path:
                    npc.path = calculated_path
                    if npc.path and npc.path[0] == (npc.y, npc.x): # Remove current position if it's the first step
                        npc.path.pop(0)
                else: # No path found
                    npc.target_y, npc.target_x = None, None # Clear target
                    # Handle failure to find path based on mode
                    if npc.ai_mode == AI_MODE_SEEKING_REST: pass # Will try again or roam next tick
                    elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE:
                        npc.current_resource_target_type = None; npc.ai_mode = AI_MODE_ROAMING
                    elif npc.ai_mode == AI_MODE_PATROLLING:
                        # Try next waypoint or roam if path is broken
                        if npc.patrol_path_id and game_state.patrol_paths.get(npc.patrol_path_id):
                            route = game_state.patrol_paths[npc.patrol_path_id]
                            if route : npc.current_patrol_waypoint_index = (npc.current_patrol_waypoint_index + 1) % len(route)
                            else: npc.ai_mode = AI_MODE_ROAMING; npc.patrol_path_id = None # Invalid route
                        else: npc.ai_mode = AI_MODE_ROAMING; npc.patrol_path_id = None
                    else: # Default for other modes like ROAMING if target becomes unreachable
                        npc.ai_mode = AI_MODE_ROAMING

            # Move NPC if path exists (every NPC_MOVE_FREQUENCY ticks)
            if game_state.game_tick_counter % NPC_MOVE_FREQUENCY == 0:
                if npc.path and npc.ai_mode not in [AI_MODE_RESTING, AI_MODE_GATHERING_RESOURCE, AI_MODE_ENCOUNTER]:
                    next_y, next_x = npc.path.pop(0)

                    # Basic collision check: is the next step occupied by another NPC?
                    is_next_step_occupied = any(o.id != npc.id and o.y == next_y and o.x == next_x for o in game_state.npcs)

                    if not is_next_step_occupied:
                        npc.y, npc.x = next_y, next_x
                    else:
                        npc.path.insert(0, (next_y, next_x)) # Re-add step, effectively pausing
                        # Consider more complex collision handling: recalculate path or wait.
                        # For now, it just waits for the spot to be clear.

                    # Check if NPC reached its target
                    if npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x):
                        previous_ai_mode_on_arrival = npc.ai_mode # Store mode before changing it

                        if npc.ai_mode == AI_MODE_SEEKING_REST and (npc.y,npc.x) in game_state.rest_spot_locations:
                            npc.ai_mode = AI_MODE_RESTING; npc.path=[]
                        elif npc.ai_mode == AI_MODE_SEEKING_RESOURCE: # Arrived at resource
                            npc.ai_mode = AI_MODE_GATHERING_RESOURCE
                            npc.gathering_timer = GATHER_TIME_TICKS
                            npc.path=[]
                        elif npc.ai_mode == AI_MODE_PATROLLING:
                            pass # Stays in patrolling mode, will get next waypoint above
                        else: # Default for other modes like ROAMING
                            npc.ai_mode = AI_MODE_ROAMING

                        # Clear target unless it was a patrol waypoint arrival
                        if previous_ai_mode_on_arrival != AI_MODE_PATROLLING:
                            npc.target_y, npc.target_x, npc.path = None, None, []
                        elif npc.ai_mode == AI_MODE_PATROLLING : # Arrived at patrol waypoint
                             npc.path = [] # Clear path to recalculate for next waypoint

                    elif not npc.path and npc.target_y is not None: # Path ended but not at target (should not happen if path was valid)
                        npc.target_y, npc.target_x = None, None # Clear target
                        # Potentially log this unexpected state

        # --- Draw and Refresh Screen ---
        draw_map(stdscr, game_state, color_pairs)
        stdscr.refresh()

        # --- Timing and Input ---
        curses.napms(100) # Game speed: pause for 100 milliseconds

        # Exit condition (testing duration or 'q' pressed)
        if game_running_duration and game_state.game_tick_counter >= game_running_duration:
            # Using print for end-of-game messages as curses window might be closing
            print(f"LOG: Test duration ({game_running_duration} ticks) reached at game_tick {game_state.game_tick_counter}.")
            break

        try:
            key = stdscr.getch() # Get keyboard input (non-blocking)
            if key != curses.ERR: # A key was pressed
                if key == ord('q') or key == curses.ascii.ESC:
                    print(f"LOG: Quit key pressed at game_tick {game_state.game_tick_counter}.")
                    break
                # Add other key handling here if needed (e.g., pause, debug commands)
        except curses.error: # Can happen if window is too small or other curses issues
             pass # Ignore for now, or log if persistent

if __name__ == "__main__":
    # sys and traceback are now imported at the top of the file.
    try:
        curses.wrapper(main)
    except curses.error as e:
        # Handle curses-specific errors that might occur outside the wrapper's main loop
        # or if wrapper itself fails (e.g. terminal too small)
        print(f"ERROR: A curses specific error occurred: {e}")
        traceback.print_exc()
    except Exception as e:
        # Ensure curses is ended before printing traceback for general exceptions
        try:
            curses.endwin() # Attempt to restore terminal
        except curses.error:
            # endwin itself can fail if curses wasn't initialized or already ended
            # This usually means curses never started properly.
            pass
        print(f"ERROR: An unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        # Attempt to restore terminal state if not already done by wrapper or error handling
        try:
            if curses.isendwin() is False: # Only call endwin if curses is still active
                 curses.endwin()
        except curses.error:
            pass # Silently ignore if already ended or never started
        print(f"Game ended. Total ticks: {loop_counter}.")
        # Flushing stdout/stderr can be useful if output is buffered and not showing up
        if 'sys' in globals() and sys.stdout and not sys.stdout.closed:
            sys.stdout.flush()
        if 'sys' in globals() and sys.stderr and not sys.stderr.closed:
            sys.stderr.flush()

# --- Helper Functions ---
def get_npc_by_id(npc_list: list[Npc], npc_id: int | None) -> Npc | None:
    """
    Finds an NPC in a list by their ID.

    Args:
        npc_list: The list of NPCs to search.
        npc_id: The ID of the NPC to find.

    Returns:
        The NPC object if found, otherwise None.
    """
    if npc_id is None: # Guard against None ID
        return None
    for npc_obj in npc_list: # Renamed npc to npc_obj to avoid conflict if this func is called inside Npc class methods
        if npc_obj.id == npc_id:
            return npc_obj
    return None

# --- Encounter Helper Functions ---
def update_relationships_on_encounter_action(npc_actor: Npc, npc_target: Npc, action: str):
    """
    Updates relationship scores and interaction history between two NPCs
    based on an action taken by the npc_actor towards the npc_target.

    Args:
        npc_actor: The NPC performing the action.
        npc_target: The NPC who is the target of the action.
        action: The action string (e.g., "[Talk]", "[Threaten]").
    """
    if not npc_target: # Should not happen if called correctly
        print(f"WARN: update_relationships_on_encounter_action called for {npc_actor.id} with no target for action {action}.")
        return

    if action == "[Talk]":
        npc_actor.update_relationship_towards(npc_target.id, DEFAULT_RELATIONSHIP_SCORE_CHANGE_POSITIVE, INTERACTION_TYPE_I_TALKED_TO_THEM)
        npc_target.update_relationship_towards(npc_actor.id, DEFAULT_RELATIONSHIP_SCORE_CHANGE_POSITIVE, INTERACTION_TYPE_TALKED_TO_BY_ME)
    elif action == "[Ignore]":
        npc_actor.update_relationship_towards(npc_target.id, 0, INTERACTION_TYPE_I_IGNORED_THEM)
        npc_target.update_relationship_towards(npc_actor.id, DEFAULT_RELATIONSHIP_SCORE_CHANGE_NEGATIVE, INTERACTION_TYPE_IGNORED_ME)
    elif action == "[Flee]":
        npc_actor.update_relationship_towards(npc_target.id, 0, INTERACTION_TYPE_I_FLED_FROM_THEM)
        npc_target.update_relationship_towards(npc_actor.id, DEFAULT_RELATIONSHIP_SCORE_CHANGE_NEGATIVE, INTERACTION_TYPE_FLED_FROM_ME)
    elif action == "[Threaten]":
        npc_actor.update_relationship_towards(npc_target.id, DEFAULT_RELATIONSHIP_SCORE_CHANGE_NEGATIVE, INTERACTION_TYPE_I_THREATENED_THEM)
        npc_target.update_relationship_towards(npc_actor.id, STRONG_RELATIONSHIP_SCORE_CHANGE_NEGATIVE, INTERACTION_TYPE_THREATENED_ME)
    elif action == "[Offer_Gift]":
        # Assuming gift is always a positive intent from giver, receiver's reaction might vary (not implemented here)
        npc_actor.update_relationship_towards(npc_target.id, DEFAULT_RELATIONSHIP_SCORE_CHANGE_POSITIVE, INTERACTION_TYPE_I_OFFERED_GIFT_TO_THEM)
        npc_target.update_relationship_towards(npc_actor.id, STRONG_RELATIONSHIP_SCORE_CHANGE_POSITIVE, INTERACTION_TYPE_OFFERED_GIFT_TO_ME)
    elif action == "[Ask_For_Help]":
        # Score might change based on whether help is given; for now, initial interaction is neutral.
        npc_actor.update_relationship_towards(npc_target.id, 0, INTERACTION_TYPE_I_ASKED_FOR_HELP_FROM_THEM)
        npc_target.update_relationship_towards(npc_actor.id, 0, INTERACTION_TYPE_ASKED_FOR_HELP_FROM_ME)

def handle_encounter_action_consequences(npc: Npc, other_npc: Npc | None, action: str, game_state: GameState):
    """
    Handles the game state changes (like starting dialogue, fleeing, setting timers)
    resulting from an NPC's chosen encounter action.

    Args:
        npc: The NPC performing the action.
        other_npc: The other NPC involved in the encounter (if any).
        action: The action string (e.g., "[Talk]", "[Flee]").
        game_state: The current game state.
    """
    if action == "[Talk]" and npc.encounter_submode is None:
        npc.encounter_submode = ENCOUNTER_SUBMODE_TALKING # Mark that this NPC is now in 'talking' submode
        if other_npc:
            shared_history = []
            npc.dialogue_history = shared_history
            other_npc.dialogue_history = shared_history
            npc.dialogue_exchange_count = 0
            other_npc.dialogue_exchange_count = 0

            npc.dialogue_turn_taker_id = npc.id
            other_npc.dialogue_turn_taker_id = npc.id

            other_npc.encounter_submode = ENCOUNTER_SUBMODE_TALKING
            other_npc.encounter_partner_id = npc.id
            other_npc.encounter_timer = ENCOUNTER_DURATION_TICKS

            initiation_prompt = generate_dialogue_initiation_prompt(npc, other_npc, game_state)
            opening_line = get_llm_encounter_response(initiation_prompt, npc.id, game_state.game_tick_counter, context_type="init_dialogue")
            opening_line = opening_line.strip().replace('[', '').replace(']', '')

            npc.dialogue_history.append({'speaker_id': npc.id, 'line': opening_line})
            npc.dialogue_exchange_count += 1
            other_npc.dialogue_exchange_count = npc.dialogue_exchange_count

            npc.dialogue_turn_taker_id = other_npc.id
            other_npc.dialogue_turn_taker_id = other_npc.id
            npc.encounter_timer = ENCOUNTER_DURATION_TICKS
        else:
            npc.llm_parsed_action = "[Ignore]" # Fallback if partner is somehow gone
            npc.encounter_timer = 0 # End encounter

    elif action == "[Ignore]":
        npc.encounter_timer = 0
    elif action == "[Flee]":
        flee_target_y, flee_target_x = npc.y, npc.x
        if other_npc:
            map_h, map_w = len(game_state.map_data), len(game_state.map_data[0])
            if other_npc.y < npc.y: flee_target_y = min(map_h - 1, npc.y + 3)
            else: flee_target_y = max(0, npc.y - 3)
            if other_npc.x < npc.x: flee_target_x = min(map_w - 1, npc.x + 3)
            else: flee_target_x = max(0, npc.x - 3)
        npc.target_y, npc.target_x = flee_target_y, flee_target_x
        npc.path = []
        # Encounter timer is not set to 0 here; the main loop's timer decrement will eventually end it,
        # or it's set to 0 if the NPC successfully moves away. This allows "fleeing" to take a moment.
        # However, for immediate mode change, timer could be set to 0 and mode to roaming.
        # For now, let existing timer logic handle it.
    elif action == "[Threaten]":
        npc.encounter_timer = max(1, ENCOUNTER_DURATION_TICKS // 2)
    elif action in ["[Offer_Gift]", "[Ask_For_Help]"] and npc.encounter_submode != ENCOUNTER_SUBMODE_TALKING:
        npc.encounter_timer = ENCOUNTER_DURATION_TICKS


# --- AI Mode Helper Functions ---
def handle_ai_seeking_rest(npc: Npc, game_state: GameState, walkable_tiles: list[str], is_idle: bool):
    """
    Handles AI logic for an NPC in AI_MODE_SEEKING_REST.
    The NPC will try to find the closest rest spot and pathfind to it.
    If no rest spots are available or no path is found, it reverts to roaming.
    """
    if is_idle: # Needs a target or path
        if not game_state.rest_spot_locations: # No rest spots on map
            npc.ai_mode = AI_MODE_ROAMING # Fallback
            return

        best_target_spot, shortest_path_len = None, float('inf')
        for spot_y, spot_x in game_state.rest_spot_locations:
            if (npc.y, npc.x) == (spot_y, spot_x): # Already at a rest spot
                best_target_spot = (spot_y, spot_x)
                npc.path = [] # Clear path, already there
                shortest_path_len = 0
                break # Found optimal (already there)
            current_path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (spot_y, spot_x), walkable_tiles_map_chars=walkable_tiles)
            if current_path and len(current_path) < shortest_path_len:
                shortest_path_len = len(current_path)
                best_target_spot = (spot_y, spot_x)

        if best_target_spot:
            npc.target_y, npc.target_x = best_target_spot
            if (npc.y, npc.x) == best_target_spot: # Arrived (should have been caught by the check above, but good safeguard)
                npc.ai_mode = AI_MODE_RESTING
                npc.path = []
            # Path will be calculated in the main loop's pathfinding section if not already at spot
        else: # No path to any rest spot
            npc.ai_mode = AI_MODE_ROAMING # Fallback

def handle_ai_patrolling(npc: Npc, game_state: GameState, is_idle: bool):
    """Handles AI logic for an NPC in AI_MODE_PATROLLING."""
    if npc.patrol_path_id and \
       (is_idle or ((npc.y, npc.x) == (npc.target_y, npc.target_x))): # Arrived at waypoint or needs one
        route = game_state.patrol_paths.get(npc.patrol_path_id)
        if route:
            if (npc.y, npc.x) == (npc.target_y, npc.target_x): # If arrived at current waypoint, advance to next
                 npc.current_patrol_waypoint_index = (npc.current_patrol_waypoint_index + 1) % len(route)
            npc.target_y, npc.target_x = route[npc.current_patrol_waypoint_index]
            npc.path = [] # Will be recalculated by main pathfinding logic
        else: # Invalid patrol_path_id or route
            npc.ai_mode = AI_MODE_ROAMING
            npc.patrol_path_id = None # Clear invalid path ID

def handle_ai_gathering_resource(npc: Npc, game_state: GameState):
    """
    Handles AI logic for an NPC in AI_MODE_GATHERING_RESOURCE.
    Decrements gathering timer. When timer is up, adds resource to inventory
    and transitions to a post-gathering state (e.g., roaming or back to patrol).
    """
    npc.gathering_timer -= 1
    if npc.gathering_timer <= 0:
        res_type = npc.current_resource_target_type
        if res_type and res_type in npc.inventory: # Ensure res_type is valid
            npc.inventory[res_type] += GATHER_AMOUNT

        # Restore interrupted patrol or default to roaming/patrolling
        if npc.interrupted_patrol_path_id:
            npc.ai_mode = AI_MODE_PATROLLING
            npc.patrol_path_id = npc.interrupted_patrol_path_id
            npc.current_patrol_waypoint_index = npc.interrupted_waypoint_index
            npc.interrupted_patrol_path_id, npc.interrupted_waypoint_index = None, 0
        elif npc.patrol_path_id: # If it has a default patrol path
            npc.ai_mode = AI_MODE_PATROLLING
        else:
            npc.ai_mode = AI_MODE_ROAMING

        npc.target_y, npc.target_x, npc.path = None, None, [] # Clear target and path
        npc.current_resource_target_type = None # Clear current resource type

def handle_ai_seeking_resource(npc: Npc, game_state: GameState, walkable_tiles: list[str], is_idle: bool):
    """
    Handles AI logic for an NPC in AI_MODE_SEEKING_RESOURCE.
    If no current resource target, it picks one. Then, it finds the closest
    resource of that type and sets it as a target.
    If no resources or no path, reverts to roaming.
    """
    if is_idle: # Needs a resource target
        if not npc.current_resource_target_type or \
           not game_state.resource_locations.get(npc.current_resource_target_type):
            available_res_types = [rt for rt in RESOURCE_TYPES if game_state.resource_locations.get(rt)]
            if not available_res_types:
                npc.ai_mode = AI_MODE_ROAMING
                return
            npc.current_resource_target_type = random.choice(available_res_types)

        resource_locations_of_target_type = game_state.resource_locations.get(npc.current_resource_target_type, [])
        if not resource_locations_of_target_type: # Should be caught by check above, but as safeguard
            npc.ai_mode = AI_MODE_ROAMING
            npc.current_resource_target_type = None
            return

        best_target_resource_spot, shortest_path_len = None, float('inf')
        for spot_y, spot_x in resource_locations_of_target_type:
            current_path = astar_pathfind(game_state.map_data, (npc.y, npc.x), (spot_y, spot_x), walkable_tiles_map_chars=walkable_tiles)
            if current_path and len(current_path) < shortest_path_len:
                shortest_path_len = len(current_path)
                best_target_resource_spot = (spot_y, spot_x)

        if best_target_resource_spot:
            npc.target_y, npc.target_x = best_target_resource_spot
            npc.path = [] # Path will be calculated by main pathfinding logic
        else: # No path to any resource of this type
            npc.ai_mode = AI_MODE_ROAMING
            npc.current_resource_target_type = None

def handle_ai_roaming(npc: Npc, game_state: GameState, all_walkable_coords: list[tuple[int,int]], is_idle: bool):
    """
    Handles AI logic for an NPC in AI_MODE_ROAMING.
    The NPC may resume patrolling, decide to seek resources, or pick a random
    walkable spot to move to.
    """
    if is_idle:
        # 1. Resume interrupted patrol
        if npc.interrupted_patrol_path_id:
            npc.ai_mode = AI_MODE_PATROLLING
            npc.patrol_path_id = npc.interrupted_patrol_path_id
            npc.current_patrol_waypoint_index = npc.interrupted_waypoint_index
            npc.interrupted_patrol_path_id, npc.interrupted_waypoint_index = None, 0
            return
        # 2. Start default patrol
        elif npc.patrol_path_id:
            npc.ai_mode = AI_MODE_PATROLLING
            return

        # 3. Chance to seek resources
        if random.random() < CHANCE_TO_SEEK_RESOURCE:
            available_res_types = [rt for rt in RESOURCE_TYPES if game_state.resource_locations.get(rt)]
            if available_res_types:
                npc.current_resource_target_type = random.choice(available_res_types)
                npc.ai_mode = AI_MODE_SEEKING_RESOURCE
                npc.target_y, npc.target_x, npc.path = None, None, []
                return

        # 4. Pick a random walkable spot
        if all_walkable_coords:
            possible_choices = [crd for crd in all_walkable_coords if crd != (npc.y, npc.x)]
            if not possible_choices: possible_choices = all_walkable_coords
            if possible_choices:
                 npc.target_y, npc.target_x = random.choice(possible_choices)
                 npc.path = [] # Clear path for recalculation
