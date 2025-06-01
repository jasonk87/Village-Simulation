import json
import os
import random
import time

import prompter 
import game_utils # Added import

# ollama_client will be imported dynamically if not using mock

AGENT_DATA_PATH = "agents"
WORLD_STATE_FILE = "world_state.json" 
MAX_MEMORY_LOG = 10

ollama_client = None 

# --- Inventory Migration Helper ---
# REMOVED local definition of convert_inventory_to_dict_format
# It will now be imported from game_utils.py

def migrate_all_agents_inventories(all_agents_data_dict):
    if not isinstance(all_agents_data_dict, dict):
        print("Warning: migrate_all_agents_inventories expects a dictionary of agent data.")
        return

    for agent_id, agent_data in all_agents_data_dict.items():
        if not isinstance(agent_data, dict):
            print(f"Warning: Agent data for {agent_id} is not a dictionary. Skipping inventory migration.")
            continue
        
        inventory = agent_data.get("inventory") 
        if isinstance(inventory, list):
            agent_name = agent_data.get('name', agent_id) 
            print(f"  Migrating inventory for {agent_name} from list to dict (via migrate_all_agents_inventories)...")
            agent_data["inventory"] = game_utils.convert_inventory_to_dict_format(inventory) #MODIFIED
        elif inventory is None:
            agent_data["inventory"] = {}
        elif not isinstance(inventory, dict):
            agent_name = agent_data.get('name', agent_id)
            print(f"Warning: Inventory for {agent_name} is an unexpected type: {type(inventory)}. Resetting to empty dict.")
            agent_data["inventory"] = {}

# --- Core Simulation Functions ---
def get_status_description(agent_data):
    health, hunger, energy = agent_data["status"]["health"], agent_data["status"]["hunger"], agent_data["status"]["energy"]
    health_desc = "Healthy"
    if 40 <= health < 70: health_desc = "Injured"
    elif health < 40: health_desc = "Critically Wounded"
    hunger_desc = "Full"
    if 21 <= hunger <= 50: hunger_desc = "Peckish"
    elif 51 <= hunger <= 80: hunger_desc = "Hungry"
    elif hunger > 80: hunger_desc = "Starving"
    energy_desc = "Energetic"
    if 40 <= energy < 70: energy_desc = "Fatigued"
    elif energy < 40: energy_desc = "Exhausted"
    return f"{health_desc}, {hunger_desc}, {energy_desc}"

def load_world():
    try:
        with open(WORLD_STATE_FILE, 'r') as f: return json.load(f)
    except FileNotFoundError: 
        print(f"Warning: {WORLD_STATE_FILE} not found. A new one might be created or loaded by main logic.")
        return None

def save_world(world_data):
    try:
        with open(WORLD_STATE_FILE, 'w') as f: 
            json.dump(world_data, f, indent=2)
    except Exception as e:
        print(f"Error saving world state: {e}")

def load_agent(agent_filename): 
    filepath = os.path.join(AGENT_DATA_PATH, agent_filename) 
    try:
        with open(filepath, 'r') as f: return json.load(f)
    except FileNotFoundError: 
        return None

def save_agent(agent_data):
    filepath = os.path.join(AGENT_DATA_PATH, f"{agent_data['agent_id']}.json")
    try:
        with open(filepath, 'w') as f: json.dump(agent_data, f, indent=2)
    except Exception as e:
        print(f"Error saving agent {agent_data['agent_id']}: {e}")

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

