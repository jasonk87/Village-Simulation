import json
import os
import random

# --- Configuration ---
NUM_AGENTS = 50
AGENT_DATA_PATH = "agents"
WORLD_STATE_FILE = "world_state.json"
PROMPTER_FILE = "prompter.py"
SIM_ENGINE_FILE = "sim_engine.py"
OLLAMA_CLIENT_FILE = "ollama_client.py"

# --- Content for Files ---

# Agent Generation Data
POSSIBLE_NAMES = [
    "Elara", "Gorok", "Mira", "Kael", "Seraphina", "Roric", "Lyra", "Bram", "Astrid", "Jorn",
    "Faelan", "Sorin", "Thora", "Cassian", "Lenore", "Orin", "Brynn", "Zephyr", "Rowan", "Gareth",
    "Althea", "Darian", "Maeve", "Lucian", "Terra", "Rhys", "Clara", "Finnian", "Isolde", "Jasper",
    "Willow", "Silas", "Nadia", "Corbin", "Elowen", "Gideon", "Priya", "Ronan", "Astrid", "Evander",
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
    "impulsive", "methodical", "quiet", "talkative", "stubborn", "flexible"
]
POSSIBLE_SKILLS = ["hunting", "gathering", "building", "crafting", "healing", "social"]
INITIAL_INVENTORY_ITEMS = ["worn_pouch", "flint_chip", "dried_berries_x1"]
TOTAL_SKILL_POINTS_BUDGET = 12 # Distribute this many points among skills

# world_state.json content
INITIAL_WORLD_STATE = {
    "day": 1,
    "season": "Spring",
    "weather": "Mild",
    "village_resources": {
        "food": 200,
        "wood": 100,
        "stone": 50,
        "herbs": 30,
        "simple_tools": 5
    },
    "active_needs": [
        {
            "need_id": "N001",
            "description": "Stockpile more food for the coming days.",
            "urgency": "medium",
            "related_skills": ["hunting", "gathering"],
            "progress": 0.0,
            "assigned_agents": []
        },
        {
            "need_id": "N002",
            "description": "Reinforce a section of the makeshift shelter.",
            "urgency": "low",
            "related_skills": ["building", "crafting"],
            "required_materials": {"wood": 10},
            "progress": 0.0,
            "assigned_agents": []
        }
    ],
    "events_log": [
        "Day 0: A weary group of survivors established a rudimentary camp in a new clearing."
    ]
}

