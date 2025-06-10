# game_utils.py
# Utility functions for the simulation

import random
import config

def get_status_description(agent_data):
    """Converts agent's numerical status into a textual description."""
    health = agent_data["status"]["health"]
    hunger = agent_data["status"]["hunger"]
    energy = agent_data["status"]["energy"]

    health_desc = "Healthy"
    if 70 <= health < 100: health_desc = "Feeling Good"
    elif 40 <= health < 70: health_desc = "Injured"
    elif 1 <= health < 40: health_desc = "Critically Wounded"
    elif health <= 0: health_desc = "Deceased"


    hunger_desc = "Satiated"
    if 21 <= hunger <= 50: hunger_desc = "Peckish"
    elif 51 <= hunger <= 80: hunger_desc = "Hungry"
    elif hunger > 80: hunger_desc = "Starving"

    energy_desc = "Energetic"
    if 70 <= energy < 100: energy_desc = "Vigorous"
    elif 40 <= energy < 70: energy_desc = "Fatigued"
    elif 1 <= energy < 40: energy_desc = "Exhausted"
    elif energy <=0: energy_desc = "Collapsed"

    if health <= 0: return "Deceased"
    return f"{health_desc}, {hunger_desc}, {energy_desc}"

def perform_skill_check(skill_value, difficulty=3, tool_bonus=0):
    """
    Performs a skill check.
    Args:
        skill_value (int): The agent's relevant skill level (0-5).
        difficulty (int): The difficulty of the task (1-5, default 3).
        tool_bonus (int): Bonus from tools (0 or positive).
    Returns:
        bool: True if successful, False otherwise.
    """
    # Roll a d10. Success if roll >= target.
    # Target = Base Difficulty (e.g., 6) - Skill - Tool Bonus + Task Difficulty Modifier
    # Simplified: Higher skill/tool lowers target number needed on d10.
    # Example: Skill 3, Diff 3, Tool 0. Roll d10. Target = 6 - 3 - 0 + 0 = 3. Need 3+ to succeed.
    # Example: Skill 1, Diff 3, Tool 0. Roll d10. Target = 6 - 1 - 0 + 0 = 5. Need 5+ to succeed.
    # Let's use a slightly different model for more spread:
    # Chance of success increases with skill.
    # Base success chance could be (skill_value + tool_bonus) * 15% + random element vs difficulty.
    # For now, keeping it simple:
    roll = random.randint(1, 10)
    # Effective skill is skill_value + tool_bonus
    # Target number to beat on d10. Lower is better for agent.
    # Let's say 5 is a neutral difficulty.
    # Difficulty here is an abstract value; higher difficulty makes success harder.
    # Let's map skill to a success threshold on a d10 roll.
    # Skill 0: needs 8+
    # Skill 1: needs 7+
    # Skill 2: needs 6+
    # Skill 3: needs 5+
    # Skill 4: needs 4+
    # Skill 5: needs 3+
    # Adjust this by difficulty (e.g. +1 to roll needed per difficulty point above 3, -1 per below 3)

    required_roll = max(3, 8 - (skill_value + tool_bonus)) # Base roll needed
    required_roll += (difficulty - 3) # Adjust for task difficulty (3 is neutral)
    required_roll = max(1, min(10, required_roll)) # Clamp between 1 and 10

    return roll >= required_roll

def get_random_name(used_names_set):
    """Generates a unique random name from the config list."""
    available_names = [name for name in config.POSSIBLE_NAMES if name not in used_names_set]
    if not available_names: # Fallback if all names are used (shouldn't happen with enough names)
        return f"Villager_{random.randint(1000, 9999)}"
    name = random.choice(available_names)
    used_names_set.add(name)
    return name

def convert_inventory_to_dict_format(inventory_data):
    """Converts old list-based inventory or ensures dict format."""
    if isinstance(inventory_data, dict):
        return inventory_data
    if isinstance(inventory_data, list):
        new_inventory = {}
        for item_name in inventory_data:
            item_key = str(item_name).lower().replace(" ", "_")
            new_inventory[item_key] = new_inventory.get(item_key, 0) + 1
        return new_inventory
    return {}

if __name__ == '__main__':
    # Test get_status_description
    test_agent_status = {"health": 100, "hunger": 10, "energy": 80}
    print(f"Status (100,10,80): {get_status_description({'status': test_agent_status})}")
    test_agent_status = {"health": 50, "hunger": 60, "energy": 30}
    print(f"Status (50,60,30): {get_status_description({'status': test_agent_status})}")
    test_agent_status = {"health": 0, "hunger": 90, "energy": 0}
    print(f"Status (0,90,0): {get_status_description({'status': test_agent_status})}")

    # Test perform_skill_check
    print("\nSkill Check Examples (Skill 3, Difficulty 3):")
    successes = 0
    for _ in range(10):
        if perform_skill_check(skill_value=3, difficulty=3):
            successes +=1
    print(f"  Successes: {successes}/10")

    print("Skill Check Examples (Skill 1, Difficulty 4):")
    successes = 0
    for _ in range(10):
        if perform_skill_check(skill_value=1, difficulty=4):
            successes +=1
    print(f"  Successes: {successes}/10")
