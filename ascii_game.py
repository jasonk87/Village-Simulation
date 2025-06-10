import curses
import curses.ascii # For checking 'q'
import heapq
import collections
import random
import time

# NPC Data Structure
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
        self.is_idle = True

# Node Representation (for A*)
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
def astar_pathfind(map_data, start_pos, end_pos, walkable_tiles_map_chars=['G', 'W', 'T', ' ']):
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

class GameState:
    def __init__(self, map_data_strings, npc_definitions):
        self.map_data = []
        self.npcs = []
        self.walkable_map_chars = ['G', 'W', 'T', ' ']

        npc_id_counter = 0
        temp_map = [list(row_str) for row_str in map_data_strings]

        for r, row_list in enumerate(temp_map):
            for c, char_val in enumerate(row_list):
                if char_val in npc_definitions:
                    npc_def = npc_definitions[char_val]
                    new_npc = Npc(
                        id=npc_id_counter,
                        y=r,
                        x=c,
                        char=char_val,
                        color_pair_index=npc_def['color_pair_index']
                    )
                    self.npcs.append(new_npc)
                    npc_id_counter += 1
                    temp_map[r][c] = 'G'

        self.map_data = ["".join(row_list) for row_list in temp_map]

def draw_map(stdscr, game_state, color_pairs):
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            color_pair_to_use = color_pairs.get('default', curses.color_pair(1))
            display_char = char_val
            if char_val == 'G': color_pair_to_use = color_pairs.get('grass', curses.color_pair(1))
            elif char_val == 'W': color_pair_to_use = color_pairs.get('water', curses.color_pair(1))
            elif char_val == '#': color_pair_to_use = color_pairs.get('wall', curses.color_pair(1))
            elif char_val == 'T': color_pair_to_use = color_pairs.get('target', curses.color_pair(1))

            # Simple path viz for the first NPC if its path exists (can be enhanced for multiple NPCs)
            if game_state.npcs:
                # Example: visualize path of first NPC, or a specific NPC by ID
                # For simplicity, just showing path for npc[0] if it exists
                npc_to_viz_path = game_state.npcs[0]
                if npc_to_viz_path.path and (r,c) in npc_to_viz_path.path:
                     if (r,c) != (npc_to_viz_path.y, npc_to_viz_path.x) :
                        display_char = '.'

            try: stdscr.addch(r, c, display_char, color_pair_to_use)
            except curses.error: pass

    for npc in game_state.npcs:
        try: stdscr.addch(npc.y, npc.x, npc.char, curses.color_pair(npc.color_pair_index))
        except curses.error: pass

    # Display status for a few NPCs for simple debugging
    for i, npc_to_display in enumerate(game_state.npcs[:2]): # Display for first 2 NPCs
        if npc_to_display.target_y is not None:
            try:
                status_msg = f"NPC{npc_to_display.id} T:({npc_to_display.target_y},{npc_to_display.target_x}) P:{len(npc_to_display.path)}"
                stdscr.addstr(len(game_state.map_data) + i, 0, status_msg[:curses.COLS-1])
            except curses.error: pass


