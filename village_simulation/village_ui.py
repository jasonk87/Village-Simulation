import tkinter as tk
from tkinter import scrolledtext, font
import queue # Added import

class VillageUI:
    def __init__(self, root, update_queue): # Added update_queue parameter
        self.root = root
        self.update_queue = update_queue # Store the queue
        self.root.title("Primitive Village Chronicles")

        try:
            self.console_font = font.Font(family="Courier New", size=10)
        except tk.TclError:
            try:
                self.console_font = font.Font(family="Consolas", size=10)
            except tk.TclError:
                try:
                    self.console_font = font.Font(family="Monaco", size=10)
                except tk.TclError:
                    try:
                        self.console_font = font.Font(family="Liberation Mono", size=10)
                    except tk.TclError:
                        self.console_font = ("TkFixedFont", 10)

        self.map_frame = tk.Frame(self.root, bg='lightgrey', relief=tk.SUNKEN, borderwidth=1)
        self.map_frame.pack(fill=tk.X, padx=5, pady=5)
        self.map_label = tk.Label(self.map_frame, text="--- Village Map Area ---", font=self.console_font, bg='lightgrey', justify=tk.LEFT)
        self.map_label.pack(padx=5, pady=5, anchor=tk.NW)

        self.log_frame = tk.Frame(self.root)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, font=self.console_font, height=20, bg='black', fg='lightgreen')
        self.log_text.insert(tk.END, "Welcome to the Village Chronicles!\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.status_frame = tk.Frame(self.root, bg='lightblue', relief=tk.SUNKEN, borderwidth=1)
        self.status_frame.pack(fill=tk.X, padx=5, pady=5)
        self.status_label = tk.Label(self.status_frame, text="Status: Day 1 | Weather: Sunny", font=self.console_font, bg='lightblue')
        self.status_label.pack(padx=5, pady=5, anchor=tk.W)

        self.root.after(100, self.process_ui_queue) # Schedule first queue check

    def process_ui_queue(self):
        try:
            while True: # Process all messages currently in queue
                message_item = self.update_queue.get_nowait()
                if isinstance(message_item, dict):
                    msg_type = message_item.get("type")
                    data = message_item.get("data")
                    if msg_type == "log":
                        self.add_log_message(str(data))
                    elif msg_type == "status_update":
                        self.update_status(data) # data is world_data
                    elif msg_type == "map_update":
                        self.update_map(data) # data is all_agents_data
                    elif msg_type == "clear_log":
                        self.log_text.config(state=tk.NORMAL)
                        self.log_text.delete(1.0, tk.END)
                        # self.log_text.insert(tk.END, "Log cleared by new session.\n") # Optional: add a message
                        self.log_text.config(state=tk.DISABLED)
                    # Add more message types as needed (e.g., "game_over", "ask_input")
                else: # Assume it's a simple log message string
                    self.add_log_message(str(message_item))
                self.update_queue.task_done() # Signal task completion for each processed item
        except queue.Empty:
            pass # No messages in queue, normal situation
        except Exception as e:
            # Log error to console or a file if UI's own log is problematic
            print(f"Error processing UI queue: {e}")
        finally:
            self.root.after(100, self.process_ui_queue) # Schedule next check

    def update_map(self, all_agents_data):
        shelter_chars = {0: 'o', 1: '^', 2: 'H', 3: 'B', 4: 'W'}
        map_lines = ["~ Villager Shelters ~"]
        agent_initials_line, shelter_chars_line = [], []

        if not isinstance(all_agents_data, dict):
            self.map_label.config(text="Error: Invalid agent data for map.")
            return

        agents_to_display = list(all_agents_data.values())[:20]

        for agent in agents_to_display:
            if not isinstance(agent, dict):
                initials, shelter_char = "??", "?"
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
            if i + grid_width < len(agents_to_display):
                 map_lines.append("-" * (grid_width * 4))
        map_lines.append("\n" + ("="*30))
        self.map_label.config(text="\n".join(map_lines))
        self.root.update_idletasks() # Ensure map updates visually

    def add_log_message(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def update_status(self, world_data: dict):
        if not isinstance(world_data, dict):
            self.status_label.config(text="Status: Error loading world data.")
            self.root.update_idletasks()
            return

        day = world_data.get('day', '?')
        season = world_data.get('season', 'Unknown Season')
        weather = world_data.get('weather', 'Unknown Weather')
        village_resources = world_data.get('village_resources', {})
        if not isinstance(village_resources, dict): village_resources = {}

        food = village_resources.get('food', 0)
        wood = village_resources.get('wood', 0)
        stone = village_resources.get('stone', 0)
        herbs = village_resources.get('herbs', 0)
        status_string = f"Day: {day} ({season}) | Weather: {weather} | Food: {food}, Wood: {wood}, Stone: {stone}, Herbs: {herbs}"
        self.status_label.config(text=status_string)
        self.root.update_idletasks()

if __name__ == '__main__':
    # This __main__ block is for testing village_ui.py independently.
    # The actual game will run from main.py.
    test_queue = queue.Queue()
    root = tk.Tk()
    app = VillageUI(root, test_queue) # Pass the test queue
    root.geometry("800x600")

    # Simulate putting messages into the queue for testing
    sample_agents_for_map = {
        "agent_001": {"name": "Elara", "shelter_level": 1}, "agent_002": {"name": "Gorok", "shelter_level": 2},
        "agent_003": {"name": "Mira", "shelter_level": 0}
    }
    test_queue.put({"type": "map_update", "data": sample_agents_for_map})
    test_queue.put({"type": "log", "data": "Test Log: UI Initialized."})

    sample_world_data_for_status = {
        "day": 1, "season": "Spring", "weather": "Sunny",
        "village_resources": {"food": 10, "wood": 5, "stone": 2, "herbs": 3}
    }
    test_queue.put({"type": "status_update", "data": sample_world_data_for_status})

    def add_more_test_messages():
        test_queue.put({"type": "log", "data": "Test Log: Another message after 2 seconds."})
        sample_world_data_for_status["day"] = 2
        sample_world_data_for_status["village_resources"]["food"] += 5
        test_queue.put({"type": "status_update", "data": sample_world_data_for_status.copy()})
        app.add_log_message("Direct call to add_log_message for testing.") # Test direct call too
    root.after(2000, add_more_test_messages) # Add more messages after 2 seconds

    root.mainloop()