# prompter.py content
PROMPTER_SCRIPT_CONTENT = """
import json

def generate_agent_prompt(agent_data, world_state):
    # Basic prompt structure, can be expanded significantly
    prompt = f"You are {agent_data['name']}, a {agent_data['background']}. Your traits: {', '.join(agent_data['personality_traits'])}."
    prompt += f"\\nIt is Day {world_state['day']}, the weather is {world_state['weather']} during the {world_state['season']}."
    prompt += f"\\nYour current status: Health {agent_data['status']['health']}, Hunger {agent_data['status']['hunger']} (0=full, 100=starving), Energy {agent_data['status']['energy']}."
    
    skill_strings = []
    for skill, value in agent_data['skills'].items():
        skill_strings.append(f"{skill.capitalize()}: {value}/5")
    prompt += f"\\nYour skills: {', '.join(skill_strings)}."
    prompt += f"\\nYour inventory: {', '.join(agent_data['inventory']) if agent_data['inventory'] else 'nothing'}."
    
    if agent_data['memory_log']:
        prompt += f"\\nRecent memories (last 3): {' | '.join(agent_data['memory_log'][-3:])}"
    else:
        prompt += "\\nRecent memories: None yet."

    prompt += "\\n\\nVillage Overview:"
    prompt += f"\\n  Resources: Food: {world_state['village_resources']['food']}, Wood: {world_state['village_resources']['wood']}, Stone: {world_state['village_resources']['stone']}, Herbs: {world_state['village_resources']['herbs']}"
    
    prompt += "\\n  Active Village Needs:"
    if not world_state['active_needs']:
        prompt += "\\n    - No pressing needs currently identified."
    else:
        for i, need in enumerate(world_state['active_needs']):
            assigned_count = len(need.get('assigned_agents', []))
            progress_percent = need.get('progress', 0.0) * 100
            prompt += f"\\n    {i+1}. ID: {need['need_id']} - {need['description']} (Urgency: {need['urgency']}, Related Skills: {', '.join(need['related_skills'])}, Progress: {progress_percent:.0f}%, Assigned: {assigned_count})"

    prompt += \"\"\"

What is your primary thought process, and what single action will you attempt today?
Consider your skills, status, inventory, and the village's needs.
You can:
- ADDRESS_NEED: Choose a Village Need to work on (specify ID and how your skills apply).
- PERSONAL_ACTION: Hunt, gather, craft (specify item), rest, heal self, explore, improve shelter for self.
- SOCIAL_ACTION: Talk to someone (describe who or their role if known), attempt to trade, propose a new village need, try to organize a group for a task.

Respond ONLY in JSON format like this:
{
  "thought": "I'm quite good at gathering and the village needs food. The food shortage (N001) seems like a good fit for my skills. I'll try to find some edible roots.",
  "action_type": "ADDRESS_NEED",
  "action_details": {
    "need_id": "N001",
    "activity_description": "Search for edible roots and berries in the nearby forest.",
    "expected_contribution_skill": "gathering"
  },
  "speech": "" // Optional: if you say something to the group or another agent
}

// Example for PERSONAL_ACTION (Rest):
// {
//   "thought": "My energy is low. I should rest to recover.",
//   "action_type": "PERSONAL_ACTION",
//   "action_details": {"activity": "rest"},
//   "speech": ""
// }

// Example for SOCIAL_ACTION (Propose Task):
// {
//   "thought": "The north palisade wall (N002) is important. My building skill is low, but maybe I can convince Grok (known for building skill) to help.",
//   "action_type": "SOCIAL_ACTION",
//   "action_details": {"sub_type": "persuade_for_task", "target_description": "Grok (the strong one who likes building)", "task_id_for_collaboration": "N002", "argument": "The wall needs fixing badly, and your skill would be invaluable."},
//   "speech": "Grok, we need to fix that wall. Your strength would be a great help!"
// }
\"\"\"
    return prompt

if __name__ == '__main__':
    # Example usage (for testing the prompter)
    sample_agent_data = {
        "agent_id": "A001", "name": "Elara", "background": "Exiled Herbalist's Apprentice",
        "personality_traits": ["cautious", "observant"],
        "skills": {"hunting": 1, "gathering": 4, "building": 1, "crafting": 2, "healing": 3, "social": 2},
        "status": {"health": 100, "hunger": 10, "energy": 80},
        "inventory": ["worn_pouch", "flint_knife"], "current_focus_need_id": None, "memory_log": ["Found a strange plant."]
    }
    sample_world_state = {
        "day": 1, "season": "Spring", "weather": "Mild",
        "village_resources": {"food": 100, "wood": 50, "stone": 20, "herbs":10, "simple_tools": 2},
        "active_needs": [{"need_id": "N001", "description": "Gather food", "urgency": "high", "related_skills": ["gathering", "hunting"], "progress": 0.1, "assigned_agents": ["A002"]}],
        "events_log": []
    }
    test_prompt = generate_agent_prompt(sample_agent_data, sample_world_state)
    print("--- Example Agent Prompt ---")
    print(test_prompt)
    print("----------------------------")
"""