def handle_resource_acquisition_and_allocation(agent_data, world_state, resource_type, amount_acquired, use_mock_llm_for_allocation):
    if amount_acquired <= 0:
        return f"Found no {resource_type.replace('_',' ')}."

    narration = f"managed to acquire {amount_acquired} {resource_type.replace('_',' ')}!"
    
    allocation_prompt = prompter.generate_resource_allocation_prompt(agent_data, resource_type, amount_acquired)
    allocation_response_str = None

    if use_mock_llm_for_allocation:
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
            "allocate_to_personal": to_personal,
            "allocate_to_village": to_village
        }
        allocation_response_str = json.dumps(mock_allocation)
    else:
        if not ollama_client:
            print("!!! CRITICAL ERROR: ollama_client not loaded for resource allocation call.")
            allocation_response_str = json.dumps({
                "allocation_thought": "Error: LLM client not available. Defaulting allocation.",
                "allocate_to_personal": 0, "allocate_to_village": amount_acquired
            })
        else:
            allocation_response_str = ollama_client.call_model(allocation_prompt, model_name="gemma:2b") 

    try:
        allocation_decision = json.loads(allocation_response_str)
        personal_gain = allocation_decision.get("allocate_to_personal", 0)
        village_gain = allocation_decision.get("allocate_to_village", 0)

        if not (isinstance(personal_gain, int) and isinstance(village_gain, int) and \
                personal_gain >= 0 and village_gain >= 0 and \
                (personal_gain + village_gain == amount_acquired)): 
            print(f"  Warning: Invalid allocation numbers by {agent_data['name']} for {resource_type} (p:{personal_gain}, v:{village_gain}, total:{amount_acquired}). Sum was {personal_gain + village_gain}. Defaulting to all personal.")
            add_to_memory(agent_data, f"Error in allocating {resource_type}. Kept all.")
            personal_gain = amount_acquired
            village_gain = 0
        
        if personal_gain > 0:
            agent_data["inventory"][resource_type] = agent_data["inventory"].get(resource_type, 0) + personal_gain
            narration += f" Kept {personal_gain} for themself."
            add_to_memory(agent_data, f"Allocated {personal_gain} {resource_type} to personal stash.")
        if village_gain > 0:
            village_resource_key = resource_type
            if resource_type == "food_rations": village_resource_key = "food"
            elif resource_type == "wood_scraps": village_resource_key = "wood"
            
            world_state["village_resources"][village_resource_key] = world_state["village_resources"].get(village_resource_key, 0) + village_gain
            narration += f" Contributed {village_gain} to the village."
            add_to_memory(agent_data, f"Contributed {village_gain} {resource_type} to village ({village_resource_key}).")
        
        if allocation_decision.get("allocation_thought"):
            add_to_memory(agent_data, f"Allocation thought: {allocation_decision['allocation_thought'][:100]}")

    except json.JSONDecodeError:
        narration += " But seemed unsure how to divide it, so they kept it all."
        agent_data["inventory"][resource_type] = agent_data["inventory"].get(resource_type, 0) + amount_acquired
        add_to_memory(agent_data, f"Error decoding allocation for {resource_type}. Kept all.")
    except Exception as e:
        narration += f" But an error occurred during allocation ({e}), so they kept it all."
        agent_data["inventory"][resource_type] = agent_data["inventory"].get(resource_type, 0) + amount_acquired
        add_to_memory(agent_data, f"Exception during allocation for {resource_type}. Kept all.")
        
    return narration

