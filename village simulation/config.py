# config.py
# Centralized configuration for the Primitive Village Simulation

# --- General Simulation Parameters ---
DEBUG_MODE = True  # Set to True for verbose output, False for cleaner output
SIM_DAYS_TO_RUN = 10 # Max number of simulation days to run in a session (if not ended by other means)
USE_MOCK_LLM = True    # If True, uses predefined mock LLM responses. If False, attempts to use Ollama.
DELAY_BETWEEN_AGENT_TURNS = 0.05 # Seconds to pause between each agent's turn (for readability)
DELAY_END_OF_DAY = 0.1 # Seconds to pause after daily summary (for readability)

# --- File Paths ---
# Ensure these paths are relative to where the main script is run from, or use absolute paths.
AGENT_DATA_PATH = "agents" # Directory to save/load individual agent JSON files (if that strategy is used)
WORLD_STATE_FILE = "world_state.json" # Legacy, potentially for initial import if main save file doesn't exist
SAVE_GAME_FILE = "save_game.json"     # Primary file for saving and loading the entire game state

# --- LLM Configuration ---
OLLAMA_DEFAULT_MODEL = "llama3:8b-instruct-q5_K_M" # Default model for Ollama
OLLAMA_TEMPERATURE = 0.7  # Default temperature for Ollama LLM calls (0.0-1.0, higher is more creative/random)

# --- Agent Generation & Attributes ---
INITIAL_AGENT_COUNT = 5 # Number of agents to create for a new game
MAX_MEMORY_LOG = 20       # Maximum number of entries in an agent's memory log
MAX_SKILL_LEVEL = 5       # Maximum level an agent can achieve in a skill (0-5)
TOTAL_SKILL_POINTS_BUDGET_FOR_CREATION = 14 # Points to distribute among skills for new agents
MAX_INITIAL_FOOD_RATIONS = 3 # Max food rations an agent can start with in their personal inventory

# Lists for dynamic agent creation. Used by agent_manager.create_initial_agents and generate_simulation_files.py.
POSSIBLE_NAMES_FOR_CREATION = [
    "Elara", "Gorok", "Mira", "Kael", "Seraphina", "Roric", "Lyra", "Bram", "Astrid", "Jorn",
    "Faelan", "Sorin", "Thora", "Cassian", "Lenore", "Orin", "Brynn", "Zephyr", "Rowan", "Gareth",
    "Althea", "Darian", "Maeve", "Lucian", "Terra", "Rhys", "Clara", "Finnian", "Isolde", "Jasper",
    "Willow", "Silas", "Nadia", "Corbin", "Elowen", "Gideon", "Priya", "Ronan", "Evander",
    "Leona", "Tarek", "Samira", "Kieran", "Anika", "Barrett", "Siona", "Malachi", "Zara", "Ragnar"
]
POSSIBLE_BACKGROUNDS_FOR_CREATION = [
    "Exiled Herbalist's Apprentice", "Lost Child of a Noble Tribe", "Traveling Merchant with Few Wares",
    "Curious Youth Eager to Explore", "Injured Warrior Seeking Refuge", "Former Village Elder",
    "Escaped Captive", "Sole Survivor of a Natural Disaster", "Mysterious Wanderer", "Disgraced Hunter",
    "Aspiring Storyteller", "Orphaned Farmhand", "Skeptical Outcast", "Dreaming Shaman-in-Training",
    "Resourceful Scavenger"
]
POSSIBLE_PERSONALITY_TRAITS_FOR_CREATION = [
    "cautious", "observant", "resourceful", "brave", "greedy", "lazy", "optimistic", "pessimistic",
    "curious", "loyal", "selfish", "generous", "suspicious", "trusting", "ambitious", "content",
    "impulsive", "methodical", "quiet", "talkative", "stubborn", "flexible", "pragmatic", "idealistic",
    "ruthless", "desperate"
]
POSSIBLE_SKILLS_FOR_CREATION = ["hunting", "gathering", "building", "crafting", "healing", "social", "fighting"]
INITIAL_AGENT_INVENTORY_TEMPLATE = {
    "food_rations": 1,
    "flint_chip": 1,
    "personal_trinket": 1
}

