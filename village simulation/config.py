# config.py
# Centralized configuration for the simulation

DEBUG_MODE = True  # Set to True for verbose output during development

# --- Simulation Parameters ---
SIM_DAYS_TO_RUN = 7
USE_MOCK_LLM = True
AGENT_DATA_PATH = "agents" 
WORLD_STATE_FILE = "world_state.json" 
SAVE_GAME_FILE = "save_game.json" 
INITIAL_AGENT_COUNT = 20 
DELAY_BETWEEN_AGENT_TURNS = 0.1 
DELAY_END_OF_DAY = 0.5 


# --- LLM Configuration ---
OLLAMA_DEFAULT_MODEL = "llama3.2:latest" 
OLLAMA_TEMPERATURE = 0.7

# --- Agent Generation Data ---
POSSIBLE_NAMES = [
    "Elara", "Gorok", "Mira", "Kael", "Seraphina", "Roric", "Lyra", "Bram", "Astrid", "Jorn",
    "Faelan", "Sorin", "Thora", "Cassian", "Lenore", "Orin", "Brynn", "Zephyr", "Rowan", "Gareth",
    "Althea", "Darian", "Maeve", "Lucian", "Terra", "Rhys", "Clara", "Finnian", "Isolde", "Jasper",
    "Willow", "Silas", "Nadia", "Corbin", "Elowen", "Gideon", "Priya", "Ronan", "Evander",
    "Leona", "Tarek", "Samira", "Kieran", "Anika", "Barrett", "Siona", "Malachi", "Zara", "Ragnar"
]
POSSIBLE_BACKGROUNDS = [
    "Exiled Herbalist's Apprentice", "Lost Child of a Noble Tribe", "Traveling Merchant with Few Wares",
    "Curious Youth Eager to Explore", "Injured Warrior Seeking Refuge", "Former Village Elder",
    "Escaped Captive", "Sole Survivor of a Natural Disaster", "Mysterious Wanderer", "Disgraced Hunter",
    "Aspiring Storyteller", "Orphaned Farmhand", "Skeptical Outcast", "Dreaming Shaman-in-Training",
    "Resourceful Scavenger"
]
POSSIBLE_PERSONALITY_TRAITS = [
    "cautious", "observant", "resourceful", "brave", "greedy", "lazy", "optimistic", "pessimistic",
    "curious", "loyal", "selfish", "generous", "suspicious", "trusting", "ambitious", "content",
    "impulsive", "methodical", "quiet", "talkative", "stubborn", "flexible", "pragmatic", "idealistic",
    "ruthless", "desperate"
]
POSSIBLE_SKILLS = ["hunting", "gathering", "building", "crafting", "healing", "social", "fighting"]
INITIAL_AGENT_INVENTORY_TEMPLATE = { 
    "food_rations": 1,
    "flint_chip": 1,
    "personal_trinket": 1
}
TOTAL_SKILL_POINTS_BUDGET_FOR_CREATION = 14
MAX_SKILL_LEVEL = 5
MAX_MEMORY_LOG = 10

# --- Initial World State Defaults ---
INITIAL_VILLAGE_RESOURCES = {
    "food": 150, "wood": 80, "stone": 40, "herbs": 25, "simple_tools": 3,
    "sturdy_branch": 20, "sharpened_stone": 10, "vine_rope": 15, "pointed_stone": 10, 
    "flat_stone": 5, "grinding_stone": 5, "heavy_branch": 10, "stone_spearhead": 5, 
    "small_stones": 50, "flexible_branch": 5, "thin_stick": 30, "bird_feathers": 20, 
    "animal_hide": 0, "animal_fat": 0, "clay_deposit": 0, "reeds_grass": 30,
    "healing_herbs": 10, # More specific herb type
    "bone_shard": 5 # From animals
}
INITIAL_ACTIVE_NEEDS = [
    {
        "need_id": "N_Sys_001", "description": "Establish a more permanent source of food.",
        "urgency": "high", "related_skills": ["hunting", "gathering", "fishing"], "progress": 0.0, "assigned_agents": []
    },
    {
        "need_id": "N_Sys_002", "description": "Improve the basic shelters against the elements.",
        "urgency": "medium", "related_skills": ["building", "crafting"],
        "required_materials": {"wood": 10, "vine_rope": 2}, "progress": 0.0, "assigned_agents": []
    }
]
INITIAL_EVENTS_LOG = ["The survivors gathered, a new beginning uncertain."]

# --- Game Mechanics Constants ---
AGENT_DAILY_FOOD_CONSUMPTION = 1
STARVATION_HEALTH_PENALTY = 5
COLD_WEATHER_HEALTH_PENALTY = 3
LOW_ENERGY_HEALTH_PENALTY = 2 
BASE_ENERGY_COST_PER_ACTION = 5
BASE_HUNGER_INCREASE_PER_ACTION = 2
REST_ENERGY_GAIN = 25

