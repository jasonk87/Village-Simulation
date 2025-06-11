# game_utils.py
# Utility functions for the simulation

import random
from typing import Dict, Any, List, Optional, Set
import config # For MAX_MEMORY_LOG and other potential shared constants

def add_memory_log(agent_data: Dict[str, Any], entry: str, config_module: Optional[Any] = None):
    """
    Adds an entry to the agent's memory log, ensuring it doesn't exceed the maximum size.

    Args:
        agent_data: The agent's data dictionary.
        entry: The string to add to the memory log.
        config_module: The configuration module (e.g., config.py) to get MAX_MEMORY_LOG.
                       Defaults to using the imported 'config' module.
    """
    if config_module is None:
        config_module = config # Use the globally imported config if specific one isn't provided

    max_log = getattr(config_module, 'MAX_MEMORY_LOG', 10) # Default to 10 if not found

    agent_data.setdefault("memory_log", []).append(entry)
    if len(agent_data["memory_log"]) > max_log:
        agent_data["memory_log"] = agent_data["memory_log"][-max_log:]

def get_status_description(agent_data: Dict[str, Any]) -> str:
    """
    Converts agent's numerical status (health, hunger, energy) into a textual description.

    Args:
        agent_data: The agent's data dictionary, expected to have a "status" sub-dictionary.

    Returns:
        A string describing the agent's current status.
    """
    status = agent_data.get("status", {})
    health = status.get("health", 0)
    hunger = status.get("hunger", 0)
    energy = status.get("energy", 0)

    if health <= 0:
        return "Deceased"

    health_desc = "Healthy"
    if 70 <= health < 100: health_desc = "Feeling Good"
    elif 40 <= health < 70: health_desc = "Injured"
    elif 1 <= health < 40: health_desc = "Critically Wounded"
    # health <= 0 is handled above

    hunger_desc = "Satiated"
    if 21 <= hunger <= 50: hunger_desc = "Peckish"
    elif 51 <= hunger <= 80: hunger_desc = "Hungry"
    elif hunger > 80: hunger_desc = "Starving"

    energy_desc = "Energetic"
    if 70 <= energy < 100: energy_desc = "Vigorous"
    elif 40 <= energy < 70: energy_desc = "Fatigued"
    elif 1 <= energy < 40: energy_desc = "Exhausted"
    elif energy <= 0: energy_desc = "Collapsed" # Should ideally also check health

    return f"{health_desc}, {hunger_desc}, {energy_desc}"

def get_shelter_description(shelter_level: int) -> str:
    """
    Returns a textual description of the agent's shelter based on its level.

    Args:
        shelter_level: The numerical level of the shelter.

    Returns:
        A string describing the shelter.
    """
    if shelter_level == 0: return "exposed to the elements"
    if shelter_level == 1: return "a crude lean-to"
    if shelter_level == 2: return "a basic hut"
    if shelter_level == 3: return "a sturdy hut"
    if shelter_level >= 4: return "a well-built dwelling"
    return "an unknown shelter"

def perform_skill_check(skill_value: int, difficulty: int = 3, tool_bonus: int = 0) -> bool:
    """
    Performs a skill check based on skill value, difficulty, and tool bonus.
    A d10 roll is made. To succeed, roll >= required_roll.
    Base required_roll is 8, decreasing with higher skill/tool bonus.
    Difficulty adjusts the required_roll (higher difficulty increases required_roll).

    Args:
        skill_value: The agent's relevant skill level (typically 0-5).
        difficulty: The difficulty of the task (e.g., 1-5, where 3 is neutral).
        tool_bonus: Bonus points from tools or other aids.

    Returns:
        True if the skill check is successful, False otherwise.
    """
    roll = random.randint(1, 10)

    # Base roll needed is 8 for skill 0. Each skill point effectively reduces this.
    # Example: Skill 0 needs 8+, Skill 1 needs 7+, ..., Skill 5 needs 3+
    required_roll_base = 8 - skill_value

    # Apply tool bonus, reducing the required roll
    required_roll_after_tool = required_roll_base - tool_bonus

    # Adjust for task difficulty (neutral difficulty is 3)
    # Higher difficulty increases the roll needed.
    difficulty_modifier = difficulty - 3
    final_required_roll = required_roll_after_tool + difficulty_modifier

    # Clamp the required roll to be within 1-10 (as it's a d10 roll)
    # (Though practically, needing >10 means impossible, <1 means guaranteed if roll can be 1)
    # A roll of 1 might always fail, a 10 might always succeed, depending on game design.
    # For now, just clamp the target.
    final_required_roll = max(1, min(10, final_required_roll))

    return roll >= final_required_roll

def get_random_name(used_names_set: Set[str], config_module: Optional[Any] = None) -> str:
    """
    Generates a unique random name from the config list, adding it to the used_names_set.

    Args:
        used_names_set: A set of names already in use to ensure uniqueness.
        config_module: The configuration module (e.g., config.py) to get POSSIBLE_NAMES.
                       Defaults to using the imported 'config' module.
    Returns:
        A unique name string.
    """
    if config_module is None:
        config_module = config

    possible_names = getattr(config_module, 'POSSIBLE_NAMES_FOR_CREATION', ["Villager"]) # Default if not in config

    available_names = [name for name in possible_names if name not in used_names_set]
    if not available_names:
        # Fallback if all names are used (shouldn't happen with enough names)
        fallback_name = f"Settler_{random.randint(1000, 9999)}"
        while fallback_name in used_names_set: # Ensure fallback is also unique
            fallback_name = f"Settler_{random.randint(1000, 9999)}"
        used_names_set.add(fallback_name)
        return fallback_name

    name = random.choice(available_names)
    used_names_set.add(name)
    return name

def convert_inventory_to_dict_format(inventory_data: Any) -> Dict[str, int]:
    """
    Converts old list-based inventory or ensures dict format.
    Handles None, existing dicts, or lists of item names.

    Args:
        inventory_data: The inventory data to convert. Can be None, list, or dict.

    Returns:
        A dictionary representing the inventory, with item_id as key and quantity as value.
        Returns an empty dictionary if input is unparsable or inappropriate.
    """
    if isinstance(inventory_data, dict):
        return inventory_data # Already in correct format

    new_inventory: Dict[str, int] = {}
    if isinstance(inventory_data, list):
        for item_name in inventory_data:
            if isinstance(item_name, str):
                item_key = item_name.lower().replace(" ", "_") # Normalize key
                new_inventory[item_key] = new_inventory.get(item_key, 0) + 1
            # else: ignore non-string items in a list-based inventory
        return new_inventory

    # If inventory_data is None or some other unexpected type, return empty dict
    return {}
