# world_manager.py
# Manages the simulation's world state, daily updates, saving, and loading.

import json
import os
import random
import config # Import the configuration
import game_utils # Import game_utils for status description

def initialize_new_world():
    """
    Creates a brand new world_state dictionary for a new game.
    """
    return {
        "day": 1,
        "season": "Spring", # TODO: Implement seasons later
        "weather": "Mild",
        "village_resources": config.INITIAL_VILLAGE_RESOURCES.copy(),
        "active_needs": [need.copy() for need in config.INITIAL_ACTIVE_NEEDS], # Deep copy
        "events_log": list(config.INITIAL_EVENTS_LOG) # Deep copy
        # Add other world-specific states here later (e.g., discovered locations)
    }

def load_initial_world_state_from_json():
    """
    Loads the world state from the old world_state.json.
    This is a temporary function for compatibility during refactoring.
    It will be replaced by loading from the main save_game.json.
    """
    try:
        with open(config.WORLD_STATE_FILE, 'r') as f:
            print(f"Loading initial world data from {config.WORLD_STATE_FILE} (legacy).")
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Legacy {config.WORLD_STATE_FILE} not found. Initializing new world.")
        return initialize_new_world()
    except json.JSONDecodeError:
        print(f"Error: Could not decode legacy {config.WORLD_STATE_FILE}. Initializing new world.")
        return initialize_new_world()


def save_game_state(world_data, all_agents_data):
    """Saves the entire game state (world + all agents) to a single file."""
    game_state = {
        "world_data": world_data,
        "all_agents_data": all_agents_data # This will be a dict of agent_id: agent_dict
    }
    try:
        with open(config.SAVE_GAME_FILE, 'w') as f:
            json.dump(game_state, f, indent=2)
        # print(f"Game state saved to {config.SAVE_GAME_FILE} on Day {world_data.get('day', '?')}")
    except IOError as e:
        print(f"Error saving game state: {e}")

def load_game_state():
    """Loads the entire game state from a single file."""
    if not os.path.exists(config.SAVE_GAME_FILE):
        # print(f"No save file found at {config.SAVE_GAME_FILE}.")
        return None
    try:
        with open(config.SAVE_GAME_FILE, 'r') as f:
            game_state = json.load(f)
            # Basic validation
            if "world_data" in game_state and "all_agents_data" in game_state:
                print(f"Successfully loaded game state from {config.SAVE_GAME_FILE} (Day {game_state['world_data'].get('day', '?')}).")
                return game_state
            else:
                print(f"Error: Save file {config.SAVE_GAME_FILE} is corrupted or has missing data.")
                return None
    except json.JSONDecodeError:
        print(f"Error decoding save file {config.SAVE_GAME_FILE}. It might be corrupted.")
        return None
    except IOError as e:
        print(f"Error loading game state: {e}")
        return None

def display_world_status(world_data):
    """Prints the current status of the village resources and needs."""
    print(f"Village Resources: Food={world_data['village_resources']['food']}, Wood={world_data['village_resources']['wood']}, Stone={world_data['village_resources']['stone']}, Herbs={world_data['village_resources']['herbs']}")
    
    if world_data['active_needs']:
        print("Current Village Needs:")
        for i, need in enumerate(world_data['active_needs']):
            progress_percent = need.get('progress', 0.0) * 100
            assigned_count = len(need.get('assigned_agents', []))
            assigned_str = f"({assigned_count} assigned)" if assigned_count > 0 else ""
            print(f"  - {need['description'][:60]}... (Urgency: {need['urgency']}, {progress_percent:.0f}% done {assigned_str})")
    else:
        print("The village has no pressing communal tasks at the moment.")
    print("-" * 50)