# --- Craftable Items Definitions ---
# item_id: {
#   name: "Readable Name",
#   description: "Brief description for LLM/UI",
#   recipe: {"material_id_from_personal_resources": count, ...},
#   skill_required: "crafting_skill_name", (e.g., "crafting", "building", "healing")
#   min_skill_level: integer,
#   energy_cost: integer (energy to craft),
#   time_cost: float (abstract time units, e.g., 1.0 for a standard action),
#   yield: integer (how many are crafted at once, default 1),
#   properties: {
#       item_category: "tool", "weapon", "armor", "clothing", "consumable", "component", "decoration"
#       tool_type: "axe", "pickaxe", "knife", "shovel", "hammer", "fishing_rod" (if item_category is "tool")
#       weapon_type: "melee_blunt", "melee_slashing", "melee_piercing", "ranged_thrown", "ranged_bow", "ranged_sling" (if item_category is "weapon")
#       equip_slot: ["hand_main", "hand_off", "body", "head", "feet"] (if equippable)
#       effects: [ 
#           {"type": "gathering_yield", "resource": "wood", "bonus_flat": 2, "condition": "equipped"},
#           {"type": "action_energy_modifier", "action": "gather_wood", "modifier": -2, "condition": "equipped"},
#           {"type": "combat_damage", "damage_value": 3, "damage_type": "slashing", "condition": "equipped_hand_main"},
#           {"type": "armor_value", "damage_type": "physical", "value": 1, "condition": "equipped_body"},
#           {"type": "stat_change_on_consume", "stat": "health", "change": 10}, 
#           {"type": "stat_change_on_consume", "stat": "hunger", "change": -20} 
#       ],
#       durability: integer (optional, e.g., 100)
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
                {"type": "action_success_modifier", "action": "skin_small_animal", "bonus_chance": 0.1, "condition": "equipped"}, # +10% success
                {"type": "combat_damage", "damage_value": 1, "damage_type": "piercing", "condition": "equipped_hand_main"} # Very basic weapon
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
            "item_category": "tool", # Can also be "weapon" or have dual categories if logic supports
            "tool_type": "axe",
            "weapon_type": "melee_slashing", # Dual purpose
            "equip_slot": ["hand_main"], # Can be one or two-handed if logic allows
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
        "skill_required": "crafting", # Minimal crafting, more like selecting a good branch
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
        "recipe": {"healing_herbs": 2, "animal_fat": 1}, # Animal fat makes it a salve
        "skill_required": "healing",
        "min_skill_level": 1,
        "energy_cost": 5,
        "time_cost": 0.5,
        "yield": 1, # Makes one dose
        "properties": {
            "item_category": "consumable",
            "effects": [
                {"type": "stat_change_on_consume", "stat": "health", "change": 10} # Heals 10 HP
            ]
            # No durability for consumables
        }
    },
    "rope": {
        "name": "Rope",
        "description": "Strong fibers twisted together, useful for crafting and building.",
        "recipe": {"vine_rope": 3}, # 'vine_rope' is the gatherable resource
        "skill_required": "crafting",
        "min_skill_level": 0,
        "energy_cost": 4,
        "time_cost": 0.4,
        "yield": 1, # Makes one length of rope
        "properties": {
            "item_category": "component"
            # No direct effects, used in other recipes
        }
    }
    # Add more items here following the structure
}

# Define which personal resources can be gathered directly by agents
GATHERABLE_PERSONAL_RESOURCES = {
    "sturdy_branch": {"skill": "gathering", "base_yield": [1, 3], "base_difficulty": 2, "time_cost": 0.8},
    "vine_rope": {"skill": "gathering", "base_yield": [1, 2], "base_difficulty": 3, "time_cost": 0.7}, # This is the raw material for 'rope'
    "flint_chip": {"skill": "gathering", "base_yield": [1, 4], "base_difficulty": 1, "time_cost": 0.5},
    "small_stones": {"skill": "gathering", "base_yield": [5, 10], "base_difficulty": 1, "time_cost": 0.3},
    "reeds_grass": {"skill": "gathering", "base_yield": [2, 5], "base_difficulty": 1, "time_cost": 0.6},
    "healing_herbs": {"skill": "gathering", "base_yield": [1, 3], "base_difficulty": 2, "time_cost": 0.7},
    "sharpened_stone": {"skill": "gathering", "base_yield": [0, 1], "base_difficulty": 4, "time_cost": 1.0}, # Harder to find directly
    "heavy_branch": {"skill": "gathering", "base_yield": [0, 1], "base_difficulty": 3, "time_cost": 0.9},
    "thin_stick": {"skill": "gathering", "base_yield": [2, 6], "base_difficulty": 1, "time_cost": 0.4},
    # Raw stone might need a "mining" action or higher gathering skill/pickaxe
    # "raw_stone_chunks": {"skill": "gathering", "base_yield": [1,2], "base_difficulty": 4, "required_tool": "stone_pickaxe"}, 
}

# Tool effectiveness (simplified, specific effects are in item properties)
# This can be used for quick lookups or more generic checks if needed.
# The primary source of truth for an item's effect should be its own 'properties.effects' list.
TOOL_EFFECTIVENESS_GENERAL_GUIDE = {
    "axe": {"primary_use": "gather_wood", "secondary_use": "combat_melee"},
    "knife": {"primary_use": "gather_herbs", "secondary_use": "skin_animal", "tertiary_use": "combat_melee_light"},
    "pickaxe": {"primary_use": "gather_stone", "secondary_use": "dig"},
    # ...
}

