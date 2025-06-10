import json
import random
import re
import os 
from action_handler import execute_action
from game_utils import convert_inventory_to_dict_format # This import will now work
import config # Added to use config.OLLAMA_DEFAULT_MODEL

AGENT_DATA_PATH = "agents" 

# --- Data for Dynamic Agent Creation ---
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
TOTAL_SKILL_POINTS_BUDGET_FOR_CREATION = 14
# --- End of Data for Dynamic Agent Creation ---


# --- Helper Functions ---

def get_shelter_description(shelter_level): 
    if shelter_level == 0: return "exposed to the elements"
    if shelter_level == 1: return "a crude lean-to"
    if shelter_level == 2: return "a basic hut"
    if shelter_level == 3: return "a sturdy hut"
    if shelter_level >= 4: return "a well-built dwelling"
    return "an unknown shelter"

SHELTER_UPGRADE_COSTS = {
    1: {"wood_scraps": 10, "herbs_bundle": 2},
    2: {"wood_scraps": 20, "stone_chip": 5},   
    3: {"wood_scraps": 30, "stone_chip": 10, "food_rations": 1}, 
}

MAX_MEMORY_LOG = 10 

def add_to_memory(agent_data, memory_entry):
    if "memory_log" not in agent_data: 
        agent_data["memory_log"] = []
    agent_data["memory_log"].append(memory_entry)
    if len(agent_data["memory_log"]) > MAX_MEMORY_LOG:
        agent_data["memory_log"] = agent_data["memory_log"][-MAX_MEMORY_LOG:]

def perform_skill_check(skill_value, difficulty=3, tool_bonus=0):
    roll = random.randint(1, 10) + tool_bonus 
    target = 7 - skill_value + difficulty 
    return roll >= target