# sim_engine.py content
SIM_ENGINE_SCRIPT_CONTENT = """
import json
import os
import random
import time # For simulating delay

# Assuming prompter.py and ollama_client.py are in the same directory
import prompter 
# import ollama_client # Uncomment when you have your ollama_client.py ready

# --- Constants ---
AGENT_DATA_PATH = "agents"
WORLD_STATE_FILE = "world_state.json"
MAX_MEMORY_LOG = 10 # Max entries in an agent's short-term memory

# --- Helper Functions ---
def load_world():
    try:
        with open(WORLD_STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: World state file {WORLD_STATE_FILE} not found.")
        return None # Or raise an exception

def save_world(world_data):
    with open(WORLD_STATE_FILE, 'w') as f:
        json.dump(world_data, f, indent=2)

def load_agent(agent_id_filename): # Expects filename like "agent_001.json"
    filepath = os.path.join(AGENT_DATA_PATH, agent_id_filename)
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # print(f"Warning: Agent file {filepath} not found during load.")
        return None 

def save_agent(agent_data):
    filepath = os.path.join(AGENT_DATA_PATH, f"{agent_data['agent_id']}.json")
    with open(filepath, 'w') as f:
        json.dump(agent_data, f, indent=2)

def add_to_memory(agent_data, memory_entry):
    agent_data["memory_log"].append(memory_entry)
    if len(agent_data["memory_log"]) > MAX_MEMORY_LOG:
        agent_data["memory_log"] = agent_data["memory_log"][-MAX_MEMORY_LOG:]

def perform_skill_check(skill_value, difficulty=3, tool_bonus=0):
    # Simple skill check: skill_value (0-5) + tool_bonus vs difficulty (1-5)
    # More randomness can be added.
    # A success is if (skill_value + tool_bonus + random_factor) >= difficulty
    # For now, a simple probabilistic check:
    # Base success chance: 20% per skill point above (difficulty - 2)
    # e.g. skill 3, diff 3: (3 - (3-2)) * 20 = 40% base. Let's refine.
    
    # Simpler: each skill point is ~15% chance. Add a random element.
    # Max skill 5 = 75% + random. Min skill 0 = 0% + random.
    # Let's use a threshold system.
    roll = random.randint(1, 10) # Roll a d10
    target = 6 - skill_value - tool_bonus + difficulty # Higher skill/tool lowers target, higher diff raises it
    return roll >= target # Success if roll meets or beats target

# --- Core Simulation Logic ---
def process_agent_action(agent_data, action_json, world_state):
    # This is a critical function where you'll implement the detailed consequences of actions.
    # It needs to be significantly expanded based on your game's rules.
    
    thought = action_json.get("thought", "No thought recorded.")
    action_type = action_json.get("action_type")
    details = action_json.get("action_details", {})
    speech = action_json.get("speech", "")

    add_to_memory(agent_data, f"Thought: {thought}")
    if speech:
        add_to_memory(agent_data, f"Said: '{speech}'")
        world_state["events_log"].append(f"{agent_data['name']} says: '{speech}'")
        print(f"    {agent_data['name']} says: '{speech}'")

    print(f"    Action Type: {action_type}, Details: {details}")

    # Basic energy/hunger cost for any action
    agent_data["status"]["energy"] = max(0, agent_data["status"]["energy"] - random.randint(3, 7))
    agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + random.randint(1, 3))

    if action_type == "ADDRESS_NEED":
        need_id = details.get("need_id")
        skill_used = details.get("expected_contribution_skill")
        target_need = next((n for n in world_state["active_needs"] if n["need_id"] == need_id), None)

        if target_need and skill_used in agent_data["skills"]:
            agent_data["current_focus_need_id"] = need_id
            if agent_data["agent_id"] not in target_need.get("assigned_agents", []):
                 target_need.setdefault("assigned_agents", []).append(agent_data["agent_id"])
            
            skill_level = agent_data["skills"].get(skill_used, 0)
            # Assume difficulty 3 for most need-based tasks for now
            if perform_skill_check(skill_level, difficulty=3): 
                contribution_amount = random.randint(1, skill_level + 1) # e.g. more food, faster building
                
                if skill_used in ["hunting", "gathering"] and target_need["related_skills"][0] in ["hunting", "gathering"]:
                    world_state["village_resources"]["food"] += contribution_amount
                    add_to_memory(agent_data, f"Successfully contributed {contribution_amount} food to need {need_id} using {skill_used}.")
                    print(f"    {agent_data['name']} gathered/hunted {contribution_amount} food for the village.")
                elif skill_used in ["building", "crafting"]:
                    # Check for materials if specified by the need
                    can_proceed = True
                    if "required_materials" in target_need:
                        for material, amount_needed in target_need["required_materials"].items():
                            # Simple check: assume 1 unit of progress uses 1 unit of material for now
                            if world_state["village_resources"].get(material, 0) < 1 : # Needs 1 unit per contribution tick
                                can_proceed = False
                                add_to_memory(agent_data, f"Tried to work on {need_id}, but village lacked {material}.")
                                print(f"    {agent_data['name']} tried to work on {need_id} but lacked {material}.")
                                break
                        if can_proceed and "required_materials" in target_need: # Deduct materials
                             for material, amount_needed in target_need["required_materials"].items():
                                 if world_state["village_resources"].get(material, 0) > 0:
                                     world_state["village_resources"][material] -=1 # Consume 1 unit

                    if can_proceed:
                        target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.05 * contribution_amount)) # Progress is percentage
                        add_to_memory(agent_data, f"Successfully contributed to {need_id} (progress: {target_need['progress']:.2f}) using {skill_used}.")
                        print(f"    {agent_data['name']} made progress on {need_id}.")
                
                # Generic success message if not covered above
                else:
                     add_to_memory(agent_data, f"Successfully contributed to {need_id} using {skill_used}.")
                     print(f"    {agent_data['name']} successfully contributed to {need_id} using {skill_used}.")


            else: # Skill check failed
                add_to_memory(agent_data, f"Attempted to contribute to {need_id} using {skill_used} but made little progress.")
                print(f"    {agent_data['name']} failed to make significant progress on {need_id} with {skill_used}.")
        else:
            add_to_memory(agent_data, f"Tried to address need {need_id} but it was invalid or skill {skill_used} was missing.")
            print(f"    {agent_data['name']} tried to address an invalid need or lacked the skill.")


    elif action_type == "PERSONAL_ACTION":
        activity = details.get("activity")
        if activity == "rest":
            energy_gained = random.randint(15, 30)
            agent_data["status"]["energy"] = min(100, agent_data["status"]["energy"] + energy_gained)
            add_to_memory(agent_data, f"Rested and gained {energy_gained} energy.")
            print(f"    {agent_data['name']} is resting.")
        elif activity == "eat":
            # Basic eating from inventory - assumes "food" item exists and is generic
            # More complex: check for specific food items
            if "food_item_x1" in agent_data["inventory"]: # Example item
                agent_data["inventory"].remove("food_item_x1")
                hunger_reduced = random.randint(20,40)
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - hunger_reduced)
                add_to_memory(agent_data, f"Ate a food item, hunger reduced by {hunger_reduced}.")
                print(f"    {agent_data['name']} ate a food item.")
            else:
                add_to_memory(agent_data, "Tried to eat but had no personal food.")
                print(f"    {agent_data['name']} tried to eat but had no food.")
        elif activity == "gather_personal":
            if perform_skill_check(agent_data["skills"].get("gathering",0), difficulty=2):
                found_food = random.randint(1,2)
                # Add to personal inventory, e.g. "berries_x{found_food}"
                # For simplicity, let's add a generic item
                agent_data["inventory"].append(f"wild_food_x{found_food}")
                add_to_memory(agent_data, f"Gathered {found_food} wild food for personal use.")
                print(f"    {agent_data['name']} gathered {found_food} wild food personally.")
            else:
                add_to_memory(agent_data, "Tried to gather food personally but found little.")
                print(f"    {agent_data['name']} failed to gather food personally.")

        # Add more personal actions: craft_tool, explore, etc.

    elif action_type == "SOCIAL_ACTION":
        sub_type = details.get("sub_type")
        # Add logic for talking, trading, proposing needs, forming groups
        add_to_memory(agent_data, f"Engaged in social action: {sub_type} - {details.get('target_description','')}")
        print(f"    {agent_data['name']} engaged in social action: {sub_type}.")
        # Example: Proposing a new need
        if sub_type == "propose_need":
            new_need_desc = details.get("need_description", "A new task.")
            related_skills_prop = details.get("related_skills", ["general"])
            # Basic check to avoid too many needs or duplicates
            if len(world_state["active_needs"]) < 10: # Limit total active needs
                new_need_id = f"N_User_{random.randint(1000,9999)}"
                world_state["active_needs"].append({
                    "need_id": new_need_id, "description": f"(Proposed by {agent_data['name']}) {new_need_desc}",
                    "urgency": "medium", "related_skills": related_skills_prop, "progress": 0.0, "assigned_agents": [agent_data["agent_id"]]
                })
                world_state["events_log"].append(f"{agent_data['name']} proposed a new need: {new_need_desc}")
                print(f"    {agent_data['name']} proposed a new need: {new_need_desc}")


    # Clamp status values
    for status_key in ["health", "hunger", "energy"]:
        agent_data["status"][status_key] = max(0, min(100, agent_data["status"][status_key]))


def daily_world_update(world_state, all_agents_data_list):
    print("\\n--- Daily World Update ---")
    world_state["day"] += 1
    world_state["events_log"].append(f"Day {world_state['day']} begins.")

    # Weather changes (simple example)
    weather_options = ["Mild", "Sunny", "Rainy", "Cold", "Windy"]
    world_state["weather"] = random.choice(weather_options)
    world_state["events_log"].append(f"The weather is now {world_state['weather']}.")
    print(f"Weather: {world_state['weather']}")

    # Basic needs generation/escalation (can be more sophisticated)
    if world_state["village_resources"]["food"] < len(all_agents_data_list) * 3 and not any(n["description"].startswith("CRITICAL: Food reserves are dangerously low!") for n in world_state["active_needs"]):
        # Escalate existing food need or create new critical one
        existing_food_need = next((n for n in world_state["active_needs"] if "food" in n["description"].lower()), None)
        if existing_food_need:
            existing_food_need["description"] = "CRITICAL: Food reserves are dangerously low! Gather more immediately!"
            existing_food_need["urgency"] = "critical"
            print("SYSTEM: Food need escalated to CRITICAL.")
        else:
            new_need_id = f"N_Sys_{random.randint(100,999)}"
            world_state["active_needs"].append({
                "need_id": new_need_id, "description": "CRITICAL: Food reserves are dangerously low! Gather more immediately!",
                "urgency": "critical", "related_skills": ["hunting", "gathering"], "progress": 0.0, "assigned_agents": []
            })
            print("SYSTEM: Generated new CRITICAL need - Low Food.")
            world_state["events_log"].append("A critical need for food has arisen!")


    # Remove completed needs
    initial_need_count = len(world_state["active_needs"])
    world_state["active_needs"] = [n for n in world_state["active_needs"] if n.get("progress", 0.0) < 1.0]
    if len(world_state["active_needs"]) < initial_need_count:
        completed_count = initial_need_count - len(world_state["active_needs"])
        print(f"SYSTEM: {completed_count} village need(s) completed.")
        world_state["events_log"].append(f"{completed_count} village need(s) were completed.")


    # Agent status updates (hunger, health from hunger/cold)
    for agent_data in all_agents_data_list:
        if agent_data["status"]["health"] <= 0: continue # Skip dead agents

        # Food consumption from village stockpile (if available and agent is hungry enough)
        # More complex: agents decide if they eat from stockpile or personal inventory
        if agent_data["status"]["hunger"] > 30: # Agent is somewhat hungry
            food_to_eat = 2 # Standard portion
            if world_state["village_resources"]["food"] >= food_to_eat:
                world_state["village_resources"]["food"] -= food_to_eat
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - random.randint(25, 40)) # Eating reduces hunger
                add_to_memory(agent_data, f"Ate from village stockpile. Hunger now {agent_data['status']['hunger']}.")
            else: # Not enough village food
                agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + 5) # Gets hungrier
                add_to_memory(agent_data, "Wanted to eat from stockpile, but it was empty.")
                if agent_data["status"]["hunger"] > 70: # Starvation effect
                    agent_data["status"]["health"] = max(0, agent_data["status"]["health"] - random.randint(3,8))
                    add_to_memory(agent_data, f"Starvation taking a toll. Health is now {agent_data['status']['health']}.")
                    world_state["events_log"].append(f"{agent_data['name']} is suffering from starvation.")
        
        # Weather effects
        if world_state["weather"] == "Cold" and agent_data["status"]["energy"] < 30: # Example: cold affects tired agents
            agent_data["status"]["health"] = max(0, agent_data["status"]["health"] - random.randint(1,4))
            add_to_memory(agent_data, f"The cold is biting. Health is now {agent_data['status']['health']}.")
        
        if agent_data["status"]["health"] <= 0:
            world_state["events_log"].append(f"TRAGEDY: {agent_data['name']} has perished from poor health!")
            print(f"TRAGEDY: {agent_data['name']} ({agent_data['agent_id']}) has perished!")
            # The agent will be filtered out in the next day's agent loading process.
        
        save_agent(agent_data) # Save updated agent status


def run_simulation(num_days=10, use_mock_llm=True):
    world = load_world()
    if not world:
        print("Failed to load world. Exiting.")
        return

    agent_filenames = [f for f in os.listdir(AGENT_DATA_PATH) if f.startswith("agent_") and f.endswith(".json")]
    
    for day_num in range(1, num_days + 1):
        print(f"\\n{'='*10} DAY {world['day']} ({world['season']}, {world['weather']}) {'='*10}")
        print(f"Resources: Food={world['village_resources']['food']}, Wood={world['village_resources']['wood']}, Stone={world['village_resources']['stone']}")
        print("Active Needs:")
        for need in world['active_needs']:
            print(f"  - ID: {need['need_id']}, Desc: {need['description'][:50]}... (Progress: {need.get('progress',0.0)*100:.0f}%)")

        current_day_agents_data = []
        for agent_filename in agent_filenames:
            agent = load_agent(agent_filename)
            if agent and agent["status"]["health"] > 0: # Only process living agents
                 current_day_agents_data.append(agent)
        
        if not current_day_agents_data:
            print("\\n--- VILLAGE HAS PERISHED ---")
            world_state["events_log"].append("The last survivor has fallen. The village is lost.")
            break

        random.shuffle(current_day_agents_data) # Randomize agent turn order each day

        for agent_data in current_day_agents_data:
            print(f"\\nProcessing turn for: {agent_data['name']} ({agent_data['agent_id']}) | Health:{agent_data['status']['health']}, Hunger:{agent_data['status']['hunger']}, Energy:{agent_data['status']['energy']}")

            # Reset focus if their focused need is completed or gone
            if agent_data["current_focus_need_id"]:
                focused_need_exists = any(n["need_id"] == agent_data["current_focus_need_id"] for n in world["active_needs"])
                if not focused_need_exists:
                    add_to_memory(agent_data, f"My focused need {agent_data['current_focus_need_id']} is no longer active.")
                    agent_data["current_focus_need_id"] = None
            
            # --- LLM Call ---
            prompt_text = prompter.generate_agent_prompt(agent_data, world)
            
            llm_response_str = None
            if use_mock_llm:
                # MOCK LLM RESPONSE - Replace with actual ollama_client.call_model
                print(f"  (Mock LLM) Generating action for {agent_data['name']}...")
                time.sleep(0.1) # Simulate LLM processing time
                
                mock_actions = []
                # Try to address a need if available
                if world["active_needs"]:
                    # Prefer focused need if still valid
                    focused_need = None
                    if agent_data["current_focus_need_id"]:
                        focused_need = next((n for n in world["active_needs"] if n["need_id"] == agent_data["current_focus_need_id"]), None)
                    
                    need_to_address = focused_need
                    if not need_to_address: # Pick a random need if not focused or focus invalid
                         need_to_address = random.choice(world["active_needs"])

                    relevant_skills = [s for s in agent_data["skills"] if s in need_to_address["related_skills"] and agent_data["skills"][s] > 0]
                    if relevant_skills:
                        chosen_skill = random.choice(relevant_skills)
                        mock_actions.append({
                            "thought": f"I will continue working on {need_to_address['need_id']} using my {chosen_skill} skill.",
                            "action_type": "ADDRESS_NEED",
                            "action_details": {"need_id": need_to_address['need_id'], "activity_description": f"Work on {need_to_address['description']}", "expected_contribution_skill": chosen_skill},
                            "speech": random.choice(["", f"I'll help with {need_to_address['description'][:20]}.", "Working on it."])
                        })
                
                # Personal action: rest if energy is low
                if agent_data["status"]["energy"] < 40:
                    mock_actions.append({"thought": "I'm tired, I should rest.", "action_type": "PERSONAL_ACTION", "action_details": {"activity": "rest"}, "speech": ""})
                
                # Personal action: gather food if hungry and good at it
                if agent_data["status"]["hunger"] > 50 and agent_data["skills"].get("gathering",0) > 2:
                     mock_actions.append({"thought": "I'm hungry, I'll try to find some food for myself.", "action_type": "PERSONAL_ACTION", "action_details": {"activity": "gather_personal"}, "speech": ""})

                if not mock_actions: # Default action if no specific conditions met
                    mock_actions.append({"thought": "I will rest for a bit to conserve energy.", "action_type": "PERSONAL_ACTION", "action_details": {"activity": "rest"}, "speech": ""})

                llm_response_str = json.dumps(random.choice(mock_actions))
            else:
                # print(f"  Prompt for {agent_data['name']}:\\n{prompt_text[:300]}...") # Log part of the prompt
                # llm_response_str = ollama_client.call_model(prompt_text) # UNCOMMENT FOR ACTUAL LLM
                print("ERROR: Real LLM call is commented out. Set use_mock_llm=True or implement ollama_client.")
                return 

            # --- Process LLM Response ---
            if llm_response_str:
                try:
                    action_json = json.loads(llm_response_str)
                    process_agent_action(agent_data, action_json, world)
                except json.JSONDecodeError:
                    print(f"  ERROR: Failed to decode JSON from LLM for {agent_data['name']}: {llm_response_str}")
                    add_to_memory(agent_data, "SYSTEM_ERROR: My thoughts were jumbled and my action was unclear.")
                except Exception as e:
                    print(f"  ERROR: Unexpected error processing action for {agent_data['name']}: {e}")
                    add_to_memory(agent_data, f"SYSTEM_ERROR: An unexpected issue occurred: {str(e)[:50]}")
            else:
                print(f"  ERROR: No response from LLM for {agent_data['name']}.")
                add_to_memory(agent_data, "SYSTEM_ERROR: I was unable to decide on an action.")

            save_agent(agent_data) # Save agent state after their turn

        # --- End of Day ---
        daily_world_update(world, current_day_agents_data) # Pass list of agents active that day
        save_world(world)

        if world['day'] >= num_days:
            print("\\n--- SIMULATION ENDED: Specified number of days reached. ---")
            break
        
        # Check for end condition (e.g. all agents perished) is handled at the start of the loop

    print("\\nFinal world state saved.")
    print("Events Log:")
    for entry in world.get("events_log", [])[-20:]: # Print last 20 events
        print(f"- {entry}")

if __name__ == "__main__":
    # This will run when the script is executed
    # You might want to add a check here to see if files already exist
    # or add command-line arguments for number of days, etc.
    print("Starting simulation engine...")
    run_simulation(num_days=5, use_mock_llm=True) # Run for 5 days with mock LLM for testing
"""