def perform_daily_world_update(world_data, all_agents_data_dict): # all_agents_data is now a dict
    """
    Updates the world state at the end of a day (e.g., weather, resource changes, agent sustenance).
    This will take parts of the old daily_world_update from sim_engine.py.
    """
    print("\n--- Dusk Settles: End of Day ---")
    world_data["day"] += 1 # Increment day *after* processing turns, before next day's dawn
    log_entry = f"Night falls on Day {world_data['day']-1}. Day {world_data['day']} will soon dawn."
    world_data["events_log"].append(log_entry)

    # Weather changes
    weather_options = ["Mild", "Sunny", "Rainy", "Cold", "Windy", "Overcast", "Humid"]
    old_weather = world_data["weather"]
    world_data["weather"] = random.choice(weather_options)
    if old_weather != world_data["weather"]:
        print(f"The air shifts; the weather changes from {old_weather} to {world_data['weather']}.")
        world_data["events_log"].append(f"The weather changed to {world_data['weather']}.")

    # Basic needs generation/escalation
    num_living_agents = sum(1 for agent in all_agents_data_dict.values() if agent["status"]["health"] > 0)
    if num_living_agents == 0: return # No one to feed or affect

    # Food need
    food_per_agent_threshold = 3 * num_living_agents
    if world_data["village_resources"]["food"] < food_per_agent_threshold and not any("low on food" in n["description"].lower() for n in world_data["active_needs"]):
        new_need_id = f"N_Sys_{random.randint(100,999)}"
        desc = "A growing concern: Food reserves are dwindling. More must be found!"
        world_data["active_needs"].append({
            "need_id": new_need_id, "description": desc,
            "urgency": "high", "related_skills": ["hunting", "gathering"], "progress": 0.0, "assigned_agents": []
        })
        print("Village Update: Food supplies are becoming scarce.")
        world_data["events_log"].append("Concern rises as food supplies dwindle.")
    
    # Remove completed needs
    completed_needs_today = 0
    initial_need_count = len(world_data["active_needs"])
    world_data["active_needs"] = [n for n in world_data["active_needs"] if n.get("progress", 0.0) < 1.0]
    completed_needs_today = initial_need_count - len(world_data["active_needs"])
    if completed_needs_today > 0:
        print(f"Village Update: {completed_needs_today} communal task(s) were completed today!")
        world_data["events_log"].append(f"{completed_needs_today} task(s) completed.")

    # Agent sustenance and environmental effects
    print("\nAs night falls, villagers assess their wellbeing:")
    for agent_id, agent_data in all_agents_data_dict.items():
        if agent_data["status"]["health"] <= 0:
            continue # Skip dead agents

        # Food consumption
        ate_today = False
        if agent_data["status"]["hunger"] > 25: # Agent is somewhat hungry
            food_needed = config.AGENT_DAILY_FOOD_CONSUMPTION
            if world_data["village_resources"]["food"] >= food_needed:
                world_data["village_resources"]["food"] -= food_needed
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - random.randint(30, 50))
                # agent_manager.add_agent_memory(agent_data, f"Ate from village stockpile. Hunger: {agent_data['status']['hunger']}.")
                ate_today = True
            else: # Not enough village food
                agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + random.randint(5,10))
                # agent_manager.add_agent_memory(agent_data, "Village stockpile empty. Hunger increased.")
                if agent_data["status"]["hunger"] > 70: # Starvation effect
                    agent_data["status"]["health"] = max(0, agent_data["status"]["health"] - config.STARVATION_HEALTH_PENALTY)
                    # agent_manager.add_agent_memory(agent_data, f"Starvation setting in. Health: {agent_data['status']['health']}.")
                    world_data["events_log"].append(f"{agent_data['name']} is weakened by severe hunger.")
        
        # Narrative for eating
        if ate_today:
            print(f"  {agent_data['name']} partakes in the evening meal.")
        elif agent_data["status"]["hunger"] > 70 :
             print(f"  {agent_data['name']} faces another night with a gnawing hunger...")
        
        # Weather effects (e.g., cold)
        if world_data["weather"] == "Cold" and agent_data["status"]["energy"] < 30: # Example: cold affects tired agents more
            agent_data["status"]["health"] = max(0, agent_data["status"]["health"] - config.COLD_WEATHER_HEALTH_PENALTY)
            # agent_manager.add_agent_memory(agent_data, f"Felt the chill due to exhaustion. Health: {agent_data['status']['health']}.")
            if agent_data["status"]["health"] > 0:
                print(f"  The biting cold of the night seeps into {agent_data['name']}'s weary bones.")
        
        if agent_data["status"]["health"] <= 0:
            world_data["events_log"].append(f"TRAGEDY: {agent_data['name']} has succumbed to hardship during the night.")
            print(f"  TRAGEDY STRIKES! {agent_data['name']} ({agent_data['agent_id']}) does not survive the night!")
            # Agent data remains, but they are marked as health <= 0

        # Note: agent_manager will be responsible for saving individual agent files if we stick to that,
        # or this module will handle saving all_agents_data as part of the main save_game.json.
        # For now, we assume save_game_state in main.py handles the collective save.

def display_simulation_summary(world_data, all_agents_data): # Accepts two arguments
    """Prints a summary at the very end of the simulation."""
    print("\n--- End of the Chronicle ---")
    print("Final Village Resources:")
    print(f"  Food: {world_data['village_resources']['food']}, Wood: {world_data['village_resources']['wood']}, Stone: {world_data['village_resources']['stone']}, Herbs={world_data['village_resources']['herbs']}")
    
    living_agents_count = sum(1 for agent in all_agents_data.values() if agent["status"]["health"] > 0)
    if living_agents_count > 0:
        print(f"\n{living_agents_count} survivor(s) remain:")
        for agent_id, agent_data in all_agents_data.items():
            if agent_data["status"]["health"] > 0:
                # Ensure game_utils is imported in world_manager.py to use this
                print(f"  - {agent_data['name']} ({game_utils.get_status_description(agent_data)})") 
    else:
        print("\nAlas, there were no survivors.")

    print("\nRecent Events Log (Last 15 entries):")
    for entry in world_data.get("events_log", [])[-15:]:
        print(f"- {entry}")