# --- Initial World State Defaults ---
# These values define the starting conditions for a new game.
INITIAL_VILLAGE_RESOURCES = {
    "food": 25,             # Starting food stockpile for the village (e.g., equivalent to a few days for initial agents)
    "wood": 30,             # Starting wood stockpile
    "stone": 15,            # Starting stone stockpile
    "herbs": 10,            # General purpose herbs
    "simple_tools": 2,      # Basic shared tools available to the village (e.g. a couple of crude axes or knives)

    # Raw materials that agents might also start with or gather:
    "sturdy_branch": 20,    # Common crafting material
    "sharpened_stone": 10,  # Component for tools/weapons
    "vine_rope": 15,        # Component for crafting (raw version of 'rope')
    "pointed_stone": 10,    # For spears, arrows
    "flat_stone": 5,        # For grinding or construction
    "grinding_stone": 1,    # A more prepared tool/station component
    "heavy_branch": 10,     # For clubs or heavy construction
    "stone_spearhead": 2,   # Crafted component
    "small_stones": 50,     # For slings, or minor construction
    "flexible_branch": 5,   # For bows, traps
    "thin_stick": 30,       # For kindling, arrows, small crafts
    "bird_feathers": 20,    # For fletching arrows
    "animal_hide": 0,       # Must be acquired through hunting
    "animal_fat": 0,        # Must be acquired
    "clay_deposit": 0,      # Must be found/gathered
    "reeds_grass": 30,      # For thatching, weaving
    "healing_herbs": 10,    # Specific medicinal herbs
    "bone_shard": 5         # From animals, for tools/needles
}
INITIAL_ACTIVE_NEEDS = [ # Initial tasks or challenges for the village
    {
        "need_id": "N_Sys_001",
        "description": "Establish a sustainable source of food for the growing village.",
        "urgency": "high",
        "related_skills": ["hunting", "gathering", "fishing"], # 'fishing' skill can be added if relevant mechanics exist
        "progress": 0.0,
        "assigned_agents": []
    },
    {
        "need_id": "N_Sys_002",
        "description": "Improve basic shelters to protect against the elements and store goods.",
        "urgency": "medium",
        "related_skills": ["building", "crafting"],
        "required_materials": {"wood": 15, "sturdy_branch": 10, "vine_rope": 5}, # Example materials
        "progress": 0.0,
        "assigned_agents": []
    }
]
INITIAL_EVENTS_LOG = ["The survivors, weary but determined, surveyed their new, unfamiliar surroundings. A fresh start, fraught with peril and promise."]

# --- Game Mechanics Constants ---
# These values govern the core rules of the simulation.
AGENT_DAILY_FOOD_CONSUMPTION = 1    # Amount of 'food' resource an agent tries to consume from village stockpile per day if very hungry.
STARVATION_HEALTH_PENALTY = 5     # Health lost per day if agent's hunger is critical (e.g., >80) and no food is eaten.
COLD_WEATHER_HEALTH_PENALTY = 3   # Health lost if agent is exposed to "Cold" weather with low energy/poor shelter.
COLD_EFFECT_ENERGY_THRESHOLD = 30 # Energy level below which agents are more susceptible to cold without adequate shelter.
SHELTER_COLD_RESISTANCE_BONUS = 10# Effective energy bonus per shelter level against cold (e.g. shelter_level 1 adds 10 to energy for cold check).
LOW_ENERGY_HEALTH_PENALTY = 2     # Health lost if energy is 0 at end of day (currently a placeholder, could be expanded).
BASE_ENERGY_COST_PER_ACTION = 5   # Default energy cost for most agent actions, can be modified by item effects.
BASE_HUNGER_INCREASE_PER_ACTION = 2 # Default hunger points an agent gains after performing an action.
REST_ENERGY_GAIN = 25             # Amount of energy an agent regains when successfully performing the 'rest' action.
PROGRESS_PER_SUCCESSFUL_GATHER = 0.02 # Factor determining how much a single successful resource gather contributes to a related Need's progress.

# --- Shelter Configuration ---
# Defines the resources required to upgrade an agent's personal shelter to the next level.
# Key is the target shelter level.
SHELTER_UPGRADE_COSTS = {
    1: {"wood": 10, "sturdy_branch": 5, "vine_rope": 2},  # Cost to upgrade from level 0 to level 1 (Crude Lean-to)
    2: {"wood": 20, "stone": 10, "vine_rope": 4},        # Cost to upgrade from level 1 to level 2 (Basic Hut)
    3: {"wood": 30, "stone": 20, "rope": 2},             # Cost to upgrade from level 2 to level 3 (Sturdy Hut) - uses crafted 'rope'
    # Add costs for higher levels as needed
}