def process_agent_action(agent_data, action_json, world_state, use_mock_llm):
    thought = action_json.get("thought", "No specific thought recorded.")
    action_type = action_json.get("action_type")
    details = action_json.get("action_details", {})
    speech = action_json.get("speech", "")

    add_to_memory(agent_data, f"Considered: {thought[:100]}")
    if speech:
        print(f"  {agent_data['name']}: \"{speech}\"")
        add_to_memory(agent_data, f"Said: \"{speech}\"")

    agent_data["status"]["energy"] = max(0, agent_data["status"]["energy"] - random.randint(3, 7))
    agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + random.randint(1, 3))
    action_narration = ""

    if not isinstance(agent_data.get("inventory"), dict):
        agent_name = agent_data.get('name', agent_data.get('agent_id', 'Unknown Agent'))
        print(f"  CRITICAL WARNING (process_agent_action): Inventory for {agent_name} is not a dict. Attempting conversion.")
        agent_data["inventory"] = game_utils.convert_inventory_to_dict_format(agent_data.get("inventory", [])) # MODIFIED


    if action_type == "ADDRESS_NEED":
        need_id = details.get("need_id")
        skill_used = details.get("expected_contribution_skill", "their effort")
        activity_desc = details.get("activity_description", f"working on need {need_id}")
        target_need = next((n for n in world_state["active_needs"] if n["need_id"] == need_id), None)

        if target_need and (skill_used in agent_data.get("skills",{}) or skill_used == "their effort"):
            agent_data["current_focus_need_id"] = need_id
            if agent_data["agent_id"] not in target_need.get("assigned_agents", []): 
                 target_need.setdefault("assigned_agents", []).append(agent_data["agent_id"])

            skill_level = agent_data.get("skills",{}).get(skill_used, 0)
            if perform_skill_check(skill_level, difficulty=3):
                action_narration = f"{agent_data['name']} focused on {activity_desc}."
                
                if skill_used in ["hunting", "gathering"] and \
                   target_need.get("related_skills") and \
                   target_need.get("related_skills")[0] in ["hunting", "gathering"]:
                    amount_acquired = random.randint(skill_level + 1, (skill_level + 1) * 2) 
                    resource_key = "food_rations" 
                    
                    allocation_narration = handle_resource_acquisition_and_allocation(
                        agent_data, world_state, resource_key, amount_acquired, use_mock_llm
                    )
                    action_narration += " " + allocation_narration
                    target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.05 * amount_acquired)) 

                elif skill_used in ["building", "crafting"]:
                    can_proceed = True
                    if "required_materials" in target_need:
                        for material, amount_needed in target_need["required_materials"].items():
                            if world_state["village_resources"].get(material, 0) < 1 : 
                                can_proceed = False
                                action_narration += f" Tried {activity_desc}, but the village lacked {material}."
                                break
                        if can_proceed and "required_materials" in target_need: 
                             for material, amount_needed in target_need["required_materials"].items():
                                 if world_state["village_resources"].get(material, 0) > 0:
                                     world_state["village_resources"][material] -=1 
                    if can_proceed:
                        target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.05 * (skill_level+1)))
                        action_narration += f" Made good progress on {activity_desc}."
                else: 
                    target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.02 * (skill_level+1)))
                    action_narration += f" Contributed to {activity_desc} using {skill_used}."
                add_to_memory(agent_data, f"Successfully contributed to {need_id} via {activity_desc}.")
            else:
                action_narration = f"{agent_data['name']} attempted {activity_desc}, but struggled."
                add_to_memory(agent_data, f"Tried {activity_desc} for {need_id} but faced difficulties.")
        else:
            action_narration = f"{agent_data['name']} seemed confused about {activity_desc}."
            add_to_memory(agent_data, f"Tried to address invalid need or lacked skill for {activity_desc}.")

    elif action_type == "PERSONAL_ACTION":
        activity = details.get("activity", "something personal")
        if activity == "rest":
            energy_gained = random.randint(15, 30)
            agent_data["status"]["energy"] = min(100, agent_data["status"]["energy"] + energy_gained)
            action_narration = f"{agent_data['name']} took a moment to rest, regaining some energy."
            add_to_memory(agent_data, f"Rested, energy now {agent_data['status']['energy']}.")

        elif activity == "eat_personal":
            item_to_eat = details.get("item_to_eat", "food_rations")
            quantity_to_eat = details.get("quantity_to_eat", 1)
            
            if agent_data["inventory"].get(item_to_eat, 0) >= quantity_to_eat:
                agent_data["inventory"][item_to_eat] -= quantity_to_eat
                if agent_data["inventory"][item_to_eat] <= 0:
                    del agent_data["inventory"][item_to_eat] 

                hunger_reduced = random.randint(20, 30) * quantity_to_eat 
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - hunger_reduced)
                action_narration = f"{agent_data['name']} ate {quantity_to_eat} {item_to_eat.replace('_',' ')} from their personal stash."
                add_to_memory(agent_data, f"Ate {quantity_to_eat} {item_to_eat} personally. Hunger: {agent_data['status']['hunger']}.")
            else:
                action_narration = f"{agent_data['name']} wanted to eat {item_to_eat.replace('_',' ')}, but had none in their stash."
                add_to_memory(agent_data, f"Tried to eat {item_to_eat} but had none.")
        
        elif activity == "gather_personal":
            action_narration = f"{agent_data['name']} went to forage for themself."
            if perform_skill_check(agent_data.get("skills",{}).get("gathering",0), difficulty=2):
                amount_acquired = random.randint(1, agent_data.get("skills",{}).get("gathering",0) + 1)
                resource_key = "food_rations" 
                
                allocation_narration = handle_resource_acquisition_and_allocation(
                    agent_data, world_state, resource_key, amount_acquired, use_mock_llm
                )
                action_narration += " " + allocation_narration
            else:
                action_narration += " But returned empty-handed."
                add_to_memory(agent_data, "Failed personal gathering.")
        
        elif activity == "error_idle":
            action_narration = f"{agent_data['name']} {random.choice(['seems confused.', 'looks bewildered.', 'pauses, lost in thought.'])}"
        else:
            action_narration = f"{agent_data['name']} decided to {activity.replace('_',' ')}."
            add_to_memory(agent_data, f"Did: {activity}.")

    elif action_type == "SOCIAL_ACTION":
        sub_type = details.get("sub_type", "interact")
        target_desc = details.get("target_description", "someone")
        if sub_type == "propose_need":
            new_need_desc = details.get("need_description", "a new task")
            action_narration = f"{agent_data['name']} spoke up, proposing a new task for the village: '{new_need_desc}'."
            if len(world_state["active_needs"]) < 10:
                new_need_id = f"N_User_{random.randint(1000,9999)}"
                world_state["active_needs"].append({
                    "need_id": new_need_id, "description": f"(Proposed by {agent_data['name']}) {new_need_desc}",
                    "urgency": "medium", "related_skills": details.get("related_skills", ["general"]), "progress": 0.0, "assigned_agents": [agent_data["agent_id"]]
                })
                world_state["events_log"].append(f"{agent_data['name']} proposed: '{new_need_desc}'")
            else:
                action_narration += " However, the village already has many tasks at hand."
        else:
            action_narration = f"{agent_data['name']} chose to {sub_type.replace('_',' ')} with {target_desc}."
        add_to_memory(agent_data, f"Social: {sub_type} with {target_desc}.")
    else:
        action_narration = f"{agent_data['name']} {random.choice(['ponders.', 'looks around.', 'takes a moment.'])}"
        if action_type: add_to_memory(agent_data, f"Took an unrecognized action: {action_type}")

    if action_narration:
        print(f"  -> {action_narration}")
    
    for status_key in ["health", "hunger", "energy"]: 
        agent_data["status"][status_key] = max(0, min(100, agent_data["status"][status_key]))