def main(stdscr):
    curses.curs_set(0)
    curses.start_color()

    color_pairs = {
        'default': curses.color_pair(1), 'grass': curses.color_pair(2),
        'water': curses.color_pair(3), 'npc_yellow': curses.color_pair(4), # Used by ID 4
        'wall': curses.color_pair(5), 'target': curses.color_pair(6),
        'npc_cyan': curses.color_pair(7) # Used by ID 7
    }
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_CYAN, curses.COLOR_BLACK)

    initial_map_data_strings = [
        "####################",
        "#G@GGGGGGGGGGGGGGGT#",
        "#G#####%##########G#",
        "#G#GGGGGGGGGGGGGG#G#",
        "#G#G###########G#G#",
        "#G#G#GGGGGGG#G#G#G#",
        "#G#G#G#####G#G#G#G#",
        "#G#G#GGGGGGG#G#G#G#",
        "#G#G###########G#G#",
        "#GGGGGGGGGGGGGGGGG#",
        "####################"
    ]

    npc_definitions_on_map = {
        '@': {'color_pair_index': 4},
        '%': {'color_pair_index': 7}
    }

    game_state = GameState(map_data_strings=initial_map_data_strings,
                           npc_definitions=npc_definitions_on_map)

    all_walkable_coords = []
    for r, row_str in enumerate(game_state.map_data):
        for c, char_val in enumerate(row_str):
            if char_val in game_state.walkable_map_chars:
                all_walkable_coords.append((r,c))

    stdscr.nodelay(True)
    loop_counter = 0
    astar_walkable_map_tiles = game_state.walkable_map_chars
    NPC_MOVE_FREQUENCY = 3 # Move NPC every N game loops

    while True:
        stdscr.clear()
        loop_counter += 1

        for npc in game_state.npcs:
            # AI Decision Logic (Target Selection)
            if npc.target_y is None and not npc.path:
                npc.is_idle = True

            if npc.is_idle:
                if all_walkable_coords:
                    possible_targets = [coord for coord in all_walkable_coords if coord != (npc.y, npc.x)]
                    if not possible_targets: possible_targets = all_walkable_coords
                    if possible_targets:
                        new_target_y, new_target_x = random.choice(possible_targets)
                        npc.target_y = new_target_y
                        npc.target_x = new_target_x
                        npc.is_idle = False
                        print(f"NPC {npc.id} ({npc.char}) new random target: ({npc.target_y}, {npc.target_x})")
                else:
                    print(f"NPC {npc.id} ({npc.char}): No walkable_coords for random target.")

            # Path Calculation Logic (Per-NPC)
            if npc.target_y is not None and not npc.path and not npc.is_idle:
                calculated_path = astar_pathfind(game_state.map_data,
                                                 (npc.y, npc.x),
                                                 (npc.target_y, npc.target_x),
                                                 astar_walkable_map_tiles)
                if calculated_path:
                    npc.path = calculated_path
                    print(f"Path found for NPC {npc.id} ({npc.char}) to ({npc.target_y},{npc.target_x}): {npc.path}")
                    if npc.path and npc.path[0] == (npc.y, npc.x): # Remove current pos if A* includes it
                        npc.path.pop(0)
                else:
                    print(f"No path for NPC {npc.id} ({npc.char}) to target ({npc.target_y},{npc.target_x}). Clearing target.")
                    npc.target_y = None
                    npc.target_x = None
                    npc.is_idle = True

            # Movement Logic (Per-NPC)
            if loop_counter % NPC_MOVE_FREQUENCY == 0:
                if npc.path: # Check current NPC's path
                    next_y, next_x = npc.path.pop(0) # Get and remove first step
                    # Basic collision check with other NPCs (simple version: if target tile is occupied by another NPC, wait)
                    # This can be improved with more sophisticated collision avoidance.
                    is_next_step_occupied_by_other_npc = False
                    for other_npc in game_state.npcs:
                        if other_npc.id != npc.id and other_npc.y == next_y and other_npc.x == next_x:
                            is_next_step_occupied_by_other_npc = True
                            npc.path.insert(0, (next_y, next_x)) # Re-add step, try again next time
                            print(f"NPC {npc.id} ({npc.char}) path blocked by NPC {other_npc.id} at ({next_y},{next_x}). Waiting.")
                            break

                    if not is_next_step_occupied_by_other_npc:
                        npc.y = next_y
                        npc.x = next_x
                        # print(f"NPC {npc.id} ({npc.char}) moved to ({npc.y},{npc.x})") # Optional: can be verbose

                    # Arrival Check (after moving)
                    if npc.target_y is not None and (npc.y, npc.x) == (npc.target_y, npc.target_x):
                        print(f"NPC {npc.id} ({npc.char}) reached target at ({npc.y}, {npc.x}).")
                        npc.target_y = None
                        npc.target_x = None
                        npc.path = [] # Path is now empty or should be cleared
                        npc.is_idle = True
                    elif not npc.path and npc.target_y is not None: # Path ended but not at target
                        print(f"NPC {npc.id} ({npc.char}) path ended but not at target. Current:({npc.y},{npc.x}), Target:({npc.target_y},{npc.target_x}). Recalculating.")
                        # Clear target to force recalc or just path, for now clear path to recalc
                        npc.is_idle = False # Force path recalculation next cycle
                        # No, if path is empty and not at target, it implies path was bad or target became unreachable
                        # Set to idle to pick a new target if it's not immediately trying to repath to same target.
                        # For now, let path calculation logic handle this: if target still set, it will try again.
                        # If target was blocked, pathfinding should fail and then it becomes idle.
                        pass


        draw_map(stdscr, game_state, color_pairs)
        stdscr.refresh()
        curses.napms(100)

        key = stdscr.getch()
        if key != curses.ERR:
            if key == ord('q') or key == curses.ascii.ESC:
                break
            # Player control logic can be added here for a specific NPC if needed

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try: curses.endwin()
        except: pass
        print("Game ended.")