# --- Craftable Items Definitions ---
# This dictionary defines all items that can be crafted by agents.
# Structure:
# "item_id": {
#   "name": "Readable Name",
#   "description": "Brief description for LLM context and potentially UI tooltips.",
#   "recipe": {"material_id_from_personal_resources_or_inventory": count, ...}, # Materials consumed during crafting.
#   "skill_required": "skill_name", # e.g., "crafting", "building", "healing" from POSSIBLE_SKILLS_FOR_CREATION.
#   "min_skill_level": integer,       # Minimum skill level required to attempt crafting.
#   "energy_cost": integer,           # Energy consumed by the agent to perform the crafting action.
#   "time_cost": float,               # Abstract time units (not directly used by sim_engine yet, but planned).
#   "yield": integer,                 # How many items are produced from one crafting action (default 1).
#   "properties": {                   # Specific attributes of the crafted item.
#       "item_category": "tool", "weapon", "armor", "clothing", "consumable", "component", "material", "decoration",
#       "tool_type": "axe", "pickaxe", "knife", etc. (if item_category is "tool"),
#       "weapon_type": "melee_blunt", "melee_slashing", etc. (if item_category is "weapon"),
#       "equip_slot": ["hand_main", "hand_off", "body", "head", "feet"] (if equippable),
#       "effects": [  # List of effects the item provides.
#           {"type": "gathering_yield", "resource": "wood", "bonus_flat": 2, "condition": "equipped"}, # Increases wood gathered by 2.
#           {"type": "action_energy_modifier", "action": "gather_wood", "modifier": -2, "condition": "equipped"}, # Reduces energy cost of gathering wood by 2.
#           {"type": "combat_damage", "damage_value": 3, "damage_type": "slashing", "condition": "equipped_hand_main"}, # Adds 3 slashing damage.
#           {"type": "armor_value", "damage_type": "physical", "value": 1, "condition": "equipped_body"}, # Provides 1 physical armor.
#           {"type": "stat_change_on_consume", "stat": "health", "change": 10}, # Consuming heals 10 HP.
#           {"type": "stat_change_on_consume", "stat": "hunger", "change": -20} # Consuming reduces hunger by 20.
#       ],
#       "durability": integer (optional, e.g., 100, for items that wear out)
#   }
# }
CRAFTABLE_ITEMS = {
    "flint_knife": {
        "name": "Flint Knife",
        "description": "A sharp piece of flint attached to a small stick, useful for cutting and light tasks.",
        "recipe": {"flint_chip": 1, "thin_stick": 1, "vine_rope": 1},
        "skill_required": "crafting",
        "min_skill_level": 0,
        "energy_cost": 5,
        "time_cost": 0.5,
        "yield": 1,
        "properties": {
            "item_category": "tool",
            "tool_type": "knife",
            "equip_slot": ["hand_main"],
            "effects": [
                {"type": "gathering_yield", "resource": "herbs", "bonus_flat": 1, "condition": "equipped"},
                {"type": "gathering_yield", "resource": "healing_herbs", "bonus_flat": 1, "condition": "equipped"},
                {"type": "action_success_modifier", "action": "skin_small_animal", "bonus_chance": 0.1, "condition": "equipped"},
                {"type": "combat_damage", "damage_value": 1, "damage_type": "piercing", "condition": "equipped_hand_main"}
            ],
            "durability": 20
        }
    },
    "stone_axe": {
        "name": "Stone Axe",
        "description": "A sharpened stone head hafted to a sturdy branch, good for chopping wood and as a crude weapon.",
        "recipe": {"sturdy_branch": 1, "sharpened_stone": 1, "vine_rope": 1},
        "skill_required": "crafting",
        "min_skill_level": 1,
        "energy_cost": 10,
        "time_cost": 1.0,
        "yield": 1,
        "properties": {
            "item_category": "tool",
            "tool_type": "axe",
            "weapon_type": "melee_slashing",
            "equip_slot": ["hand_main"],
            "effects": [
                {"type": "gathering_yield", "resource": "wood", "bonus_flat": 2, "condition": "equipped"},
                {"type": "action_energy_modifier", "action": "gather_wood", "modifier": -2, "condition": "equipped"},
                {"type": "combat_damage", "damage_value": 3, "damage_type": "slashing", "condition": "equipped_hand_main"}
            ],
            "durability": 50
        }
    },
    "wooden_club": {
        "name": "Wooden Club",
        "description": "A heavy, sturdy branch, suitable as a basic blunt weapon.",
        "recipe": {"heavy_branch": 1},
        "skill_required": "crafting",
        "min_skill_level": 0,
        "energy_cost": 3,
        "time_cost": 0.3,
        "yield": 1,
        "properties": {
            "item_category": "weapon",
            "weapon_type": "melee_blunt",
            "equip_slot": ["hand_main"],
            "effects": [
                {"type": "combat_damage", "damage_value": 2, "damage_type": "blunt", "condition": "equipped_hand_main"}
            ],
            "durability": 30
        }
    },
    "basic_healing_salve": {
        "name": "Basic Healing Salve",
        "description": "A simple poultice of crushed healing herbs, provides minor healing.",
        "recipe": {"healing_herbs": 2, "animal_fat": 1},
        "skill_required": "healing",
        "min_skill_level": 1,
        "energy_cost": 5,
        "time_cost": 0.5,
        "yield": 1,
        "properties": {
            "item_category": "consumable",
            "effects": [
                {"type": "stat_change_on_consume", "stat": "health", "change": 10}
            ]
        }
    },
    "rope": {
        "name": "Rope",
        "description": "Strong fibers twisted together, useful for crafting and building.",
        "recipe": {"vine_rope": 3},
        "skill_required": "crafting",
        "min_skill_level": 0,
        "energy_cost": 4,
        "time_cost": 0.4,
        "yield": 1,
        "properties": {
            "item_category": "component"
        }
    },
    "food_rations": {
        "name": "Food Rations",
        "description": "A basic bundle of preserved food for sustenance.",
        "recipe": {"food": 1}, # Assumes 'food' is a generic resource that can be converted.
        "skill_required": "crafting",
        "min_skill_level": 0,
        "energy_cost": 2,
        "time_cost": 0.2,
        "yield": 1,
        "properties": {
            "item_category": "consumable",
            "effects": [
                {"type": "stat_change_on_consume", "stat": "hunger", "change": -30}
            ]
        }
    }
}