def daily_world_update(world_state, all_agents_data_list):
    print("\n--- Dusk Settles: End of Day ---")
    world_state["day"] += 1
    weather_options = ["Mild", "Sunny", "Rainy", "Cold", "Windy", "Overcast"]
    old_weather = world_state["weather"]
    world_state["weather"] = random.choice(weather_options)
    if old_weather != world_state["weather"]:
        print(f"The weather shifts from {old_weather} to {world_state['weather']}.")
        world_state["events_log"].append(f"The weather changed to {world_state['weather']}.")

    if world_state["village_resources"]["food"] < len(all_agents_data_list) * 2 and not any("low on food" in n["description"].lower() for n in world_state["active_needs"]):
        new_need_id = f"N_Sys_{random.randint(100,999)}"
        desc = "Food reserves are critically low. More must be found urgently!"
        world_state["active_needs"].append({
            "need_id": new_need_id, "description": desc,
            "urgency": "critical", "related_skills": ["hunting", "gathering"], "progress": 0.0, "assigned_agents": []
        })
        print("CRITICAL Concern: Village food supplies are dangerously low.")
        world_state["events_log"].append("Critical concern as food supplies run dangerously low.")
    
    completed_needs_today = 0
    initial_need_count = len(world_state["active_needs"])
    world_state["active_needs"] = [n for n in world_state["active_needs"] if n.get("progress", 0.0) < 1.0]
    completed_needs_today = initial_need_count - len(world_state["active_needs"])
    if completed_needs_today > 0:
        print(f"{completed_needs_today} village task(s) were completed today!")
        world_state["events_log"].append(f"{completed_needs_today} task(s) completed.")

    print("\nVillage Sustenance & Status Check:")
    for agent_data in all_agents_data_list:
        if agent_data["status"]["health"] <= 0: continue
        
        if agent_data["status"]["hunger"] > 60: 
            food_to_eat_communally = 1 
            if world_state["village_resources"]["food"] >= food_to_eat_communally:
                world_state["village_resources"]["food"] -= food_to_eat_communally
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - random.randint(15, 25))
                add_to_memory(agent_data, f"Ate a small portion from village stockpile. Hunger: {agent_data['status']['hunger']}.")
                print(f"  {agent_data['name']} supplements their meal from the village stores.")
            else: 
                agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + random.randint(5,10))
                add_to_memory(agent_data, "Village stockpile empty, couldn't supplement meal.")
                if agent_data["status"]["hunger"] > 80: 
                    agent_data["status"]["health"] = max(0, agent_data["status"]["health"] - random.randint(5,10))
                    add_to_memory(agent_data, f"Starvation worsening. Health: {agent_data['status']['health']}.")
                    world_state["events_log"].append(f"{agent_data['name']} is severely weakened by hunger.")
                    print(f"  {agent_data['name']} is visibly suffering from lack of food...")
        
        if world_state["weather"] == "Cold" and agent_data["status"]["energy"] < 25: 
            agent_data["status"]["health"] = max(0, agent_data["status"]["health"] - random.randint(1,5)) 
            add_to_memory(agent_data, f"Felt the biting cold due to exhaustion. Health: {agent_data['status']['health']}.")
            if agent_data["status"]["health"] > 0:
                print(f"  The harsh cold saps more of {agent_data['name']}'s dwindling strength.")

        if agent_data["status"]["health"] <= 0:
            world_state["events_log"].append(f"TRAGEDY: {agent_data['name']} has succumbed to hardship.")
            print(f"  TRAGEDY STRIKES! {agent_data['name']} ({agent_data['agent_id']}) has perished!")
        
        save_agent(agent_data) 

