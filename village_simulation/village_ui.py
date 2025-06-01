import tkinter as tk
from tkinter import scrolledtext, font
import queue
import re # For parsing agent_id in agent list

class VillageUI:
    """
    Manages the Tkinter-based user interface for the Primitive Village Simulation.

    This class is responsible for creating all UI widgets, handling user interactions
    (clicks, selections, text input), processing updates from the simulation engine
    via a queue, and dynamically theming the UI.
    """
    def __init__(self, root: tk.Tk, update_queue: queue.Queue):
        """
        Initializes the VillageUI.

        Args:
            root: The root Tkinter window.
            update_queue: A queue used to receive updates from the simulation engine.
        """
        self.root = root
        self.update_queue = update_queue
        self.root.title("Primitive Village Chronicles")

        # --- Instance Variables ---
        self.all_agents_data_cache = {} # Stores full data for all agents, keyed by agent_id
        self.map_size = (10, 10)  # Width, Height of the map grid
        self.clickable_map_elements = [] # Stores info about clickable elements on the map

        # --- Theme and Font Initialization ---
        self._init_themes() # Defines self.themes, self.current_theme_name, self.current_theme
        self._init_font()   # Defines self.console_font based on current theme

        # --- UI Structure Initialization ---
        self._setup_menu()
        self._setup_top_frame()    # Map display
        self._setup_bottom_frame() # Status bar and game controls
        self._setup_middle_frame() # Main content area (agent list, log, details)

        # Apply the default theme to all created widgets
        self._apply_theme(self.current_theme_name)

        # Start polling the update queue
        self.root.after(100, self.process_ui_queue)

    def _setup_menu(self):
        """Sets up the main menu bar and theme selection submenu."""
        # Main Menu Bar
        self.main_menubar = tk.Menu(self.root)
        self.root.config(menu=self.main_menubar)

        # Theme Menu
        theme_menu = tk.Menu(self.main_menubar, tearoff=0)
        self.main_menubar.add_cascade(label="Theme", menu=theme_menu)
        self.theme_choice_var = tk.StringVar(value=self.current_theme_name)
        theme_menu.add_radiobutton(label="Light Mode", variable=self.theme_choice_var, value="light", command=lambda: self._apply_theme("light"))
        theme_menu.add_radiobutton(label="Dark Mode", variable=self.theme_choice_var, value="dark", command=lambda: self._apply_theme("dark"))

    def _setup_top_frame(self):
        """Sets up the top frame containing the map display."""
        self.map_frame = tk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        self.map_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        self.map_text_widget = tk.Text(self.map_frame, font=self.console_font, wrap=tk.NONE, height=self.map_size[1] + 2, state=tk.DISABLED)
        self.map_text_widget.pack(padx=5, pady=5, anchor=tk.NW)
        self.map_text_widget.bind("<Button-1>", self._on_map_click)

    def _setup_bottom_frame(self):
        """Sets up the bottom frame containing the status label and game controls."""
        self.status_frame = tk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.status_label = tk.Label(self.status_frame, text="Status: Day 1 | Weather: Sunny", font=self.console_font)
        self.status_label.pack(side=tk.LEFT, padx=5, pady=5, anchor=tk.W)

        self.controls_frame = tk.Frame(self.status_frame)
        self.controls_frame.pack(side=tk.RIGHT, padx=5, pady=2)
        self.pause_button = tk.Button(self.controls_frame, text="Pause Sim", font=self.console_font, command=self._on_pause_sim_click)
        self.pause_button.pack(side=tk.LEFT, padx=(0,2))
        self.resume_button = tk.Button(self.controls_frame, text="Resume Sim", font=self.console_font, command=self._on_resume_sim_click)
        self.resume_button.pack(side=tk.LEFT, padx=(0,2))
        self.speed_button = tk.Button(self.controls_frame, text="Speed Up Day", font=self.console_font, command=self._on_speed_up_day_click)
        self.speed_button.pack(side=tk.LEFT, padx=(0,0))

    def _setup_middle_frame(self):
        """Sets up the middle content frame housing agent list, log, and details panel."""
        self.middle_content_frame = tk.Frame(self.root)
        self.middle_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=0)

        # Agent List Panel (Left)
        self.agent_list_frame = tk.Frame(self.middle_content_frame, width=200, relief=tk.SUNKEN, borderwidth=1)
        self.agent_list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0,5), pady=5)
        self.agent_list_label = tk.Label(self.agent_list_frame, text="--- Agents ---", font=self.console_font)
        self.agent_list_label.pack(padx=5,pady=5, fill=tk.X)
        self.agent_listbox = tk.Listbox(self.agent_list_frame, font=self.console_font, exportselection=False)
        self.agent_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.agent_list_scrollbar = tk.Scrollbar(self.agent_list_frame, orient=tk.VERTICAL, command=self.agent_listbox.yview)
        self.agent_listbox.config(yscrollcommand=self.agent_list_scrollbar.set)
        self.agent_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.agent_listbox.bind('<<ListboxSelect>>', self._on_agent_select)

        # Details Panel (Right) - Contains Agent Details and Suggestion Box
        self.agent_details_frame = tk.Frame(self.middle_content_frame, width=250, relief=tk.SUNKEN, borderwidth=1)
        self.agent_details_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0), pady=5)
        self.agent_details_frame.pack_propagate(False) # Prevent resizing due to content

        self.agent_details_label = tk.Label(self.agent_details_frame, text="--- Details ---", font=self.console_font)
        self.agent_details_label.pack(padx=5,pady=5, fill=tk.X)

        self.details_text_frame = tk.Frame(self.agent_details_frame)
        self.details_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0,5))
        self.agent_details_text = tk.Text(self.details_text_frame, wrap=tk.WORD, font=self.console_font, height=15)
        self.agent_details_scrollbar = tk.Scrollbar(self.details_text_frame, command=self.agent_details_text.yview)
        self.agent_details_text.config(yscrollcommand=self.agent_details_scrollbar.set)
        self.agent_details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.agent_details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.agent_details_text.config(state=tk.DISABLED)

        self.suggestion_frame = tk.Frame(self.agent_details_frame, relief=tk.RIDGE, borderwidth=1)
        self.suggestion_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.suggestion_label = tk.Label(self.suggestion_frame, text="Suggest New Village Need:", font=self.console_font)
        self.suggestion_label.pack(pady=(5,2))
        self.suggestion_entry = tk.Entry(self.suggestion_frame, font=self.console_font, width=28)
        self.suggestion_entry.pack(pady=(0,5), padx=5, fill=tk.X)
        self.suggest_button = tk.Button(self.suggestion_frame, text="Suggest Need", font=self.console_font, command=self._on_suggest_need_click)
        self.suggest_button.pack(pady=(0,5))

        # Log Panel (Center, fills remaining space)
        self.log_frame = tk.Frame(self.middle_content_frame)
        self.log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5) # Order matters for fill
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, font=self.console_font, height=20)
        self.log_text.insert(tk.END, "Welcome to the Village Chronicles!\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _init_themes(self):
        """Initializes theme dictionaries for light and dark modes."""
        self.themes = {
            "light": {
                "root_bg": "#ECECEC", "frame_bg": "#ECECEC", "text_fg": "black",
                "widget_bg": "white", "button_bg": "#DDDDDD", "button_fg": "black",
                "label_bg": "#ECECEC", "label_fg": "black",
                "log_bg": "black", "log_fg": "lightgreen",
                "map_bg": "lightgrey", "map_fg": "black",
                "details_frame_bg": "lightcyan", "details_text_bg": "black", "details_text_fg": "lightgray",
                "agent_list_frame_bg": "lightyellow", "listbox_bg": "white", "listbox_fg": "black",
                "listbox_select_bg": "#0078D7", "listbox_select_fg": "white",
                "status_frame_bg": "lightblue", "status_text_fg": "black",
                "controls_frame_bg": "lightblue",
                "suggestion_frame_bg": "lightcyan", "suggestion_entry_bg": "white", "suggestion_entry_fg": "black",
                "console_font_family": ["Segoe UI", "Calibri", "Helvetica", "Arial", "TkDefaultFont"],
                "console_font_size": 10
            },
            "dark": {
                "root_bg": "#2E2E2E", "frame_bg": "#2E2E2E", "text_fg": "#E0E0E0",
                "widget_bg": "#3C3C3C", "button_bg": "#505050", "button_fg": "#E0E0E0",
                "label_bg": "#2E2E2E", "label_fg": "#E0E0E0",
                "log_bg": "black", "log_fg": "lightgreen", # Keep log contrasty for now
                "map_bg": "#4A4A4A", "map_fg": "#E0E0E0",
                "details_frame_bg": "#3A4A4A", "details_text_bg": "#282828", "details_text_fg": "#D0D0D0",
                "agent_list_frame_bg": "#4A4A3A", "listbox_bg": "#3C3C3C", "listbox_fg": "#E0E0E0",
                "listbox_select_bg": "#0078D7", "listbox_select_fg": "white",
                "status_frame_bg": "#3A3A4A", "status_text_fg": "#E0E0E0",
                "controls_frame_bg": "#3A3A4A",
                "suggestion_frame_bg": "#3A4A4A", "suggestion_entry_bg": "#3C3C3C", "suggestion_entry_fg": "#E0E0E0",
                "console_font_family": ["Segoe UI", "Calibri", "Helvetica", "Arial", "TkDefaultFont"],
                "console_font_size": 10
            }
        }
        self.current_theme_name = "light"
        self.current_theme = self.themes[self.current_theme_name]

    def _init_font(self):
        """
        Initializes the primary console font based on the current theme's settings.
        It tries a list of preferred font families and falls back to defaults.
        """
        font_families = self.current_theme["console_font_family"]
        font_size = self.current_theme["console_font_size"]

        chosen_family = font_families[-1] # Default to TkDefaultFont or last in list
        available_fonts = list(font.families())
        for family_name in font_families:
            if family_name in available_fonts:
                chosen_family = family_name
                break

        self.console_font = font.Font(family=chosen_family, size=font_size)

    def _apply_theme(self, theme_name: str):
        """
        Applies the specified theme to all relevant UI elements.

        Args:
            theme_name: The name of the theme to apply (e.g., "light", "dark").
        """
        if theme_name not in self.themes:
            self.add_log_message(f"Warning: Theme '{theme_name}' not found.") # Log it
            return
        self.current_theme_name = theme_name
        self.current_theme = self.themes[theme_name]
        if hasattr(self, 'theme_choice_var'): # theme_choice_var might not exist if called before menu setup
            self.theme_choice_var.set(theme_name)

        # Re-initialize font as theme might change font settings
        self._init_font()
        ct = self.current_theme # Current theme shortcut

        # Apply colors to root and main frames
        self.root.config(bg=ct["root_bg"])
        self.map_frame.config(bg=ct["map_bg"])
        self.status_frame.config(bg=ct["status_frame_bg"])
        self.controls_frame.config(bg=ct["controls_frame_bg"]) # Part of status_frame
        self.middle_content_frame.config(bg=ct["frame_bg"])
        self.agent_list_frame.config(bg=ct["agent_list_frame_bg"])
        self.agent_details_frame.config(bg=ct["details_frame_bg"])
        self.details_text_frame.config(bg=ct["details_frame_bg"]) # Inherits from parent agent_details_frame
        self.suggestion_frame.config(bg=ct["suggestion_frame_bg"])
        self.log_frame.config(bg=ct["frame_bg"])

        # Labels
        self.status_label.config(bg=ct["status_frame_bg"], fg=ct["status_text_fg"], font=self.console_font)
        self.agent_list_label.config(bg=ct["agent_list_frame_bg"], fg=ct["text_fg"], font=self.console_font)
        self.agent_details_label.config(bg=ct["details_frame_bg"], fg=ct["text_fg"], font=self.console_font)
        self.suggestion_label.config(bg=ct["suggestion_frame_bg"], fg=ct["text_fg"], font=self.console_font)

        # Text Widgets
        self.map_text_widget.config(font=self.console_font, bg=ct["map_bg"], fg=ct["map_fg"])
        self.log_text.config(font=self.console_font, bg=ct["log_bg"], fg=ct["log_fg"])
        self.agent_details_text.config(font=self.console_font, bg=ct["details_text_bg"], fg=ct["details_text_fg"])

        # Listbox
        self.agent_listbox.config(font=self.console_font, bg=ct["listbox_bg"], fg=ct["listbox_fg"],
                                  selectbackground=ct["listbox_select_bg"], selectforeground=ct["listbox_select_fg"])

        # Entry
        self.suggestion_entry.config(font=self.console_font, bg=ct["suggestion_entry_bg"], fg=ct["suggestion_entry_fg"],
                                     relief=tk.FLAT, insertbackground=ct["text_fg"])

        # Buttons
        buttons = [self.pause_button, self.resume_button, self.speed_button, self.suggest_button]
        for btn in buttons:
            btn.config(font=self.console_font, bg=ct["button_bg"], fg=ct["button_fg"])
            try:
                btn.config(relief=tk.FLAT)
            except tk.TclError:
                pass # Some themes/platforms might not support all relief styles well for all buttons

        # Update fonts for any other widgets if their font was not set to self.console_font initially
        # or if a more granular font control per widget type is desired in themes.
        # For now, most widgets use self.console_font directly.

        self.root.update_idletasks() # Redraw UI with new theme

    def _on_agent_select(self, event: tk.Event):
        """
        Handles the selection of an agent in the agent listbox.
        Displays the selected agent's details in the details panel.

        Args:
            event: The Tkinter event object.
        """
        selected_indices = self.agent_listbox.curselection()
        if not selected_indices: # Nothing selected
            self.display_agent_details(None)
            return

        selected_index = selected_indices[0]
        selected_item_str = self.agent_listbox.get(selected_index)

        # Extract agent_id using regex, e.g., from "Elara (agent_001)"
        match = re.search(r'\((agent_\w+)\)$', selected_item_str)
        if not match:
            self.display_agent_details(None) # Clear details panel
            # Log error or show in UI if desired
            print(f"Error: Could not parse agent_id from listbox string: '{selected_item_str}'")
            return

        agent_id = match.group(1)
        agent_data = self.all_agents_data_cache.get(agent_id)
        self.display_agent_details(agent_data) # Display fetched data or None if not found

    def process_ui_queue(self):
        """
        Periodically processes messages from the update_queue.
        Updates UI elements based on message type and data.
        This method is scheduled to run via root.after().
        """
        try:
            while not self.update_queue.empty(): # Process all messages currently in queue
                message_item = self.update_queue.get_nowait()
                if isinstance(message_item, dict):
                    msg_type = message_item.get("type")
                    data = message_item.get("data")

                    if msg_type == "log":
                        self.add_log_message(str(data))
                    elif msg_type == "status_update":
                        self.update_status(data)
                    elif msg_type == "map_update":
                        self.update_map(data)
                    elif msg_type == "agent_list_update":
                        self.update_agent_list(data)
                    elif msg_type == "new_village_need":
                        # Placeholder: confirm UI received and "sent" it
                        self.add_log_message(f"UI: Suggestion '{data.get('text', '')}' forwarded to simulation.")
                    elif msg_type == "sim_control":
                        # Placeholder: confirm UI received and "sent" it
                        action = data.get('action', 'unknown_action')
                        self.add_log_message(f"UI: Sim control command '{action}' forwarded to simulation.")
                    elif msg_type == "clear_log":
                        self.log_text.config(state=tk.NORMAL)
                        self.log_text.delete(1.0, tk.END)
                        self.log_text.config(state=tk.DISABLED)
                    else:
                        self.add_log_message(f"UI: Received unknown message type '{msg_type}'.")
                else:
                    # Handle non-dict messages if any are expected
                    self.add_log_message(str(message_item))

                self.update_queue.task_done() # Signal that the task from queue is done
        except queue.Empty:
            pass # No messages to process
        except Exception as e:
            print(f"Error processing UI queue: {e}") # Print to console for debugging
            self.add_log_message(f"Error in UI queue: {e}") # Also log to UI if possible
        finally:
            self.root.after(100, self.process_ui_queue) # Reschedule polling

    def _on_suggest_need_click(self):
        """Handles the 'Suggest Need' button click.
        Sends the suggestion from the entry field to the simulation queue.
        """
        suggestion_text = self.suggestion_entry.get().strip()
        if suggestion_text:
            message = {"type": "new_village_need", "data": {"text": suggestion_text}}
            self.update_queue.put(message)
            self.add_log_message(f"UI: Suggestion '{suggestion_text}' sent.")
            self.suggestion_entry.delete(0, tk.END) # Clear field after sending
        else:
            self.add_log_message("UI: Suggestion cannot be empty.") # User feedback

    def _on_pause_sim_click(self):
        """Handles the 'Pause Sim' button click. Sends a pause command."""
        message = {"type": "sim_control", "data": {"action": "pause"}}
        self.update_queue.put(message)
        self.add_log_message("UI: Pause Simulation command sent.")

    def _on_resume_sim_click(self):
        """Handles the 'Resume Sim' button click. Sends a resume command."""
        message = {"type": "sim_control", "data": {"action": "resume"}}
        self.update_queue.put(message)
        self.add_log_message("UI: Resume Simulation command sent.")

    def _on_speed_up_day_click(self):
        """Handles the 'Speed Up Day' button click. Sends a speed_up command."""
        message = {"type": "sim_control", "data": {"action": "speed_up"}}
        self.update_queue.put(message)
        self.add_log_message("UI: Speed Up Day command sent.")

    def update_agent_list(self, agents_data: dict):
        """
        Updates the agent listbox with new agent data.
        Preserves selection if possible.

        Args:
            agents_data: A dictionary where keys are agent_ids and values are
                         dictionaries of agent information.
        """
        if not isinstance(agents_data, dict):
            self.add_log_message("Error: Invalid agent data for list update.")
            return

        self.all_agents_data_cache = agents_data # Update cache

        # Try to preserve selection
        selected_agent_id = None
        current_selection_indices = self.agent_listbox.curselection()
        if current_selection_indices:
            selected_item_str = self.agent_listbox.get(current_selection_indices[0])
            match = re.search(r'\((agent_\w+)\)$', selected_item_str)
            if match:
                selected_agent_id = match.group(1)

        self.agent_listbox.delete(0, tk.END) # Clear existing list

        new_selection_index = None
        for idx, (agent_id, agent_info) in enumerate(agents_data.items()):
            display_name = agent_info.get('name', 'Unknown Agent')
            health = agent_info.get('status', {}).get('health', 0)
            if health <= 0:
                display_name += " (Deceased)"

            list_entry = f"{display_name} ({agent_id})"
            self.agent_listbox.insert(tk.END, list_entry)

            if agent_id == selected_agent_id:
                new_selection_index = idx # Mark index for re-selection

        if new_selection_index is not None:
            self.agent_listbox.select_set(new_selection_index)
            self.agent_listbox.activate(new_selection_index) # Make sure it's visible
        elif self.agent_listbox.size() > 0 and not self.agent_listbox.curselection():
            # If nothing was re-selected (e.g. previous selection gone) and list not empty, select first.
            self.agent_listbox.select_set(0)
            self.agent_listbox.activate(0)
            # Manually trigger detail update for the newly selected first item
            self._on_agent_select(None) # Pass None as event, handler should cope or be adapted

        self.root.update_idletasks() # Ensure UI updates promptly

    def display_agent_details(self, agent_data: dict = None):
        """
        Displays the details of a given agent in the agent details text area.
        If agent_data is None, it shows a 'no agent selected' message.

        Args:
            agent_data: A dictionary containing the agent's details, or None.
        """
        self.agent_details_text.config(state=tk.NORMAL) # Enable editing
        self.agent_details_text.delete(1.0, tk.END)   # Clear current content

        if not agent_data: # No agent data provided or agent not found
            self.agent_details_text.insert(tk.END, "No agent selected or details unavailable.")
        elif isinstance(agent_data, dict) and "error" in agent_data: # Handle error messages
             self.agent_details_text.insert(tk.END, f"Error: {agent_data['error']}")
        elif isinstance(agent_data, dict):
            # Construct details string from agent_data
            details = []
            details.append(f"Name: {agent_data.get('name', 'N/A')} (ID: {agent_data.get('agent_id', 'N/A')})")

            status = agent_data.get('status', {})
            details.append(f"Status: H:{status.get('health',0)} E:{status.get('energy',0)} Hunger:{status.get('hunger',0)}")
            details.append(f"Shelter Lvl: {agent_data.get('shelter_level', 0)}")

            details.append("\nSkills:")
            skills = agent_data.get('skills', {})
            details.extend([f"  - {k.capitalize()}: {v}" for k, v in skills.items()] if skills else ["  - None"])

            details.append("\nPersonality Traits:")
            traits = agent_data.get('personality_traits', [])
            details.append(f"  {', '.join(traits) if traits else '  - None'}")

            details.append("\nInventory (Crafted/Tools):")
            inventory = agent_data.get('inventory', {})
            details.extend([f"  - {k.replace('_',' ').capitalize()}: {v}" for k, v in inventory.items() if v > 0] if inventory else ["  - Empty"])

            details.append("\nPersonal Resources (Raw Materials):")
            personal_resources = agent_data.get('personal_resources', {})
            details.extend([f"  - {k.replace('_',' ').capitalize()}: {v}" for k, v in personal_resources.items() if v > 0] if personal_resources else ["  - Empty"])

            details.append("\nRecent Memory (last 5):")
            memory_log = agent_data.get('memory_log', [])
            details.extend([f"  - {entry}" for entry in memory_log[-5:]] if memory_log else ["  - None"])

            current_focus = agent_data.get('current_focus_need_id')
            if current_focus:
                details.append(f"\nCurrent Focus ID: {current_focus}")

            self.agent_details_text.insert(tk.END, "\n".join(details))
        else: # Fallback for unexpected data type
            self.agent_details_text.insert(tk.END, "Invalid data format for agent details.")

        self.agent_details_text.config(state=tk.DISABLED) # Disable editing
        self.root.update_idletasks() # Ensure UI updates promptly

    def update_map(self, world_data: dict):
        """
        Updates the map display with resources, buildings, and agents
        from the provided world_data.

        Args:
            world_data: A dictionary containing map elements and other world state.
        """
        map_width, map_height = self.map_size
        self.clickable_map_elements.clear() # Clear previous clickable elements
        grid = [['.' for _ in range(map_width)] for _ in range(map_height)]

        if not isinstance(world_data, dict) or "map_elements" not in world_data:
            error_map_string = "Error: Invalid world data for map display."
            # Update map text widget with error
            self.map_text_widget.config(state=tk.NORMAL)
            self.map_text_widget.delete(1.0, tk.END)
            self.map_text_widget.insert(tk.END, error_map_string)
            self.map_text_widget.config(state=tk.DISABLED)
            return

        map_elements = world_data.get("map_elements", {})

        # Helper to reduce redundancy in adding clickable elements
        def _add_clickable_element(item_type, data, x_key='x', y_key='y', symbol_key='symbol', id_prefix=''):
            x, y = data.get(x_key), data.get(y_key)
            symbol = data.get(symbol_key)
            item_id = data.get('agent_id') if item_type == 'agent' else id_prefix + data.get('type', 'unknown') + f"_at_{x}_{y}"

            if x is not None and y is not None and symbol is not None and \
               0 <= x < map_width and 0 <= y < map_height:
                grid[y][x] = symbol
                self.clickable_map_elements.append({
                    'x': x, 'y': y, 'id': item_id, 'type': item_type,
                    'symbol': symbol, 'raw_data': data
                })

        # Place resources, buildings, and agents
        for resource_info in map_elements.get("resources", []):
            _add_clickable_element('resource', resource_info)
        for building_info in map_elements.get("buildings", []):
            _add_clickable_element('building', building_info)
        for agent_map_data in map_elements.get("agents", []):
            _add_clickable_element('agent', agent_map_data)

        # Convert grid to display string
        map_lines = ["~ Village Map ~"] # Header for the map
        for row_idx in range(map_height):
            display_row_chars = [f"{str(grid[row_idx][col_idx]):^3}" for col_idx in range(map_width)]
            map_lines.append("".join(display_row_chars))

        map_lines.append("=" * (map_width * 3)) # Footer separator
        map_display_string = "\n".join(map_lines)

        # Update the map text widget
        self.map_text_widget.config(state=tk.NORMAL)
        self.map_text_widget.delete(1.0, tk.END)
        self.map_text_widget.insert(tk.END, map_display_string)
        self.map_text_widget.config(state=tk.DISABLED)
        self.root.update_idletasks() # Ensure UI updates promptly

    def _on_map_click(self, event: tk.Event):
        """
        Handles clicks on the map text widget.
        Determines the clicked grid cell and displays details for any element there.

        Args:
            event: The Tkinter event object.
        """
        # Convert click coordinates to text index (e.g., "line.char")
        # Tkinter text index is 1-based for lines, 0-based for characters.
        text_index_str = self.map_text_widget.index(f"@{event.x},{event.y}")
        try:
            line_str, char_pos_str = text_index_str.split('.')
            clicked_line_num = int(line_str)    # 1-based line number in Text widget
            clicked_char_pos = int(char_pos_str)  # 0-based char position on that line
        except ValueError:
            self.add_log_message(f"UI Error: Could not parse map click index: {text_index_str}")
            return

        # Convert Text widget line/char to map grid row/col (0-indexed)
        # Line 1 of map_text_widget is "~ Village Map ~" (header)
        # Grid content starts from line 2.
        grid_row = clicked_line_num - 2
        grid_col = clicked_char_pos // 3 # Each map cell is 3 characters wide (e.g., " F ")

        # Validate if the click is within the actual map grid boundaries
        if not (0 <= grid_row < self.map_size[1] and 0 <= grid_col < self.map_size[0]):
            # self.add_log_message(f"Clicked outside map grid area (Text line {clicked_line_num}, char {clicked_char_pos} -> Grid {grid_row},{grid_col}).")
            return # Click was on header, footer, or padding

        # Find if any element matches the clicked grid coordinates
        clicked_element = None
        for element in self.clickable_map_elements:
            if element['x'] == grid_col and element['y'] == grid_row:
                clicked_element = element
                break

        if clicked_element:
            elem_type = clicked_element['type']
            elem_id = clicked_element['id'] # For agents, this is agent_id

            if elem_type == 'agent':
                agent_full_data = self.all_agents_data_cache.get(elem_id)
                if agent_full_data:
                    self.display_agent_details(agent_full_data)
                    # Sync selection with agent listbox
                    for i in range(self.agent_listbox.size()):
                        if elem_id in self.agent_listbox.get(i): # Check if agent_id is in listbox item string
                            self.agent_listbox.selection_clear(0, tk.END)
                            self.agent_listbox.select_set(i)
                            self.agent_listbox.activate(i) # Ensure it's visible
                            break
                else: # Agent ID from map not found in cache
                    self.display_agent_details({"error": f"Agent {elem_id} details not found in cache."})

            elif elem_type in ['building', 'resource']:
                # Display basic info for buildings/resources in the details panel
                display_details = [
                    f"Type: {elem_type.capitalize()}",
                    f"Symbol: {clicked_element['symbol']}",
                    f"Location: ({clicked_element['x']}, {clicked_element['y']})"
                ]
                # Add more specific details from raw_data if needed
                raw_data = clicked_element['raw_data']
                for key, value in raw_data.items():
                    if key not in ['x', 'y', 'symbol', 'type', 'agent_id']: # Avoid redundant info
                         display_details.append(f"{key.replace('_',' ').capitalize()}: {value}")

                self.agent_details_text.config(state=tk.NORMAL)
                self.agent_details_text.delete(1.0, tk.END)
                self.agent_details_text.insert(tk.END, "\n".join(display_details))
                self.agent_details_text.config(state=tk.DISABLED)
            else: # Should not happen if clickable_map_elements is correctly populated
                self.display_agent_details({"error": f"Unknown element type '{elem_type}' clicked on map."})
        # else:
            # self.add_log_message(f"No specific element found at map grid ({grid_col},{grid_row}).")


    def add_log_message(self, message: str):
        """
        Adds a message to the log text area.

        Args:
            message: The string message to add.
        """
        if not hasattr(self, 'log_text'): return # UI not fully initialized
        self.log_text.config(state=tk.NORMAL) # Enable editing
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END) # Scroll to the end
        self.log_text.config(state=tk.DISABLED) # Disable editing
        self.root.update_idletasks() # Ensure UI updates, use sparingly if performance issues arise

    def update_status(self, world_data: dict):
        """
        Updates the status bar with current world data (day, season, weather, resources).

        Args:
            world_data: A dictionary containing current world status information.
        """
        if not isinstance(world_data, dict):
            self.status_label.config(text="Status: Error loading world data.")
            self.root.update_idletasks()
            return

        day = world_data.get('day', '?')
        season = world_data.get('season', 'Unknown Season')
        weather = world_data.get('weather', 'Unknown Weather')

        village_resources = world_data.get('village_resources', {})
        if not isinstance(village_resources, dict):
            village_resources = {} # Ensure it's a dict to prevent errors with .get()

        food = village_resources.get('food', 0)
        wood = village_resources.get('wood', 0)
        stone = village_resources.get('stone', 0)
        herbs = village_resources.get('herbs', 0)

        status_string = f"Day: {day} ({season}) | Weather: {weather} | Food: {food}, Wood: {wood}, Stone: {stone}, Herbs: {herbs}"
        self.status_label.config(text=status_string)
        self.root.update_idletasks() # Ensure UI updates