# Define which personal resources can be gathered directly by agents (raw materials)
# These are typically not crafted but found in the environment.
GATHERABLE_PERSONAL_RESOURCES = {
    # resource_id: {skill_to_use, base_yield_range [min, max], base_difficulty, time_cost (abstract)}
    "sturdy_branch": {"skill": "gathering", "base_yield": [1, 3], "base_difficulty": 2, "time_cost": 0.8},
    "vine_rope": {"skill": "gathering", "base_yield": [1, 2], "base_difficulty": 3, "time_cost": 0.7},
    "flint_chip": {"skill": "gathering", "base_yield": [1, 4], "base_difficulty": 1, "time_cost": 0.5},
    "small_stones": {"skill": "gathering", "base_yield": [5, 10], "base_difficulty": 1, "time_cost": 0.3},
    "reeds_grass": {"skill": "gathering", "base_yield": [2, 5], "base_difficulty": 1, "time_cost": 0.6},
    "healing_herbs": {"skill": "gathering", "base_yield": [1, 3], "base_difficulty": 2, "time_cost": 0.7},
    "sharpened_stone": {"skill": "gathering", "base_yield": [0, 1], "base_difficulty": 4, "time_cost": 1.0}, # Harder to find just lying around
    "heavy_branch": {"skill": "gathering", "base_yield": [0, 1], "base_difficulty": 3, "time_cost": 0.9},
    "thin_stick": {"skill": "gathering", "base_yield": [2, 6], "base_difficulty": 1, "time_cost": 0.4},
    "bird_feathers": {"skill": "hunting", "base_yield": [0,3], "base_difficulty": 2, "time_cost": 0.5}, # Result of small game hunting
    "animal_fat": {"skill": "hunting", "base_yield": [0,2], "base_difficulty": 3, "time_cost": 0.8}, # Result of successful hunts
    "bone_shard": {"skill": "hunting", "base_yield": [0,2], "base_difficulty": 3, "time_cost": 0.8}  # Result of successful hunts
    # "food": {"skill": "gathering", "base_yield": [1,2], "base_difficulty": 2, "time_cost": 0.6} # Generic 'food' gatherable
}

# General guide for tool effectiveness; primary source of truth is item's own 'properties.effects' list.
# This can be used for high-level descriptions or AI hints if needed.
TOOL_EFFECTIVENESS_GENERAL_GUIDE = {
    "axe": {"primary_use": "gather_wood", "secondary_use": "combat_melee"},
    "knife": {"primary_use": "gather_herbs", "secondary_use": "skin_animal", "tertiary_use": "combat_melee_light"},
    "pickaxe": {"primary_use": "gather_stone", "secondary_use": "dig"}, # Example, pickaxe not yet defined
}