# ollama_client.py content
OLLAMA_CLIENT_SCRIPT_CONTENT = """
import json
# import requests # Example if using requests library for Ollama API

# This is a VERY basic placeholder for your Ollama client.
# You will need to implement the actual API call to your local Ollama instance.

# Example: If Ollama is running on http://localhost:11434
# OLLAMA_API_URL = "http://localhost:11434/api/generate" 
# DEFAULT_MODEL = "gemma:2b" # Or whatever model you are using

def call_model(prompt_text, model_name="gemma:2b", temperature=0.7):
    \"\"\"
    Placeholder function to simulate a call to a local LLM via Ollama.
    Replace this with your actual implementation.
    
    Args:
        prompt_text (str): The full prompt to send to the LLM.
        model_name (str): The name of the Ollama model to use.
        temperature (float): The temperature for generation.

    Returns:
        str: The JSON response string from the LLM, or a default error JSON.
    \"\"\"
    print(f"--- OLLAMA CLIENT (Placeholder) ---")
    print(f"Model: {model_name}, Temp: {temperature}")
    # print(f"Prompt (first 100 chars): {prompt_text[:100]}...")
    print(f"NOTE: This is a placeholder. No actual LLM call is being made.")
    print(f"Returning a default 'rest' action.")
    print(f"------------------------------------")

    # Simulate a delay as if an LLM was processing
    import time
    time.sleep(0.5) # Simulate a short delay

    # Default fallback response if the actual call fails or isn't implemented
    default_response = {
        "thought": "Placeholder: I am resting because the Ollama client is not fully implemented.",
        "action_type": "PERSONAL_ACTION",
        "action_details": {"activity": "rest"},
        "speech": "I need to rest... (Ollama client placeholder)"
    }
    return json.dumps(default_response)

# Example of how you might structure an actual request (pseudo-code):
# def call_ollama_real(prompt_text, model_name=DEFAULT_MODEL, temperature=0.7):
#     payload = {
#         "model": model_name,
#         "prompt": prompt_text,
#         "format": "json", # Crucial for getting JSON output directly if model supports it
#         "stream": False, # Get the full response at once
#         "options": {
#             "temperature": temperature
#         }
#     }
#     try:
#         response = requests.post(OLLAMA_API_URL, json=payload)
#         response.raise_for_status() # Raise an exception for HTTP errors
#         
#         # Ollama's non-streaming JSON output often has the JSON string within a "response" key
#         # response_data = response.json()
#         # json_string = response_data.get("response", "{}") 
#         # return json_string 
#         
#         # If "format":"json" is used in payload, response.text might be the direct JSON string
#         return response.text # Assuming this is the JSON string
#
#     except requests.exceptions.RequestException as e:
#         print(f"Error calling Ollama: {e}")
#         return json.dumps({
#             "thought": f"Error: Could not connect to Ollama or model error. Details: {str(e)}",
#             "action_type": "PERSONAL_ACTION", "action_details": {"activity": "error_idle"}, "speech": "I feel confused."
#         })


if __name__ == '__main__':
    # Test the placeholder
    sample_prompt = "You are a test agent. What do you do? Respond in JSON."
    response_json_str = call_model(sample_prompt)
    print("\\n--- Ollama Client Test Response ---")
    try:
        parsed_response = json.loads(response_json_str)
        print(json.dumps(parsed_response, indent=2))
    except json.JSONDecodeError:
        print(f"Error decoding placeholder JSON: {response_json_str}")
    print("---------------------------------")
"""