if __name__ == '__main__':
    # This block is for testing the UI independently of the main simulation engine.
    test_queue = queue.Queue()
    root = tk.Tk()
    app = VillageUI(root, test_queue)
    root.geometry("1200x700")

    sample_agents_for_ui = {
        "agent_001": {"agent_id": "agent_001", "name": "Elara", "shelter_level": 1, "status": {"health": 100, "energy": 80, "hunger": 20}, "skills": {"gathering": 3, "healing": 2}, "personality_traits": ["cautious", "kind"], "inventory": {"food_rations":1}, "personal_resources": {"herbs_bundle":2}, "memory_log": ["Found some berries.", "Spoke to Gorok."]},
        "agent_002": {"agent_id": "agent_002", "name": "Gorok", "shelter_level": 2, "status": {"health": 0, "energy": 0, "hunger": 100}, "skills": {"building": 4}, "personality_traits": ["strong", "gruff"], "inventory": {"stone_axe":1}, "personal_resources": {}, "memory_log": ["Shelter improved.", "Felt weak."]},
        "agent_003": {"agent_id": "agent_003", "name": "Mira", "shelter_level": 0, "status": {"health": 50, "energy": 60, "hunger": 40}, "skills": {"hunting": 1}, "personality_traits": ["quiet"], "inventory": {}, "personal_resources": {"food_rations":1}, "memory_log": ["Scouted the area."]},
    }

    test_queue.put({"type": "agent_list_update", "data": sample_agents_for_ui})
    # test_queue.put({"type": "map_update", "data": sample_agents_for_ui}) # Old map update

    sample_world_data_for_map = {
        "day": 1, "season": "Spring", "weather": "Sunny",
        "village_resources": {"food": 10, "wood": 5, "stone": 2, "herbs": 3}, # For status bar
        "map_elements": {
            "resources": [
                {"type": "food", "x": 2, "y": 3, "symbol": "F"},
                {"type": "wood", "x": 5, "y": 7, "symbol": "W"},
                {"type": "stone", "x": 8, "y": 1, "symbol": "S"}
            ],
            "buildings": [
                {"type": "shelter", "owner": "agent_001", "x": 1, "y": 1, "level": 1, "symbol": "^"},
                {"type": "storehouse", "x": 4, "y": 4, "symbol": "St"},
                {"type": "workshop", "x": 6, "y": 2, "symbol": "Ws"}
            ],
            "agents": [
                 {"agent_id": "agent_001", "name": "Elara", "x": 1, "y": 1, "symbol": "E1"},
                 {"agent_id": "agent_002", "name": "Gorok", "x": 3, "y": 5, "symbol": "G2"},
                 {"agent_id": "agent_003", "name": "Mira", "x": 0, "y": 0, "symbol": "M3"},
            ]
        },
        "agents_data": sample_agents_for_ui # If other parts of UI still need this structure separately
    }
    test_queue.put({"type": "map_update", "data": sample_world_data_for_map})
    test_queue.put({"type": "log", "data": "Test Log: UI Initialized. Click agent in list to see details."})

    # sample_world_data_for_status is effectively part of sample_world_data_for_map now for status line
    test_queue.put({"type": "status_update", "data": sample_world_data_for_map})


    # No direct call to display_agent_details needed here, selection will trigger it.
    # If you want an agent selected by default, you could add logic to `update_agent_list`
    # to select the first item and call _on_agent_select.

    root.mainloop()