def handle_agent_resource_allocation(agent_data, world_state, resource_type, amount_acquired, 
                                     use_mock_llm, ollama_client_func, prompter_module, config_module=None):
    if amount_acquired <= 0:
        return f"Found no {resource_type.replace('_',' ')}."

    narration = f"managed to acquire {amount_acquired} {resource_type.replace('_',' ')}!"
    
    allocation_prompt = prompter_module.generate_resource_allocation_prompt(agent_data, resource_type, amount_acquired, world_state) # Added world_state
    llm_full_response_str = None 
    
    debug_mode = getattr(config_module, 'DEBUG_MODE', False) if config_module else False
    allocation_json_str_from_llm = None 

    if use_mock_llm:
        to_personal = 0
        to_village = 0
        if "generous" in agent_data.get("personality_traits", []) and \
           "selfish" not in agent_data.get("personality_traits", []) and \
           "greedy" not in agent_data.get("personality_traits", []):
            to_personal = random.randint(0, amount_acquired // 2)
        elif "selfish" in agent_data.get("personality_traits", []) or \
             "greedy" in agent_data.get("personality_traits", []):
            to_personal = random.randint(amount_acquired // 2, amount_acquired)
        else:
            to_personal = amount_acquired // 2 
        
        to_personal = min(to_personal, amount_acquired)
        to_village = amount_acquired - to_personal
        
        mock_allocation = {
            "allocation_thought": f"Mock: Decided to keep {to_personal} and share {to_village} of the {resource_type}.",
            "allocation": { # Changed from allocate_to_personal/village to match prompter
                 "personal_stash": to_personal,
                 "village_contribution": to_village
            }
        }
        allocation_json_str_from_llm = json.dumps(mock_allocation) 
    else:
        if not ollama_client_func: 
            print("!!! CRITICAL ERROR (agent_manager): ollama_client_func not provided for resource allocation.")
            allocation_json_str_from_llm = json.dumps({ 
                "allocation_thought": "Error: LLM client function missing. Defaulting allocation.",
                 "allocation": {"personal_stash": 0, "village_contribution": amount_acquired}
            })
        else:
            model_name_for_allocation = config.OLLAMA_DEFAULT_MODEL if hasattr(config, 'OLLAMA_DEFAULT_MODEL') else "gemma:2b"
            
            if debug_mode:
                print(f"DEBUG (agent_manager): Allocation Prompt for {agent_data['name']}:\n{allocation_prompt[:500]}...")

            llm_full_response_str = ollama_client_func(allocation_prompt, model_name_for_allocation)
            
            if debug_mode:
                print(f"DEBUG (agent_manager): Raw Full LLM Allocation Response for {agent_data['name']}: {llm_full_response_str}")
            
            try:
                ollama_response_obj = json.loads(llm_full_response_str)
                allocation_json_str_from_llm = ollama_response_obj.get("response")
                if debug_mode and allocation_json_str_from_llm:
                    print(f"DEBUG (agent_manager): Extracted 'response' field for allocation: {allocation_json_str_from_llm[:200]}...")
                elif debug_mode and not allocation_json_str_from_llm : # Added check for missing allocation_json_str_from_llm
                    print(f"DEBUG (agent_manager): 'response' field missing or empty in LLM allocation output. Full response: {llm_full_response_str}")
                    allocation_json_str_from_llm = json.dumps({
                        "allocation_thought": "Error: LLM 'response' field missing. Defaulting.",
                        "allocation": {"personal_stash": 0, "village_contribution": amount_acquired}
                    })


            except json.JSONDecodeError:
                print(f"  ERROR: Failed to parse initial LLM allocation response structure for {agent_data['name']}. Response: {llm_full_response_str[:200]}")
                allocation_json_str_from_llm = json.dumps({ 
                    "allocation_thought": "Error: LLM response structure unparseable. Defaulting allocation.",
                    "allocation": {"personal_stash": 0, "village_contribution": amount_acquired}
                })

    try:
        if not allocation_json_str_from_llm: 
            # This case should be handled by the debug log above, but as a safeguard:
            print(f"  ERROR: No valid JSON string obtained from LLM for allocation for {agent_data['name']}. Defaulting.")
            allocation_decision = {
                "allocation_thought": "Error: No valid JSON from LLM. Defaulting.",
                "allocation": {"personal_stash": 0, "village_contribution": amount_acquired}
            }
        else:
            allocation_decision = json.loads(allocation_json_str_from_llm)

        if debug_mode:
            print(f"DEBUG (agent_manager): Parsed Final LLM Allocation JSON for {agent_data['name']}: {allocation_decision}")
        
        # Using the keys as defined in the prompter.py for allocation
        allocation_details = allocation_decision.get("allocation", {})
        personal_gain = allocation_details.get("personal_stash", 0)
        village_gain = allocation_details.get("village_contribution", 0)


        if not (isinstance(personal_gain, int) and isinstance(village_gain, int) and \
                personal_gain >= 0 and village_gain >= 0 and \
                (personal_gain + village_gain == amount_acquired)): 
            print(f"  Warning: Invalid allocation numbers by {agent_data['name']} for {resource_type} (p:{personal_gain}, v:{village_gain}, total:{amount_acquired}). Sum was {personal_gain + village_gain}. Defaulting to all personal.")
            add_to_memory(agent_data, f"Error in allocating {resource_type}. Kept all.")
            personal_gain = amount_acquired
            village_gain = 0
        
        # Use personal_resources for raw materials, inventory for crafted items/tools
        # Assuming resource_type here refers to a raw material for personal_resources
        agent_data.setdefault("personal_resources", {}) 
        if personal_gain > 0:
            agent_data["personal_resources"][resource_type] = agent_data["personal_resources"].get(resource_type, 0) + personal_gain
            narration += f" Kept {personal_gain} for their personal resources."
            add_to_memory(agent_data, f"Allocated {personal_gain} {resource_type} to personal resources.")

        if village_gain > 0:
            # Ensure the resource_type is valid for village_resources or map it (e.g. food_rations -> food)
            village_resource_key = resource_type 
            if resource_type == "food_rations" and "food" in world_state["village_resources"]: 
                village_resource_key = "food"
            elif resource_type == "wood_scraps" and "wood" in world_state["village_resources"]:
                 village_resource_key = "wood"
            
            world_state["village_resources"][village_resource_key] = world_state["village_resources"].get(village_resource_key, 0) + village_gain
            narration += f" Contributed {village_gain} to the village."
            add_to_memory(agent_data, f"Contributed {village_gain} {resource_type} to village ({village_resource_key}).")
        
        if allocation_decision.get("allocation_thought"):
            add_to_memory(agent_data, f"Allocation thought: {allocation_decision['allocation_thought'][:100]}")

    except json.JSONDecodeError as e:
        narration += f" But seemed unsure how to divide it (error: {e}), so they kept it all for their personal resources."
        agent_data.setdefault("personal_resources", {})
        agent_data["personal_resources"][resource_type] = agent_data["personal_resources"].get(resource_type, 0) + amount_acquired
        add_to_memory(agent_data, f"Error decoding allocation for {resource_type}. Kept all for personal resources.")
    except Exception as e:
        narration += f" But an error occurred during allocation ({e}), so they kept it all for personal resources."
        agent_data.setdefault("personal_resources", {})
        agent_data["personal_resources"][resource_type] = agent_data["personal_resources"].get(resource_type, 0) + amount_acquired
        add_to_memory(agent_data, f"Exception during allocation for {resource_type}. Kept all for personal resources.")
        
    return narration

async def process_agent_turn(
    agent_data,
    world_data,
    all_agents_data,
    prompter_module,
    ollama_client_func=None,
    use_mock_llm=True,
    config_module=None # Pass config module
):
    debug_mode = getattr(config_module, "DEBUG_MODE", False) if config_module else False

    if not isinstance(agent_data.get("inventory"), dict):
        agent_data["inventory"] = convert_inventory_to_dict_format(agent_data.get("inventory", []))

    prompt_text = prompter_module.generate_agent_prompt(agent_data, world_data)
    action_json = None # Initialize action_json

    if use_mock_llm or ollama_client_func is None:
        action_json = {
            "thought": "Mock decision: I will try to gather sturdy branches for the village.",
            "action_type": "ADDRESS_NEED", # Example action type
            "action_details": {
                "need_id": "N_Sys_002", # Example, ensure this is a valid need ID if testing
                "activity_description": "Gather sturdy branches for shelter improvements",
                "expected_contribution_skill": "gathering"
            },
            "speech": "I'll look for some sturdy branches."
        }
        # Ensure mock resource_id is valid if using gather_resource
        if action_json["action_type"] == "PERSONAL_ACTION" and action_json["action_details"].get("activity") == "gather_resource":
            if not hasattr(config_module, 'GATHERABLE_PERSONAL_RESOURCES') or not config_module.GATHERABLE_PERSONAL_RESOURCES:
                 action_json["action_details"]["resource_id"] = "sturdy_branch" # Fallback if config not available
            else:
                 action_json["action_details"]["resource_id"] = random.choice(list(config_module.GATHERABLE_PERSONAL_RESOURCES.keys()))


    else:
        # Use the model name from config
        model_to_use = config.OLLAMA_DEFAULT_MODEL if hasattr(config, 'OLLAMA_DEFAULT_MODEL') else "llama3.2:latest"
        raw_ollama_response_str = ollama_client_func(prompt_text, model_name=model_to_use)
        
        parsed_game_action = None 

        try:
            ollama_shell = json.loads(raw_ollama_response_str)
            model_generated_json_str = ollama_shell.get("response")

            if model_generated_json_str and isinstance(model_generated_json_str, str):
                try:
                    parsed_game_action = json.loads(model_generated_json_str)
                except json.JSONDecodeError as inner_e:
                    if debug_mode:
                        print(f"⚠️ DEBUG: Failed to parse inner JSON from LLM 'response' field for {agent_data['name']}. Error: {inner_e}. Inner JSON string: '{model_generated_json_str[:500]}'")
                    match = re.search(r"{\s*\"thought\":.*}", model_generated_json_str, flags=re.DOTALL)
                    if match:
                        try:
                            parsed_game_action = json.loads(match.group(0))
                        except json.JSONDecodeError:
                             if debug_mode:
                                print(f"⚠️ DEBUG: Regex on inner JSON failed for {agent_data['name']}.")
                    if not parsed_game_action:
                        parsed_game_action = {"action_type": "error_parsing_inner_json", "action_details": {"raw_inner_json": model_generated_json_str[:200]}}
            elif model_generated_json_str and isinstance(model_generated_json_str, dict) : # If response field is already a dict
                 parsed_game_action = model_generated_json_str
            else: # 'response' field was missing, empty, or not a string/dict
                if debug_mode:
                    print(f"⚠️ DEBUG: 'response' field missing, empty or invalid type in LLM output for {agent_data['name']}. Type: {type(model_generated_json_str)}. Full Ollama response: {raw_ollama_response_str[:500]}")
                parsed_game_action = {"action_type": "error_missing_or_invalid_response_field", "action_details": {}}

        except json.JSONDecodeError as outer_e:
            if debug_mode:
                print(f"⚠️ DEBUG: Failed to parse outer Ollama JSON shell for {agent_data['name']}. Error: {outer_e}. Raw response: '{raw_ollama_response_str[:500]}'")
            match = re.search(r"{\s*\"thought\":.*}", raw_ollama_response_str, flags=re.DOTALL)
            if match:
                try:
                    parsed_game_action = json.loads(match.group(0))
                except json.JSONDecodeError as regex_e:
                    if debug_mode:
                        print(f"⚠️ DEBUG: Regex fallback failed to parse JSON for {agent_data['name']}. Error: {regex_e}")
                    parsed_game_action = {"action_type": "error_parsing_json_regex_failed", "action_details": {}}
            else: 
                parsed_game_action = {"action_type": "error_parsing_json_no_match", "action_details": {}}
        
        except Exception as e: 
            if debug_mode:
                 print(f"⚠️ DEBUG: Unexpected error processing LLM response for {agent_data['name']}: {e}. Raw: {raw_ollama_response_str[:500]}")
            parsed_game_action = {"action_type": "error_unexpected_llm_processing", "action_details": {"error": str(e)}}

        action_json = parsed_game_action
        if not isinstance(action_json, dict): 
            action_json = {"action_type": "error_final_parsing_fallback", "action_details": {}}


    narration = execute_action(
        agent_data,
        action_json, # This is now the correctly parsed game action JSON
        world_data,
        all_agents_data,
        ollama_client_func, # Pass along for potential nested calls (like allocation)
        prompter_module,   # Pass along for potential nested calls
    )

    print(f"  -> {narration}")
    return narration
    
def create_initial_agents(num_agents, prompter_module_ref=None, config_module_ref=None):
    all_agents = {}
    print(f"Dynamically creating {num_agents} initial agents...")
    
    used_names = set()
    for i in range(1, num_agents + 1):
        agent_id = f"agent_{str(i).zfill(3)}"
        
        name = random.choice(POSSIBLE_NAMES_FOR_CREATION)
        original_name = name
        name_suffix = 1
        while name in used_names: 
            name = f"{original_name}_{name_suffix}"
            name_suffix += 1
        used_names.add(name)

        background = random.choice(POSSIBLE_BACKGROUNDS_FOR_CREATION)
        num_traits = random.randint(2, 4) 
        traits = random.sample(POSSIBLE_PERSONALITY_TRAITS_FOR_CREATION, num_traits)
        
        skills = {skill: 0 for skill in POSSIBLE_SKILLS_FOR_CREATION}
        points_to_distribute = TOTAL_SKILL_POINTS_BUDGET_FOR_CREATION
        for _ in range(points_to_distribute):
            chosen_skill = random.choice(POSSIBLE_SKILLS_FOR_CREATION)
            if skills[chosen_skill] < 5:
                 skills[chosen_skill] += 1
            else: 
                skill_options = random.sample(POSSIBLE_SKILLS_FOR_CREATION, len(POSSIBLE_SKILLS_FOR_CREATION))
                for sk_opt in skill_options:
                    if skills[sk_opt] < 5:
                        skills[sk_opt] +=1
                        break
        
        current_agent_inventory = INITIAL_AGENT_INVENTORY_TEMPLATE.copy()
        current_agent_inventory["food_rations"] = random.randint(0,2)

        agent_data = {
            "agent_id": agent_id, 
            "name": name, 
            "background": background,
            "personality_traits": traits, 
            "skills": skills,
            "status": { "health": 100, "hunger": random.randint(0, 25), "energy": random.randint(65, 100)},
            "inventory": current_agent_inventory, 
            "personal_resources": {}, # Initialize empty personal_resources
            "shelter_level": 0, 
            "current_focus_need_id": None,
            "memory_log": [f"Woke up feeling {random.choice(['hopeful', 'anxious', 'determined', 'weary'])}."]
        }
        all_agents[agent_id] = agent_data
    
    print(f"Successfully created {len(all_agents)} agents dynamically.")
    return all_agents

def migrate_all_loaded_agents_inventories(all_agents_data_dict):
    if not isinstance(all_agents_data_dict, dict):
        print("Warning (agent_manager): migrate_all_loaded_agents_inventories expects a dictionary of agent data.")
        return

    for agent_id, agent_data in all_agents_data_dict.items():
        if not isinstance(agent_data, dict):
            print(f"Warning (agent_manager): Agent data for {agent_id} is not a dictionary. Skipping inventory migration.")
            continue
        
        inventory = agent_data.get("inventory")
        if isinstance(inventory, list) or inventory is None or not isinstance(inventory, dict) : 
            agent_name = agent_data.get('name', agent_id)
            if isinstance(inventory, list):
                 print(f"  Migrating inventory for {agent_name} (ID: {agent_id}) from list to dict (via agent_manager)...")
            elif inventory is None:
                 print(f"  Initializing missing inventory for {agent_name} (ID: {agent_id}) as empty dict (via agent_manager)...")
            elif not isinstance(inventory, dict):
                 print(f"  Warning: Inventory for {agent_name} (ID: {agent_id}) is an unexpected type: {type(inventory)}. Resetting (via agent_manager).")
            
            agent_data["inventory"] = convert_inventory_to_dict_format(inventory)
        
        # Ensure personal_resources exists
        if "personal_resources" not in agent_data or not isinstance(agent_data["personal_resources"], dict):
            agent_data["personal_resources"] = {}