def run_simulation_for_one_day(world_state, all_agents_data, use_mock_llm=True, ollama_model_name="gemma:2b"):
    global ollama_client 

    if not world_state: 
        print("SIM_ENGINE ERROR: World state not provided for day simulation.")
        return
    if not all_agents_data:
        print("SIM_ENGINE ERROR: Agent data not provided for day simulation.")
        return

    print(f"\n\n{'='*15} DAWN OF DAY {world_state['day']} ({world_state['season']}, Weather: {world_state['weather']}) {'='*15}")
    print(f"Village Resources: Food={world_state['village_resources']['food']}, Wood={world_state['village_resources']['wood']}, Stone={world_state['village_resources']['stone']}, Herbs={world_state['village_resources']['herbs']}")
    
    if world_state['active_needs']:
        print("Current Village Needs:")
        for i, need in enumerate(world_state['active_needs']):
            progress_percent = need.get('progress', 0.0) * 100
            assigned_str = f"({len(need.get('assigned_agents',[]))} assigned)" if need.get('assigned_agents') else ""
            print(f"  - {need['description'][:60]}... (Urgency: {need['urgency']}, {progress_percent:.0f}% done {assigned_str})")
    else:
        print("The village has no pressing communal tasks at the moment.")
    print("-" * 50)
    
    current_day_agents_list = []
    for agent_id, agent_data_dict in all_agents_data.items(): 
        if agent_data_dict["status"]["health"] > 0:
            if not isinstance(agent_data_dict.get("inventory"), dict):
                 agent_name = agent_data_dict.get('name', agent_id)
                 print(f"  CRITICAL WARNING (run_simulation): Inventory for {agent_name} is still not a dict! Converting.")
                 agent_data_dict["inventory"] = game_utils.convert_inventory_to_dict_format(agent_data_dict.get("inventory", [])) # MODIFIED
            current_day_agents_list.append(agent_data_dict)

    if not current_day_agents_list:
        print("\n\n" + "*"*20 + " THE VILLAGE IS LOST " + "*"*20)
        if world_state: 
            world_state["events_log"].append("The last survivor has fallen. The village is lost.")
        return 

    random.shuffle(current_day_agents_list)

    for agent_data_turn in current_day_agents_list: 
        print(f"\n--- {agent_data_turn['name']}'s Turn ({agent_data_turn['agent_id']}) ---")
        print(f"    Status: {get_status_description(agent_data_turn)}")
        # MODIFIED to use game_utils.convert_inventory_to_dict_format if inventory is not dict
        # However, prompter.format_inventory_for_prompt expects a dict already.
        # The conversion should ideally happen before this point if it was list.
        # Assuming inventory is now correctly a dict due to earlier conversion:
        print(f"    Personal Inventory: {prompter.format_inventory_for_prompt(agent_data_turn.get('inventory',{}), agent_data_turn.get('personal_resources',{}))}")


        if agent_data_turn["current_focus_need_id"]:
            focused_need_exists = any(n["need_id"] == agent_data_turn["current_focus_need_id"] for n in world_state["active_needs"])
            if not focused_need_exists:
                add_to_memory(agent_data_turn, f"My task {agent_data_turn['current_focus_need_id']} is complete or gone.")
                agent_data_turn["current_focus_need_id"] = None
        
        prompt_text = prompter.generate_agent_prompt(agent_data_turn, world_state)
        llm_response_str = None

        if use_mock_llm:
            time.sleep(0.05) 
            mock_actions = []
            if agent_data_turn["status"]["hunger"] > 60 and agent_data_turn["inventory"].get("food_rations", 0) > 0:
                mock_actions.append({
                    "thought": "Mock: Very hungry, must eat my own food.",
                    "action_type": "PERSONAL_ACTION",
                    "action_details": {"activity": "eat_personal", "item_to_eat": "food_rations", "quantity_to_eat": 1},
                    "speech": "Need to eat something now."
                })
            elif world_state["active_needs"] and agent_data_turn["status"]["energy"] > 30 and random.random() < 0.7: 
                need_to_address = random.choice(world_state["active_needs"])
                relevant_skills = [s for s in agent_data_turn.get("skills",{}) if s in need_to_address.get("related_skills", []) and agent_data_turn.get("skills",{}).get(s,0) > 0]
                chosen_skill = random.choice(relevant_skills) if relevant_skills else "their effort"
                mock_actions.append({
                    "thought": f"Mock: Village needs {need_to_address['description'][:20]}. I'll use {chosen_skill}.",
                    "action_type": "ADDRESS_NEED",
                    "action_details": {"need_id": need_to_address['need_id'], "activity_description": f"work on {need_to_address['description'][:20]}", "expected_contribution_skill": chosen_skill},
                    "speech": random.choice(["I can help with that.", "On it!"])
                })
            elif agent_data_turn.get("skills",{}).get("gathering",0) > 0 and agent_data_turn["status"]["energy"] > 40 and random.random() < 0.4:
                 mock_actions.append({
                    "thought": "Mock: I'll try to gather some food for myself, just in case.",
                    "action_type": "PERSONAL_ACTION",
                    "action_details": {"activity": "gather_personal"},
                    "speech": "Going to forage for a bit."
                })
            
            if not mock_actions or agent_data_turn["status"]["energy"] < 25 : 
                mock_actions.append({"thought": "Mock: I'm tired and need to rest.", "action_type": "PERSONAL_ACTION", "action_details": {"activity": "rest"}, "speech": "Taking a break."})
            
            llm_response_str = json.dumps(random.choice(mock_actions))
        else: 
            if not ollama_client:
                print("!!! CRITICAL ERROR: ollama_client not available for real LLM call.")
                llm_response_str = json.dumps({"thought": "Error: LLM client missing. Resting by default.", "action_type": "PERSONAL_ACTION", "action_details": {"activity": "rest"}, "speech": ""})
            else:
                llm_response_str = ollama_client.call_model(prompt_text, model_name=ollama_model_name)

        if llm_response_str:
            try:
                action_json = json.loads(llm_response_str)
                process_agent_action(agent_data_turn, action_json, world_state, use_mock_llm) 
            except json.JSONDecodeError:
                print(f"  -> {agent_data_turn['name']} seems to mumble incoherently (LLM response was not valid JSON). Response: {llm_response_str[:100]}")
                add_to_memory(agent_data_turn, "SYSTEM_ERROR: My thoughts were jumbled.")
            except Exception as e:
                print(f"  -> An unforeseen event confuses {agent_data_turn['name']} (Error processing action: {e}).")
                add_to_memory(agent_data_turn, f"SYSTEM_ERROR: {str(e)[:50]}")
        else:
            print(f"  -> {agent_data_turn['name']} seems lost in thought, unsure what to do (No LLM response).")
            add_to_memory(agent_data_turn, "SYSTEM_ERROR: Unable to decide on an action.")
        time.sleep(0.1) 

    daily_world_update(world_state, current_day_agents_list) 


