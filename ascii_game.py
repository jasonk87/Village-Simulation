import curses
import curses.ascii # For checking 'q'
import heapq
import collections

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

def manhattan_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

def reconstruct_path(current_node):
    path = []
    while current_node:
        path.append(current_node.position)
        current_node = current_node.parent
    return path[::-1]

def astar_pathfind(map_data, start_pos, end_pos, walkable_tiles=['G', 'W', '@']):
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
            # This node was already processed with a better or equal path via a different route that also ended up in open_list
            # or it was removed and re-added with higher f value (which shouldn't happen if logic is correct)
            continue
        del open_list_nodes[current_node.position]


        if current_node.position == end_node.position:
            return reconstruct_path(current_node)

        closed_list_g_costs[current_node.position] = current_node.g

        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            neighbor_pos = (current_node.position[0] + dy, current_node.position[1] + dx)

            if not (0 <= neighbor_pos[0] < map_height and 0 <= neighbor_pos[1] < map_width):
                continue
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

# 1. GameState Target & Path Management
class GameState:
    def __init__(self, map_data, npc_char, npc_y, npc_x):
        self.map_data = map_data
        self.npc_char = npc_char
        self.npc_y = npc_y
        self.npc_x = npc_x
        self.npc_target_y = None
        self.npc_target_x = None
        self.npc_path = [] # Stores current path NPC is following

def draw_map(stdscr, game_state, color_pairs):
    # 4. Path Visualization
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

def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    color_pairs = {
        'default': curses.color_pair(1), 'grass': curses.color_pair(2),
        'water': curses.color_pair(3), 'npc': curses.color_pair(4),
        'wall': curses.color_pair(5)
    }
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)

    initial_map_data = [
        "####################",
        "#GGGGGGGGGGGGGGGGGG#",
        "#@GGGWWWWWWWWGGGGGG#", # NPC start position updated for clarity
        "#GGGGWGGGGGGWGGGGGG#",
        "#GGGGWGGGGGGWGGGGGG#",
        "#GGGGWGGGGGGWWWWGGG#",
        "#GGGGWGGGGGGGGGGGGG#",
        "#GGGGGGGGGGGGGGGGGG#",
        "#GGGGGGGGGGGGGGGGGT#", # Target T
        "####################"
    ]

    # Update GameState to use the map's initial NPC position if '@' is present
    npc_initial_y, npc_initial_x = 2, 1
    for r, row in enumerate(initial_map_data):
        if '@' in row:
            npc_initial_y, npc_initial_x = r, row.find('@')
            # Remove '@' from map_data, NPC is drawn from game_state
            map_list = list(row)
            map_list[npc_initial_x] = 'G'
            initial_map_data[r] = "".join(map_list)
            break

    game_state = GameState(map_data=initial_map_data, npc_char='@', npc_y=npc_initial_y, npc_x=npc_initial_x)

    # Set a default target
    game_state.npc_target_y, game_state.npc_target_x = 8, 18 # Position of 'T'

    stdscr.nodelay(True)
    loop_counter = 0

    while True:
        stdscr.clear()

        # 3. Main Loop AI Logic
        # Path Calculation
        if game_state.npc_target_y is not None and not game_state.npc_path:
            path = astar_pathfind(game_state.map_data,
                                  (game_state.npc_y, game_state.npc_x),
                                  (game_state.npc_target_y, game_state.npc_target_x))
            if path:
                game_state.npc_path = path
                # Remove the starting position from path as NPC is already there
                if game_state.npc_path and game_state.npc_path[0] == (game_state.npc_y, game_state.npc_x):
                    game_state.npc_path.pop(0)
            else:
                # No path found, clear target (or handle differently)
                # For now, let's make it try again next cycle if target is still set
                # game_state.npc_target_y = None
                # game_state.npc_target_x = None
                # stdscr.addstr(map_height + 1, 0, "No path to target! ") # Debug
                pass


        # Movement Along Path
        loop_counter += 1
        if loop_counter % 3 == 0: # Slow down NPC path movement a bit
            if game_state.npc_path:
                next_step = game_state.npc_path.pop(0)
                game_state.npc_y, game_state.npc_x = next_step

                if (game_state.npc_y, game_state.npc_x) == (game_state.npc_target_y, game_state.npc_target_x):
                    game_state.npc_target_y = None
                    game_state.npc_target_x = None
                    game_state.npc_path = [] # Clear path on arrival
                    # Set a new target for testing continuous movement (optional)
                    # game_state.npc_target_y, game_state.npc_target_x = (2,1) if (game_state.npc_y, game_state.npc_x) != (2,1) else (8,18)


        draw_map(stdscr, game_state, color_pairs)
        stdscr.refresh()
        curses.napms(100)

        key = stdscr.getch()

        if key != curses.ERR:
            if key == ord('q') or key == curses.ascii.ESC:
                break

            # Player Control (only if NPC has no AI target)
            if game_state.npc_target_y is None:
                new_npc_y, new_npc_x = game_state.npc_y, game_state.npc_x
                if key == curses.KEY_UP: new_npc_y -= 1
                elif key == curses.KEY_DOWN: new_npc_y += 1
                elif key == curses.KEY_LEFT: new_npc_x -= 1
                elif key == curses.KEY_RIGHT: new_npc_x += 1

                map_height = len(game_state.map_data)
                map_width = len(game_state.map_data[0])
                if 0 <= new_npc_y < map_height and \
                   0 <= new_npc_x < map_width and \
                   game_state.map_data[new_npc_y][new_npc_x] != '#':
                    game_state.npc_y, game_state.npc_x = new_npc_y, new_npc_x
                    game_state.npc_path = [] # Clear AI path if player moves NPC


if __name__ == "__main__":
    curses.wrapper(main)