# --- Main Generation Script Logic ---
def generate_files():
    print("Starting file generation...")

    # Create agents directory
    if not os.path.exists(AGENT_DATA_PATH):
        os.makedirs(AGENT_DATA_PATH)
        print(f"Created directory: {AGENT_DATA_PATH}")

    # Generate agent files
    used_names = set()
    for i in range(1, NUM_AGENTS + 1):
        agent_id = f"agent_{str(i).zfill(3)}" # e.g., agent_001

        # Ensure unique names if possible, otherwise append number
        name = random.choice(POSSIBLE_NAMES)
        original_name = name
        name_suffix = 1
        while name in used_names:
            name = f"{original_name}_{name_suffix}"
            name_suffix += 1
        used_names.add(name)

        background = random.choice(POSSIBLE_BACKGROUNDS)
        num_traits = random.randint(2, 3)
        traits = random.sample(POSSIBLE_PERSONALITY_TRAITS, num_traits)
        
        # Distribute skill points
        skills = {skill: 0 for skill in POSSIBLE_SKILLS}
        points_to_distribute = TOTAL_SKILL_POINTS_BUDGET
        for _ in range(points_to_distribute):
            chosen_skill = random.choice(POSSIBLE_SKILLS)
            if skills[chosen_skill] < 5: # Max skill level 5
                 skills[chosen_skill] += 1
            else: # If skill is maxed, try to give point to another skill
                for skill_option in random.sample(POSSIBLE_SKILLS, len(POSSIBLE_SKILLS)): # shuffle
                    if skills[skill_option] < 5:
                        skills[skill_option] +=1
                        break


        agent_data = {
            "agent_id": agent_id,
            "name": name,
            "background": background,
            "personality_traits": traits,
            "skills": skills,
            "status": {
                "health": 100,
                "hunger": random.randint(0, 20), # Start not too hungry
                "energy": random.randint(70, 100) # Start with good energy
            },
            "inventory": list(INITIAL_INVENTORY_ITEMS) + [f"personal_trinket_{random.randint(1,100)}"],
            "current_focus_need_id": None,
            "memory_log": [f"Woke up feeling {random.choice(['hopeful', 'anxious', 'determined'])}."]
        }
        with open(os.path.join(AGENT_DATA_PATH, f"{agent_id}.json"), 'w') as f:
            json.dump(agent_data, f, indent=2)
    print(f"Generated {NUM_AGENTS} agent files in '{AGENT_DATA_PATH}/'")

    # Generate world_state.json
    with open(WORLD_STATE_FILE, 'w') as f:
        json.dump(INITIAL_WORLD_STATE, f, indent=2)
    print(f"Generated {WORLD_STATE_FILE}")

    # Generate prompter.py
    with open(PROMPTER_FILE, 'w') as f:
        f.write(PROMPTER_SCRIPT_CONTENT)
    print(f"Generated {PROMPTER_FILE}")

    # Generate sim_engine.py
    with open(SIM_ENGINE_FILE, 'w') as f:
        f.write(SIM_ENGINE_SCRIPT_CONTENT)
    print(f"Generated {SIM_ENGINE_FILE}")
    
    # Generate ollama_client.py
    with open(OLLAMA_CLIENT_FILE, 'w') as f:
        f.write(OLLAMA_CLIENT_SCRIPT_CONTENT)
    print(f"Generated {OLLAMA_CLIENT_FILE}")

    print("\nFile generation complete!")
    print(f"To run the simulation (with mock LLM responses by default), execute: python {SIM_ENGINE_FILE}")

if __name__ == "__main__":
    generate_files()