if __name__ == "__main__":
    ollama_client = None 
    
    SIM_DAYS_TO_RUN_STANDALONE = 3 
    USE_MOCK_LLM_STANDALONE = True 
    OLLAMA_MODEL_STANDALONE = "gemma:2b" 

    print("Initializing the Village Chronicle (sim_engine.py direct run)...")
    if USE_MOCK_LLM_STANDALONE:
        print(">>> Using MOCK LLM responses for this simulation. <<<")
    else:
        print(">>> Attempting to use REAL Ollama LLM responses. Make sure Ollama is running! <<<")
        try:
            import ollama_client as oc_module 
            ollama_client = oc_module 
            print(f"Successfully imported ollama_client. Target model: {OLLAMA_MODEL_STANDALONE}")
        except ImportError:
            print("FATAL ERROR: Could not import ollama_client.py. Ensure it exists and has no errors.")
            print("         The simulation will run with MOCK responses instead.")
            USE_MOCK_LLM_STANDALONE = True 
    
    current_world_data = load_world()
    if not current_world_data:
        print(f"No {WORLD_STATE_FILE} found. Please run generate_simulation_files.py first.")
        exit()

    all_agents_master_dict = {}
    agent_files_in_dir = [f for f in os.listdir(AGENT_DATA_PATH) if f.startswith("agent_") and f.endswith(".json")]
    if not agent_files_in_dir:
        print(f"No agent files found in {AGENT_DATA_PATH}. Please run generate_simulation_files.py first.")
        exit()

    print("Loading and migrating agent data for standalone run...")
    for agent_file_name in agent_files_in_dir:
        loaded_agent_data = load_agent(agent_file_name) 
        if loaded_agent_data:
            if not isinstance(loaded_agent_data.get("inventory"), dict): 
                agent_name_log = loaded_agent_data.get('name', agent_file_name)
                print(f"  Migrating inventory for {agent_name_log} (from file {agent_file_name}) from list to dict...")
                loaded_agent_data["inventory"] = game_utils.convert_inventory_to_dict_format(loaded_agent_data.get("inventory", [])) # MODIFIED
                save_agent(loaded_agent_data) 
            elif loaded_agent_data.get("inventory") is None: 
                loaded_agent_data["inventory"] = {}

            all_agents_master_dict[loaded_agent_data['agent_id']] = loaded_agent_data
    
    for day_count in range(SIM_DAYS_TO_RUN_STANDALONE):
        if not any(agent_data["status"]["health"] > 0 for agent_id, agent_data in all_agents_master_dict.items()):
            print("Village has perished. Ending standalone simulation.")
            break
        
        run_simulation_for_one_day(
            world_state=current_world_data, 
            all_agents_data=all_agents_master_dict,
            use_mock_llm=USE_MOCK_LLM_STANDALONE,
            ollama_model_name=OLLAMA_MODEL_STANDALONE
        )
        
        save_world(current_world_data) 
        print(f"--- End of Day {current_world_data['day']-1} processing for standalone run. State saved. ---") 

    print("\n--- Standalone Simulation Run Complete ---")
    if current_world_data: 
        print("Final Village Resources:")
        print(f"  Food: {current_world_data['village_resources']['food']}, Wood: {current_world_data['village_resources']['wood']}, Stone: {current_world_data['village_resources']['stone']}, Herbs: {current_world_data['village_resources']['herbs']}")
        print("\nRecent Events Log (Last 10 entries):")
        for entry in current_world_data.get("events_log", [])[-10:]:
            print(f"- {entry}")
    else:
        print("Simulation ended, but world data is unavailable.")