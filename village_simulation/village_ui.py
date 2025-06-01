import tkinter as tk
from tkinter import scrolledtext, font
import queue
import re # Added for parsing agent_id

class VillageUI:
    def __init__(self, root, update_queue):
        self.root = root
        self.update_queue = update_queue
        self.root.title("Primitive Village Chronicles")
        self.all_agents_data_cache = {}

        try:
            self.console_font = font.Font(family="Courier New", size=10)
        except tk.TclError:
            try: self.console_font = font.Font(family="Consolas", size=10)
            except tk.TclError:
                try: self.console_font = font.Font(family="Monaco", size=10)
                except tk.TclError:
                    try: self.console_font = font.Font(family="Liberation Mono", size=10)
                    except tk.TclError: self.console_font = ("TkFixedFont", 10)

        self.map_frame = tk.Frame(self.root, bg='lightgrey', relief=tk.SUNKEN, borderwidth=1)
        self.map_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        self.map_label = tk.Label(self.map_frame, text="--- Village Map Area ---", font=self.console_font, bg='lightgrey', justify=tk.LEFT)
        self.map_label.pack(padx=5, pady=5, anchor=tk.NW)

        self.status_frame = tk.Frame(self.root, bg='lightblue', relief=tk.SUNKEN, borderwidth=1)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.status_label = tk.Label(self.status_frame, text="Status: Day 1 | Weather: Sunny", font=self.console_font, bg='lightblue')
        self.status_label.pack(padx=5, pady=5, anchor=tk.W)

        self.middle_content_frame = tk.Frame(self.root)
        self.middle_content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=0)

        # Agent List Frame
        self.agent_list_frame = tk.Frame(self.middle_content_frame, width=200, bg='lightyellow', relief=tk.SUNKEN, borderwidth=1)
        self.agent_list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0,5), pady=5)
        tk.Label(self.agent_list_frame, text="--- Agents ---", font=self.console_font, bg='lightyellow').pack(padx=5,pady=5, fill=tk.X)

        self.agent_listbox = tk.Listbox(self.agent_list_frame, font=self.console_font, exportselection=False)
        self.agent_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        agent_list_scrollbar = tk.Scrollbar(self.agent_list_frame, orient=tk.VERTICAL, command=self.agent_listbox.yview)
        self.agent_listbox.config(yscrollcommand=agent_list_scrollbar.set)
        agent_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.agent_listbox.bind('<<ListboxSelect>>', self._on_agent_select) # Bind event

        # Agent Details Frame
        self.agent_details_frame = tk.Frame(self.middle_content_frame, width=250, bg='lightcyan', relief=tk.SUNKEN, borderwidth=1)
        self.agent_details_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0), pady=5)
        self.agent_details_frame.pack_propagate(False)
        tk.Label(self.agent_details_frame, text="--- Details ---", font=self.console_font, bg='lightcyan').pack(padx=5,pady=5, fill=tk.X)

        details_text_frame = tk.Frame(self.agent_details_frame)
        details_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0,5))
        self.agent_details_text = tk.Text(details_text_frame, wrap=tk.WORD, font=self.console_font, bg='black', fg='lightgray')
        agent_details_scrollbar = tk.Scrollbar(details_text_frame, orient=tk.VERTICAL, command=self.agent_details_text.yview)
        self.agent_details_text.config(yscrollcommand=agent_details_scrollbar.set)
        agent_details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.agent_details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.agent_details_text.config(state=tk.DISABLED)

        # Log Frame
        self.log_frame = tk.Frame(self.middle_content_frame)
        self.log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, font=self.console_font, height=20, bg='black', fg='lightgreen')
        self.log_text.insert(tk.END, "Welcome to the Village Chronicles!\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.root.after(100, self.process_ui_queue)

    def _on_agent_select(self, event):
        # Check if the event widget is the listbox itself (not strictly necessary with direct binding but good practice)
        # widget = event.widget
        selected_indices = self.agent_listbox.curselection()

        if not selected_indices:
            self.display_agent_details(None)
            return

        selected_index = selected_indices[0]
        selected_item_str = self.agent_listbox.get(selected_index)

        # Extract agent_id using regex: Assumes format "Display Name (agent_id)"
        match = re.search(r'\((agent_\w+)\)$', selected_item_str) # \w+ allows for alphanumeric agent_ids
        if not match:
            self.display_agent_details(None)
            print(f"Error: Could not parse agent_id from listbox string: {selected_item_str}")
            return

        agent_id = match.group(1)
        agent_data = self.all_agents_data_cache.get(agent_id)
        self.display_agent_details(agent_data)

    def process_ui_queue(self):
        try:
            while True:
                message_item = self.update_queue.get_nowait()
                if isinstance(message_item, dict):
                    msg_type = message_item.get("type")
                    data = message_item.get("data")
                    if msg_type == "log": self.add_log_message(str(data))
                    elif msg_type == "status_update": self.update_status(data)
                    elif msg_type == "map_update": self.update_map(data)
                    elif msg_type == "agent_list_update": self.update_agent_list(data)
                    elif msg_type == "clear_log":
                        self.log_text.config(state=tk.NORMAL); self.log_text.delete(1.0, tk.END)
                        self.log_text.config(state=tk.DISABLED)
                else: self.add_log_message(str(message_item))
                self.update_queue.task_done()
        except queue.Empty: pass
        except Exception as e: print(f"Error processing UI queue: {e}")
        finally: self.root.after(100, self.process_ui_queue)

    def update_agent_list(self, agents_data: dict):
        self.all_agents_data_cache = agents_data
        current_selection = self.agent_listbox.curselection() # Preserve selection if possible
        selected_agent_id = None
        if current_selection:
            selected_item_str = self.agent_listbox.get(current_selection[0])
            match = re.search(r'\((agent_\w+)\)$', selected_item_str)
            if match: selected_agent_id = match.group(1)

        self.agent_listbox.delete(0, tk.END)
        new_selection_index = None
        idx_counter = 0
        if isinstance(agents_data, dict):
            for agent_id, agent_info in agents_data.items():
                display_name = agent_info.get('name', 'Unknown')
                health = agent_info.get('status', {}).get('health', 0)
                if health <= 0: display_name += " (Deceased)"
                list_entry = f"{display_name} ({agent_id})"
                self.agent_listbox.insert(tk.END, list_entry)
                if agent_id == selected_agent_id:
                    new_selection_index = idx_counter
                idx_counter +=1

        if new_selection_index is not None: # Re-select if previously selected item still exists
            self.agent_listbox.select_set(new_selection_index)
            self.agent_listbox.activate(new_selection_index) # Ensure it's visible if scrolled
            # Optionally, call _on_agent_select manually if needed, but selection should trigger it.
            # self._on_agent_select(None) # Or create a dummy event
        elif not self.agent_listbox.curselection() and self.agent_listbox.size() > 0:
            # If nothing is selected and list is not empty, select first item and show details
            self.agent_listbox.select_set(0)
            self.agent_listbox.activate(0)
            self._on_agent_select(None) # Manually trigger detail update for the first item

        self.root.update_idletasks()

    def display_agent_details(self, agent_data: dict = None):
        self.agent_details_text.config(state=tk.NORMAL)
        self.agent_details_text.delete(1.0, tk.END)
        if not agent_data:
            self.agent_details_text.insert(tk.END, "No agent selected or details unavailable.")
        else:
            details_str = []
            details_str.append(f"Name: {agent_data.get('name', 'N/A')} (ID: {agent_data.get('agent_id', 'N/A')})")
            status = agent_data.get('status', {})
            details_str.append(f"Status: H:{status.get('health',0)} E:{status.get('energy',0)} Hunger:{status.get('hunger',0)}")
            details_str.append(f"Shelter Lvl: {agent_data.get('shelter_level', 0)}")
            details_str.append("\nSkills:")
            skills = agent_data.get('skills', {})
            skill_items = [f"  - {k.capitalize()}: {v}" for k, v in skills.items()] if skills else ["  - None"]
            details_str.extend(skill_items if skill_items else ["  - None listed"])
            details_str.append("\nPersonality Traits:")
            traits = agent_data.get('personality_traits', [])
            details_str.append(f"  {', '.join(traits) if traits else '  - None'}")
            details_str.append("\nInventory (Crafted/Tools):")
            inventory = agent_data.get('inventory', {})
            inv_items = [f"  - {k.replace('_',' ').capitalize()}: {v}" for k, v in inventory.items() if v > 0] if inventory else []
            details_str.extend(inv_items if inv_items else ["  - Empty"])
            details_str.append("\nPersonal Resources (Raw Materials):")
            personal_resources = agent_data.get('personal_resources', {})
            res_items = [f"  - {k.replace('_',' ').capitalize()}: {v}" for k, v in personal_resources.items() if v > 0] if personal_resources else []
            details_str.extend(res_items if res_items else ["  - Empty"])
            details_str.append("\nRecent Memory (last 5):")
            memory_log = agent_data.get('memory_log', [])
            mem_items = [f"  - {entry}" for entry in memory_log[-5:]] if memory_log else ["  - None"]
            details_str.extend(mem_items)
            current_focus = agent_data.get('current_focus_need_id', None)
            if current_focus: details_str.append(f"\nCurrent Focus ID: {current_focus}")
            self.agent_details_text.insert(tk.END, "\n".join(details_str))
        self.agent_details_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def update_map(self, all_agents_data):
        shelter_chars = {0: 'o', 1: '^', 2: 'H', 3: 'B', 4: 'W'}
        map_lines = ["~ Villager Shelters ~"]
        agent_initials_line, shelter_chars_line = [], []
        if not isinstance(all_agents_data, dict):
            self.map_label.config(text="Error: Invalid agent data for map."); return
        agents_to_display = list(all_agents_data.values())[:20]
        for agent in agents_to_display:
            if not isinstance(agent, dict): initials, shelter_char = "??", "?"
            else:
                initials = agent.get('name', '??')[:2].ljust(2)
                shelter_level = agent.get('shelter_level', 0)
                shelter_char = shelter_chars.get(shelter_level, '?')
            agent_initials_line.append(initials)
            shelter_chars_line.append(f" {shelter_char}")
        grid_width = 10
        for i in range(0, len(agents_to_display), grid_width):
            map_lines.append("  ".join(agent_initials_line[i:i+grid_width]))
            map_lines.append("  ".join(shelter_chars_line[i:i+grid_width]))
            if i + grid_width < len(agents_to_display): map_lines.append("-" * (grid_width * 4))
        map_lines.append("\n" + ("="*30))
        self.map_label.config(text="\n".join(map_lines))
        self.root.update_idletasks()

    def add_log_message(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def update_status(self, world_data: dict):
        if not isinstance(world_data, dict):
            self.status_label.config(text="Status: Error loading world data."); self.root.update_idletasks(); return
        day = world_data.get('day', '?'); season = world_data.get('season', 'Unknown'); weather = world_data.get('weather', 'Unknown')
        village_resources = world_data.get('village_resources', {})
        if not isinstance(village_resources, dict): village_resources = {}
        food = village_resources.get('food', 0); wood = village_resources.get('wood', 0); stone = village_resources.get('stone', 0); herbs = village_resources.get('herbs', 0)
        status_string = f"Day: {day} ({season}) | Weather: {weather} | Food: {food}, Wood: {wood}, Stone: {stone}, Herbs: {herbs}"
        self.status_label.config(text=status_string)
        self.root.update_idletasks()

if __name__ == '__main__':
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
    test_queue.put({"type": "map_update", "data": sample_agents_for_ui})
    test_queue.put({"type": "log", "data": "Test Log: UI Initialized. Click agent in list to see details."})

    sample_world_data_for_status = { "day": 1, "season": "Spring", "weather": "Sunny", "village_resources": {"food": 10, "wood": 5, "stone": 2, "herbs": 3} }
    test_queue.put({"type": "status_update", "data": sample_world_data_for_status})

    # No direct call to display_agent_details needed here, selection will trigger it.
    # If you want an agent selected by default, you could add logic to `update_agent_list`
    # to select the first item and call _on_agent_select.

    root.mainloop()
