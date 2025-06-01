# --- generate_simulation_files.py ---
import json
import os
import random

# --- Configuration ---
NUM_AGENTS = 10 # Reduced for quicker testing of new mechanics
AGENT_DATA_PATH = "agents"
WORLD_STATE_FILE = "world_state.json"

# Agent Generation Data
POSSIBLE_NAMES = [
    "Elara", "Gorok", "Mira", "Kael", "Seraphina", "Roric", "Lyra", "Bram", "Astrid", "Jorn",
    "Faelan", "Sorin", "Thora", "Cassian", "Lenore", "Orin", "Brynn", "Zephyr", "Rowan", "Gareth",
    "Althea", "Darian", "Maeve", "Lucian", "Terra", "Rhys", "Clara", "Finnian", "Isolde", "Jasper"
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
    "ruthless", "desperate" # Added new traits
]
POSSIBLE_SKILLS = ["hunting", "gathering", "building", "crafting", "healing", "social", "fighting"] # Added "fighting"
INITIAL_AGENT_INVENTORY = { 
    "food_rations": 1, 
    "flint_chip": 1,
    "personal_trinket": 1 
}
TOTAL_SKILL_POINTS_BUDGET = 14 # Increased slightly to account for new skill

INITIAL_WORLD_STATE = {
    "day": 1,
    "season": "Spring",
    "weather": "Mild",
    "village_resources": {
        "food": 50, 
        "wood": 80,
        "stone": 40,
        "herbs": 20,
        "simple_tools": 3 
    },
    "active_needs": [
        {
            "need_id": "N001",
            "description": "Stockpile more food for the village.",
            "urgency": "high",
            "related_skills": ["hunting", "gathering"],
            "progress": 0.0,
            "assigned_agents": []
        },
        {
            "need_id": "N002",
            "description": "Reinforce the main shelter.",
            "urgency": "medium",
            "related_skills": ["building", "crafting"],
            "required_materials": {"wood_scraps": 10}, # Using specific resource key
            "progress": 0.0,
            "assigned_agents": []
        }
    ],
    "events_log": [
        "Day 0: A weary group of survivors established a rudimentary camp in a new clearing."
    ]
}

def generate_simulation_startup_files():
    print("Generating initial simulation files (with shelter & fighting skill)...")

    if not os.path.exists(AGENT_DATA_PATH):
        os.makedirs(AGENT_DATA_PATH)
        print(f"Created directory: {AGENT_DATA_PATH}")

    used_names = set()
    for i in range(1, NUM_AGENTS + 1):
        agent_id = f"agent_{str(i).zfill(3)}"
        name = random.choice(POSSIBLE_NAMES)
        original_name = name
        name_suffix = 1
        while name in used_names: 
            name = f"{original_name}_{name_suffix}"
            name_suffix += 1
        used_names.add(name)

        background = random.choice(POSSIBLE_BACKGROUNDS)
        num_traits = random.randint(2, 4) 
        traits = random.sample(POSSIBLE_PERSONALITY_TRAITS, num_traits)
        
        skills = {skill: 0 for skill in POSSIBLE_SKILLS}
        points_to_distribute = TOTAL_SKILL_POINTS_BUDGET
        for _ in range(points_to_distribute):
            chosen_skill = random.choice(POSSIBLE_SKILLS)
            if skills[chosen_skill] < 5: # Max skill level 5
                 skills[chosen_skill] += 1
            else: # If skill is maxed, try to give point to another skill
                # Create a shuffled list of skills to try
                skill_options = random.sample(POSSIBLE_SKILLS, len(POSSIBLE_SKILLS))
                for sk_opt in skill_options:
                    if skills[sk_opt] < 5:
                        skills[sk_opt] +=1
                        break # Break after assigning the point
        
        current_agent_inventory = INITIAL_AGENT_INVENTORY.copy()
        current_agent_inventory["food_rations"] = random.randint(0,2) # Randomize initial food

        agent_data = {
            "agent_id": agent_id, 
            "name": name, 
            "background": background,
            "personality_traits": traits, 
            "skills": skills,
            "status": { "health": 100, "hunger": random.randint(0, 25), "energy": random.randint(65, 100)},
            "inventory": current_agent_inventory, 
            "shelter_level": 0, # 0: Exposed, 1: Lean-to, 2: Basic Hut, etc.
            "current_focus_need_id": None,
            "memory_log": [f"Woke up feeling {random.choice(['hopeful', 'anxious', 'determined', 'weary'])}."]
        }
        with open(os.path.join(AGENT_DATA_PATH, f"{agent_id}.json"), 'w') as f:
            json.dump(agent_data, f, indent=2)
    print(f"Generated {NUM_AGENTS} agent files in '{AGENT_DATA_PATH}/'")

    with open(WORLD_STATE_FILE, 'w') as f:
        json.dump(INITIAL_WORLD_STATE, f, indent=2)
    print(f"Generated {WORLD_STATE_FILE}")

    print("\nInitial file generation complete!")
    print(f"Ensure prompter.py, agent_manager.py, main.py, and ollama_client.py are in the same directory to run the simulation.")

if __name__ == "__main__":
    generate_simulation_startup_files()
