# action_handler.py
# Handles the execution of specific actions chosen by agents.

import json 
import random
import config # Now includes CRAFTABLE_ITEMS with detailed properties
import game_utils

def add_memory_log(agent_data, entry):
    """Helper to add to agent's memory log, ensuring it exists."""
    agent_data.setdefault("memory_log", []).append(entry)
    if len(agent_data["memory_log"]) > config.MAX_MEMORY_LOG:
        agent_data["memory_log"] = agent_data["memory_log"][-config.MAX_MEMORY_LOG:]

def _get_equipped_item_effects(agent_data, action_type=None, target_resource=None):
    """
    Checks agent's inventory for equipped items and returns a list of relevant effects.
    For now, assumes an item in inventory is "equipped" if relevant.
    A proper equip system would be agent_data["equipped_slots"].
    """
    applicable_effects = []
    if not isinstance(agent_data.get("inventory"), dict):
        return applicable_effects # Should not happen if inventory is managed well

    for item_id, quantity in agent_data["inventory"].items():
        if quantity > 0 and item_id in config.CRAFTABLE_ITEMS:
            item_def = config.CRAFTABLE_ITEMS[item_id]
            item_properties = item_def.get("properties", {})
            
            # Crude check for "equipped" - if they have it, they might use it.
            # A real system would check agent_data["equipped_slots"].
            # For now, we'll assume if an item *can* be equipped for an action, it is.
            
            for effect in item_properties.get("effects", []):
                # Basic condition check - for now, 'equipped' is a general catch-all
                # More specific conditions like 'equipped_hand_main' would need an equip system.
                is_relevant = False
                condition = effect.get("condition", "equipped") # Default to "equipped"

                if condition == "equipped": # General check, refine if equip slots are added
                    if effect.get("type") == "gathering_yield" and effect.get("resource") == target_resource:
                        is_relevant = True
                    elif effect.get("type") == "action_energy_modifier" and effect.get("action") == action_type:
                        is_relevant = True
                    # Add other general "equipped" effects here if needed
                
                # Example for future equip system:
                # if condition == "equipped_hand_main" and agent_data.get("equipped_slots", {}).get("hand_main") == item_id:
                #     if effect.get("type") == "combat_damage": is_relevant = True
                
                # For now, if it's a tool and the action matches, or it's a weapon and action is combat:
                if item_properties.get("item_category") == "tool" and action_type and \
                   ( (item_properties.get("tool_type") == "axe" and action_type == "gather_wood") or \
                     (item_properties.get("tool_type") == "knife" and action_type == "gather_herbs") ): # Add more tool types
                     if effect.get("type") == "gathering_yield" and effect.get("resource") == target_resource:
                         is_relevant = True
                     elif effect.get("type") == "action_energy_modifier" and effect.get("action") == action_type:
                         is_relevant = True
                
                if item_properties.get("item_category") == "weapon" and action_type == "combat": # Placeholder for combat
                    if effect.get("type") == "combat_damage":
                        is_relevant = True

                if is_relevant:
                    applicable_effects.append(effect)
    return applicable_effects

def _decide_and_allocate_resources(agent_data, resource_type, amount_gained, world_data, all_agents_data, llm_caller, prompt_generator_func):
    """
    Handles the agent's decision on how to allocate newly gained resources.
    Updates personal and village inventories and returns a narration snippet.
    """
    add_memory_log(agent_data, f"Gained {amount_gained} {resource_type}. Deciding on allocation.")
    agent_data.setdefault("personal_resources", {res_type: 0 for res_type in config.INITIAL_VILLAGE_RESOURCES.keys()})

    allocation_decision_json = None
    if config.USE_MOCK_LLM: 
        keep_personal = 0
        contribute_village = 0
        if "greedy" in agent_data.get("personality_traits", []) or "selfish" in agent_data.get("personality_traits", []):
            keep_personal = random.randint(amount_gained // 2, amount_gained)
        elif "generous" in agent_data.get("personality_traits", []):
            keep_personal = random.randint(0, amount_gained // 3)
        else:
            keep_personal = random.randint(0, amount_gained // 2)
        
        keep_personal = min(amount_gained, max(0, keep_personal)) 
        contribute_village = amount_gained - keep_personal
        
        allocation_decision_json = {
            "thought": f"Mock decision: I gained {amount_gained} {resource_type}. I'll keep {keep_personal} and share {contribute_village}.",
            "allocation": {
                "personal_stash": keep_personal,
                "village_contribution": contribute_village
            }
        }
    else:
        if llm_caller and prompt_generator_func:
            # Pass world_data to the allocation prompt generator
            allocation_prompt = prompt_generator_func(agent_data, resource_type, amount_gained, world_data) 
            response_str = llm_caller(allocation_prompt, model_name=config.OLLAMA_DEFAULT_MODEL, temperature=config.OLLAMA_TEMPERATURE)
            try:
                parsed_llm_response = json.loads(response_str)
                if "response" in parsed_llm_response and isinstance(parsed_llm_response["response"], str):
                    allocation_decision_json = json.loads(parsed_llm_response["response"])
                else: # If the response is already the direct JSON
                    allocation_decision_json = parsed_llm_response
            except json.JSONDecodeError:
                add_memory_log(agent_data, f"Error decoding allocation decision for {resource_type}. Raw: {response_str[:100]}")
                allocation_decision_json = {"allocation": {"personal_stash": 0, "village_contribution": amount_gained}, "thought": "Fallback: Contributed all due to unclear thought."}
        else: 
            add_memory_log(agent_data, "SYSTEM ERROR: LLM components not available for allocation decision.")
            allocation_decision_json = {"allocation": {"personal_stash": 0, "village_contribution": amount_gained}, "thought": "Fallback: Contributed all due to system error."}

    allocation = allocation_decision_json.get("allocation", {})
    kept_personal = allocation.get("personal_stash", 0)
    contributed_village = allocation.get("village_contribution", 0)

    # Validate and correct allocation numbers
    try:
        kept_personal = int(kept_personal)
        contributed_village = int(contributed_village)
    except ValueError:
        add_memory_log(agent_data, f"Error: Non-integer allocation values from LLM for {resource_type}. Defaulting.")
        kept_personal = 0
        contributed_village = amount_gained

    if kept_personal < 0: kept_personal = 0
    if contributed_village < 0: contributed_village = 0
    
    if kept_personal + contributed_village != amount_gained:
        add_memory_log(agent_data, f"Warning: LLM allocation for {resource_type} (p:{kept_personal}, v:{contributed_village}) didn't sum to {amount_gained}. Prioritizing personal, adjusting village.")
        kept_personal = min(amount_gained, kept_personal) # Ensure personal doesn't exceed total
        actual_contributed = amount_gained - kept_personal
    else:
        actual_contributed = contributed_village
    
    agent_data["personal_resources"].setdefault(resource_type, 0)
    agent_data["personal_resources"][resource_type] += kept_personal
    
    world_data["village_resources"].setdefault(resource_type, 0)
    world_data["village_resources"][resource_type] += actual_contributed # Use corrected village contribution
    
    allocation_thought = allocation_decision_json.get("thought", "Decided on resource allocation.")
    add_memory_log(agent_data, f"Allocation thought: {allocation_thought[:100]}")
    add_memory_log(agent_data, f"Allocated {resource_type}: {kept_personal} to self, {actual_contributed} to village.")

    narration = ""
    if kept_personal > 0 and actual_contributed > 0:
        narration = f"decided to keep {kept_personal} {resource_type} and contribute {actual_contributed} to the village."
    elif kept_personal > 0:
        narration = f"kept all {kept_personal} {resource_type} for themself."
    elif actual_contributed > 0:
        narration = f"contributed all {actual_contributed} {resource_type} to the village stockpile."
    else:
        narration = f"gained {amount_gained} {resource_type} but didn't allocate any (or gained 0)."
    
    return narration


def execute_action(agent_data, action_json, world_data, all_agents_data, llm_caller, prompter_module):
    action_type = action_json.get("action_type")
    details = action_json.get("action_details", {})
    narration = f"{agent_data['name']} seems unsure what to do." 

    agent_data.setdefault("personal_resources", {res_type: 0 for res_type in config.INITIAL_VILLAGE_RESOURCES.keys()})
    if not isinstance(agent_data.get("inventory"), dict):
        agent_data["inventory"] = game_utils.convert_inventory_to_dict_format(agent_data.get("inventory", []))

    # Special handling for social actions - they cost minimal energy
    if action_type == "SOCIAL_ACTION":
        social_energy_cost = 1  # Minimal energy cost
        agent_data["status"]["energy"] = max(0, agent_data["status"]["energy"] - social_energy_cost)
        agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + 1)  # Minimal hunger increase
        
        social_narration = _handle_social_action(agent_data, details, world_data, all_agents_data, action_json)
        
        # For quick social actions (talking), allow another action
        if details.get("sub_type") in ["make_statement_to_agent", "talk_general"]:
            # Give back most of the energy that will be deducted by the main action
            agent_data["status"]["energy"] = min(100, agent_data["status"]["energy"] + (config.BASE_ENERGY_COST_PER_ACTION - social_energy_cost))
            
            # Ask LLM for another action
            next_action_prompt = prompter_module.generate_agent_prompt(agent_data, world_data)
            try:
                next_action_json = json.loads(llm_caller(next_action_prompt, model_name=config.OLLAMA_DEFAULT_MODEL, temperature=config.OLLAMA_TEMPERATURE))
                if next_action_json.get("action_type") != "SOCIAL_ACTION":  # Prevent infinite social chains
                    return f"{social_narration}\nThen, " + execute_action(agent_data, next_action_json, world_data, all_agents_data, llm_caller, prompter_module)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                add_memory_log(agent_data, f"Error getting next action after social: {str(e)[:100]}")
        
        return social_narration

    # Handle other action types normally with full energy/hunger costs
    current_action_energy_cost = config.BASE_ENERGY_COST_PER_ACTION
    current_action_hunger_increase = config.BASE_HUNGER_INCREASE_PER_ACTION
    current_action_time_cost = 1.0 # Default time cost

    # Apply item effects that modify action costs (e.g., energy for gathering wood with an axe)
    # This is a simplified pre-cost modification. More complex effects might apply during/after.
    if action_type == "ADDRESS_NEED" or (action_type == "PERSONAL_ACTION" and details.get("activity","").startswith("gather_")):
        action_activity_for_effects = details.get("activity", "") 
        if action_type == "ADDRESS_NEED": # Try to map need description to an action type for effects
            if "wood" in details.get("activity_description","").lower(): action_activity_for_effects = "gather_wood"
            elif "herb" in details.get("activity_description","").lower(): action_activity_for_effects = "gather_herbs"
            # Add more mappings as needed

        item_effects = _get_equipped_item_effects(agent_data, action_activity_for_effects)
        for effect in item_effects:
            if effect.get("type") == "action_energy_modifier" and effect.get("action") == action_activity_for_effects:
                current_action_energy_cost += effect.get("modifier", 0)
            # Add time cost modifiers here if defined in effects

    agent_data["status"]["energy"] = max(0, agent_data["status"]["energy"] - current_action_energy_cost)
    agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + current_action_hunger_increase)
    # world_data["time_elapsed_this_day"] += current_action_time_cost # If tracking intra-day time

    if action_type == "ADDRESS_NEED":
        narration = _handle_address_need(agent_data, details, world_data, all_agents_data, llm_caller, prompter_module.generate_resource_allocation_prompt)
    elif action_type == "PERSONAL_ACTION":
        narration = _handle_personal_action(agent_data, details, world_data, all_agents_data, llm_caller, prompter_module.generate_resource_allocation_prompt)
    elif action_type == "SOCIAL_ACTION":
        narration = _handle_social_action(agent_data, details, world_data, all_agents_data, action_json)
    else:
        narration = f"{agent_data['name']} performs an unrecognized action: '{action_type}'. They look puzzled."
        add_memory_log(agent_data, f"Attempted unknown action: {action_type}")

    for status_key in ["health", "hunger", "energy"]:
        agent_data["status"][status_key] = max(0, min(100, agent_data["status"][status_key]))
    
    return narration


def _handle_address_need(agent_data, details, world_data, all_agents_data, llm_caller, prompt_generator_allocation_func):
    need_id = details.get("need_id")
    skill_used_by_llm = details.get("expected_contribution_skill", "general_effort")
    activity_desc = details.get("activity_description", f"working on task {need_id}")
    
    target_need = next((n for n in world_data["active_needs"] if n["need_id"] == need_id), None)

    if not target_need:
        return f"{agent_data['name']} tried to work on task '{need_id}', but it no longer exists or is invalid."

    add_memory_log(agent_data, f"Focused on task: {activity_desc} (Need ID: {need_id})")
    agent_data["current_focus_need_id"] = need_id 
    if agent_data["agent_id"] not in target_need.get("assigned_agents", []):
        target_need.setdefault("assigned_agents", []).append(agent_data["agent_id"])

    # Determine actual skill to use based on need's related_skills
    actual_skill_to_use = skill_used_by_llm # Default to LLM's choice
    if target_need.get("related_skills"):
        # If LLM's skill is valid for the need, use it. Otherwise, pick the agent's best valid skill.
        if skill_used_by_llm not in target_need["related_skills"]:
            best_skill_val = -1
            for skill_option in target_need["related_skills"]:
                if agent_data["skills"].get(skill_option, 0) > best_skill_val:
                    best_skill_val = agent_data["skills"].get(skill_option, 0)
                    actual_skill_to_use = skill_option
            if best_skill_val == -1 : actual_skill_to_use = "general_effort" # Fallback if no matching skills
    
    skill_level = agent_data["skills"].get(actual_skill_to_use, 0) if actual_skill_to_use != "general_effort" else 0
    task_difficulty = target_need.get("difficulty", 3) 

    # --- SPECIFIC LOGIC FOR GATHERING WOOD FOR A NEED ---
    # This logic should be more generic, checking if the need is about gathering a resource affected by tools.
    # Let's assume activity_desc or related_skills indicates the resource.
    resource_gathered_for_need = None
    action_type_for_effects = "unknown_action" # For _get_equipped_item_effects

    if "wood" in activity_desc.lower() or (target_need.get("related_skills") and "woodcutting" in target_need["related_skills"]):
        resource_gathered_for_need = "wood"
        action_type_for_effects = "gather_wood"
    elif "herb" in activity_desc.lower() or (target_need.get("related_skills") and "herbalism" in target_need["related_skills"]): # Assuming a skill
        resource_gathered_for_need = "herbs" # or "healing_herbs"
        action_type_for_effects = "gather_herbs"
    # Add more mappings for other resources (stone, food types etc.)

    if resource_gathered_for_need:
        base_yield = random.randint(1, 2) + skill_level // 2 # Basic yield before tool effects
        
        # Apply tool effects
        tool_effects = _get_equipped_item_effects(agent_data, action_type_for_effects, resource_gathered_for_need)
        yield_bonus_flat = 0
        for effect in tool_effects:
            if effect.get("type") == "gathering_yield" and effect.get("resource") == resource_gathered_for_need:
                yield_bonus_flat += effect.get("bonus_flat", 0)
        
        base_yield += yield_bonus_flat
        if yield_bonus_flat > 0:
            add_memory_log(agent_data, f"Used a tool, improving {resource_gathered_for_need} gathering.")
            activity_desc += " (using a tool)"
        else:
             add_memory_log(agent_data, f"Gathered {resource_gathered_for_need} with basic means.")


        if game_utils.perform_skill_check(skill_level, difficulty=task_difficulty):
            amount_gained = max(1, base_yield) 
            
            allocation_narration = _decide_and_allocate_resources(agent_data, resource_gathered_for_need, amount_gained, world_data, all_agents_data, llm_caller, prompt_generator_allocation_func)
            main_narration = f"{agent_data['name']} diligently {activity_desc}, acquiring {amount_gained} {resource_gathered_for_need}. They {allocation_narration}"
            
            target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.02 * amount_gained * (skill_level + 1))) # Progress based on amount and skill
            return f"{main_narration} (Task progress: {target_need['progress']:.0%})"
        else:
            return f"{agent_data['name']} attempted to {activity_desc} but failed to gather any significant {resource_gathered_for_need}."
    # --- END OF GENERIC RESOURCE GATHERING FOR NEED ---

    # General skill check for other non-gathering needs (e.g., building, crafting for need)
    if game_utils.perform_skill_check(skill_level, difficulty=task_difficulty):
        contribution_amount = random.randint(1, skill_level + 2) 
        
        if actual_skill_to_use in ["building", "crafting"] and any(s in target_need.get("related_skills", []) for s in ["building", "crafting"]):
            mats_ok = True
            materials_consumed_this_turn = {}
            if "required_materials" in target_need:
                for mat, req_amount_per_tick in target_need["required_materials"].items(): # Assuming req_amount is per contribution tick
                    if world_data["village_resources"].get(mat, 0) < req_amount_per_tick:
                        mats_ok = False
                        return f"{agent_data['name']} attempted to {activity_desc}, but the village lacks enough {mat} ({req_amount_per_tick} needed for this step)."
                    else:
                        materials_consumed_this_turn[mat] = materials_consumed_this_turn.get(mat, 0) + req_amount_per_tick
            
            if mats_ok: 
                for mat, consumed_amount in materials_consumed_this_turn.items():
                     world_data["village_resources"][mat] = max(0, world_data["village_resources"][mat] - consumed_amount)
                target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.05 * contribution_amount * (skill_level + 1)))
                return f"{agent_data['name']} skillfully {activity_desc}. The task is now {target_need['progress']:.0%} complete."
        else: 
            target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.03 * contribution_amount))
            return f"{agent_data['name']} contributed to {activity_desc}. (Task progress: {target_need['progress']:.0%})"
    else:
        return f"{agent_data['name']} attempted to {activity_desc} using {actual_skill_to_use}, but made little headway."


def _handle_personal_action(agent_data, details, world_data, all_agents_data, llm_caller, prompt_generator_allocation_func):
    activity = details.get("activity", "act personally")
    time_cost = 1.0 # Default, can be overridden by specific activities or item defs
    
    if activity == "rest":
        energy_gained = config.REST_ENERGY_GAIN + random.randint(-5, 5)
        agent_data["status"]["energy"] = min(100, agent_data["status"]["energy"] + energy_gained)
        # world_data["time_elapsed_this_day"] += 0.5 # Resting might take less 'active' time
        return f"{agent_data['name']} took a moment to rest, regaining {energy_gained} energy. (Energy: {agent_data['status']['energy']})"
    
    elif activity == "eat_from_inventory":
        item_to_eat_id = details.get("consume_item", "food_rations") 
        amount_to_eat = details.get("amount", 1)
        
        if agent_data["inventory"].get(item_to_eat_id, 0) >= amount_to_eat:
            item_def = config.CRAFTABLE_ITEMS.get(item_to_eat_id) # Check if it's a defined consumable
            hunger_reduced = 0
            health_gained = 0

            if item_def and item_def["properties"]["item_category"] == "consumable":
                for effect in item_def["properties"].get("effects", []):
                    if effect.get("type") == "stat_change_on_consume":
                        if effect.get("stat") == "hunger":
                            hunger_reduced += effect.get("change", 0) # Change is usually negative for hunger
                        elif effect.get("stat") == "health":
                            health_gained += effect.get("change", 0)
                
                agent_data["inventory"][item_to_eat_id] -= amount_to_eat
                if agent_data["inventory"][item_to_eat_id] <= 0:
                    del agent_data["inventory"][item_to_eat_id]

                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] + hunger_reduced) # hunger_reduced is negative
                agent_data["status"]["health"] = min(100, agent_data["status"]["health"] + health_gained)
                narration = f"{agent_data['name']} consumed {amount_to_eat} {item_def['name']}."
                if hunger_reduced != 0: narration += f" Hunger now {agent_data['status']['hunger']}."
                if health_gained != 0: narration += f" Health now {agent_data['status']['health']}."
                return narration
            else: # Generic, non-defined food item (like old "food_rations" if not in CRAFTABLE_ITEMS)
                agent_data["inventory"][item_to_eat_id] -= amount_to_eat
                if agent_data["inventory"][item_to_eat_id] <= 0: del agent_data["inventory"][item_to_eat_id]
                hunger_reduced_generic = random.randint(15, 30) * amount_to_eat
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - hunger_reduced_generic)
                return f"{agent_data['name']} ate {amount_to_eat} {item_to_eat_id.replace('_',' ')}. (Hunger: {agent_data['status']['hunger']})"
        else: # Check personal_resources for raw food
            if item_to_eat_id in agent_data.get("personal_resources", {}) and agent_data["personal_resources"].get(item_to_eat_id,0) >= amount_to_eat:
                agent_data["personal_resources"][item_to_eat_id] -= amount_to_eat
                hunger_reduced_raw = random.randint(5, 15) * amount_to_eat 
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - hunger_reduced_raw)
                return f"{agent_data['name']} ate {amount_to_eat} raw {item_to_eat_id.replace('_',' ')}. (Hunger: {agent_data['status']['hunger']})"
            else:
                return f"{agent_data['name']} wanted to eat {amount_to_eat} {item_to_eat_id.replace('_',' ')} but didn't have enough."

    elif activity == "gather_resource": 
        resource_to_gather = details.get("resource_id", None)
        if not resource_to_gather or resource_to_gather not in config.GATHERABLE_PERSONAL_RESOURCES:
            return f"{agent_data['name']} tried to gather an unknown resource: '{resource_to_gather or 'unspecified'}'. They look confused."

        gather_info = config.GATHERABLE_PERSONAL_RESOURCES[resource_to_gather]
        skill_to_use = gather_info["skill"]
        skill_level = agent_data["skills"].get(skill_to_use, 0)
        difficulty = gather_info["base_difficulty"]
        time_cost = gather_info.get("time_cost", 1.0)
        # world_data["time_elapsed_this_day"] += time_cost # Apply specific time cost

        # Apply tool effects for personal gathering
        tool_effects = _get_equipped_item_effects(agent_data, f"gather_{resource_to_gather}", resource_to_gather) # e.g. gather_sturdy_branch
        yield_bonus_flat_personal = 0
        for effect in tool_effects:
            if effect.get("type") == "gathering_yield" and effect.get("resource") == resource_to_gather:
                 yield_bonus_flat_personal += effect.get("bonus_flat", 0)
        if yield_bonus_flat_personal > 0: add_memory_log(agent_data, f"Used a tool for personal gathering of {resource_to_gather}.")


        if game_utils.perform_skill_check(skill_level, difficulty=difficulty):
            base_yield_range = gather_info["base_yield"]
            amount_gained = random.randint(base_yield_range[0], base_yield_range[1]) + (skill_level // 2) + yield_bonus_flat_personal
            amount_gained = max(0, amount_gained) # Ensure non-negative if base yield can be 0

            if amount_gained > 0:
                agent_data["personal_resources"].setdefault(resource_to_gather, 0)
                agent_data["personal_resources"][resource_to_gather] += amount_gained
                add_memory_log(agent_data, f"Personally gathered {amount_gained} {resource_to_gather.replace('_',' ')}.")
                return f"{agent_data['name']} foraged and found {amount_gained} {resource_to_gather.replace('_',' ')}, adding it to their personal supply."
            else:
                return f"{agent_data['name']} searched for {resource_to_gather.replace('_',' ')} but found none this time."
        else:
            return f"{agent_data['name']} tried foraging for {resource_to_gather.replace('_',' ')} but failed to find any."

    elif activity == "craft_item":
        item_id_to_craft = details.get("item_id", None)
        if not item_id_to_craft or item_id_to_craft not in config.CRAFTABLE_ITEMS:
            return f"{agent_data['name']} tried to craft an unknown item: '{item_id_to_craft or 'unspecified'}'. They look confused."

        item_def = config.CRAFTABLE_ITEMS[item_id_to_craft]
        recipe = item_def["recipe"]
        skill_req_name = item_def["skill_required"]
        min_skill = item_def["min_skill_level"]
        agent_skill_level = agent_data["skills"].get(skill_req_name, 0)
        crafting_energy_cost = item_def.get("energy_cost", config.BASE_ENERGY_COST_PER_ACTION) # Specific energy cost for crafting
        # time_cost = item_def.get("time_cost", 1.0) # Specific time cost for crafting
        # world_data["time_elapsed_this_day"] += time_cost 
        # Agent energy already reduced by base, so adjust if specific cost is different
        agent_data["status"]["energy"] -= (crafting_energy_cost - config.BASE_ENERGY_COST_PER_ACTION)


        if agent_skill_level < min_skill:
            return f"{agent_data['name']} lacks the required {skill_req_name} skill (needs {min_skill}, has {agent_skill_level}) to craft a {item_def['name']}."

        has_materials = True
        missing_mats_str = []
        for material, count_needed in recipe.items():
            if agent_data["personal_resources"].get(material, 0) < count_needed:
                has_materials = False
                missing_mats_str.append(f"{count_needed} {material.replace('_',' ')}")
        
        if not has_materials:
            return f"{agent_data['name']} wanted to craft a {item_def['name']} but lacked: {', '.join(missing_mats_str)}."

        crafting_difficulty = item_def.get("difficulty", 3) 
        if game_utils.perform_skill_check(agent_skill_level, difficulty=crafting_difficulty):
            for material, count_needed in recipe.items():
                agent_data["personal_resources"][material] -= count_needed
            
            items_yielded = item_def.get("yield", 1)
            agent_data["inventory"].setdefault(item_id_to_craft, 0)
            agent_data["inventory"][item_id_to_craft] += items_yielded
            
            add_memory_log(agent_data, f"Successfully crafted {items_yielded}x {item_def['name']}.")
            return f"{agent_data['name']} successfully crafted {items_yielded}x {item_def['name']} ({item_id_to_craft})!"
        else:
            add_memory_log(agent_data, f"Fumbled while trying to craft a {item_def['name']}.")
            # Decide if materials are consumed on failure (e.g., 50% chance to lose some)
            # For now, no material loss on failed craft to be less punishing.
            return f"{agent_data['name']} fumbled while trying to craft a {item_def['name']}."
            
    elif activity == "error_idle": 
        return f"{agent_data['name']} {random.choice(['seems dazed.', 'is momentarily confused.', 'stares blankly for a moment.'])}"

    return f"{agent_data['name']} decided to {activity.replace('_',' ')} for their own reasons." # Fallback


def _handle_social_action(agent_data, details, world_data, all_agents_data, full_action_json):
    sub_type = details.get("sub_type", "interact")
    target_agent_id = details.get("target_agent_id") 
    target_description = details.get("target_description", "another villager") 
    
    target_agent = None
    if target_agent_id and target_agent_id in all_agents_data:
        target_agent = all_agents_data[target_agent_id]
        target_description = target_agent["name"] 

    if sub_type == "make_statement_to_agent":
        statement_content = details.get("statement_content") or full_action_json.get("speech")
        if not statement_content or not target_agent:
            return f"{agent_data['name']} seems to want to say something to {target_description}, but remains silent."
            
        # Add to speaker's memory
        add_memory_log(agent_data, f"You said to {target_description}: \"{statement_content}\"")
        
        # Add to target's memory
        add_memory_log(target_agent, f"{agent_data['name']} said to you: \"{statement_content}\"")
        
        return f"{agent_data['name']} says to {target_description}: \"{statement_content}\""

    elif sub_type == "talk_general":
        speech_content = full_action_json.get("speech")
        return f"{agent_data['name']} interacts with {target_description}."

    elif sub_type == "propose_new_need":
        need_desc = details.get("need_description", "a new task for the village")
        related_skills_prop = details.get("related_skills", ["general_effort"]) 
        urgency_prop = details.get("urgency", "medium")

        if len(world_data["active_needs"]) < 10: 
            new_need_id = f"N_User_{agent_data['name'][:3]}_{random.randint(100,999)}"
            world_data["active_needs"].append({
                "need_id": new_need_id, 
                "description": f"(Proposed by {agent_data['name']}) {need_desc}",
                "urgency": urgency_prop, 
                "related_skills": related_skills_prop, 
                "progress": 0.0, 
                "assigned_agents": [agent_data["agent_id"]] 
            })
            world_data["events_log"].append(f"{agent_data['name']} proposed a new village task: '{need_desc}'")
            return f"{agent_data['name']} proposed a new task for the village: '{need_desc}'."
        else:
            return f"{agent_data['name']} wanted to propose '{need_desc}', but the village already has many tasks on its mind."
    
    return f"{agent_data['name']} attempts to {sub_type.replace('_',' ')} with {target_description}."


if __name__ == '__main__':
    print("Action Handler - Test with Enhanced Craftable Items")
    
    def mock_llm_caller_test(prompt, model_name, temperature):
        if "allocate" in prompt.lower(): # For resource allocation
            # Simulate LLM deciding to keep 1, share 1 if 2 gained
            amount_in_prompt = 0
            try: # Basic parsing to get amount for mock
                parts = prompt.split("acquired ")[1].split(" ")
                amount_in_prompt = int(parts[0])
            except: pass
            
            k = amount_in_prompt // 2
            v = amount_in_prompt - k
            return json.dumps({
                "thought": f"Mock allocation: keep {k}, share {v}.",
                "allocation": {"personal_stash": k, "village_contribution": v }
            })
        # Default for other prompts (e.g., main action decision)
        return json.dumps({
            "thought": "Mock action: Decided to rest as a fallback.", 
            "action_type": "PERSONAL_ACTION", 
            "action_details": {"activity": "rest"}
        })

    class MockPrompterModule: # Simulate the prompter module for testing
        def generate_resource_allocation_prompt(self, agent, res_type, amount, world):
            return f"PROMPT_FOR_ALLOCATION: Agent {agent['name']} acquired {amount} {res_type}. World food: {world['village_resources']['food']}."
        def generate_agent_prompt(self, agent, world): # Needed if execute_action called it directly
            return "MAIN_AGENT_PROMPT_MOCK"

    mock_prompter_instance = MockPrompterModule()

    test_agent = {
        "agent_id": "crafter01", "name": "Artisan", 
        "skills": {"crafting": 3, "gathering": 2, "healing": 1}, 
        "status": {"health":100, "hunger":10, "energy":90},
        "inventory": {"flint_chip": 2}, # Start with some basic items
        "personal_resources": { # Start with materials for an axe and salve
            "sturdy_branch": 2, "sharpened_stone": 1, "vine_rope": 2, 
            "healing_herbs": 3, "animal_fat": 1, "thin_stick": 2, "flint_chip": 0 # Note: flint_chip in inventory now
            }, 
        "memory_log": []
    }
    test_world = {
        "day":1, 
        "village_resources": {"food":100, "wood":50, "stone":30, "herbs":10, "healing_herbs": 5, "sturdy_branch": 10}, 
        "active_needs": [{
            "need_id":"N002", "description":"Gather wood for shelters", 
            "related_skills":["gathering", "woodcutting"], "progress":0.0, "assigned_agents":[]
            }],
        "events_log": []
    }
    test_all_agents = {"crafter01": test_agent}

    print("\n--- Test Crafting Stone Axe ---")
    action_craft_axe = {
        "action_type": "PERSONAL_ACTION",
        "action_details": {"activity": "craft_item", "item_id": "stone_axe"},
        "speech": "Time to make a proper axe."
    }
    narration_axe = execute_action(test_agent, action_craft_axe, test_world, test_all_agents, mock_llm_caller_test, mock_prompter_instance)
    print(narration_axe)
    print(f"Inventory: {test_agent['inventory']}, Personal Res: {test_agent['personal_resources']}")
    print(f"Energy: {test_agent['status']['energy']}")

    print("\n--- Test Gathering Wood with Stone Axe ---")
    action_gather_wood = {
        "action_type": "ADDRESS_NEED",
        "action_details": {"need_id": "N002", "activity_description": "gather wood", "expected_contribution_skill": "gathering"},
        "speech": "Let's get some wood!"
    }
    if test_agent["inventory"].get("stone_axe",0) > 0: # Only if axe was crafted
        narration_wood = execute_action(test_agent, action_gather_wood, test_world, test_all_agents, mock_llm_caller_test, mock_prompter_instance)
        print(narration_wood)
        print(f"Personal Wood: {test_agent['personal_resources'].get('wood',0)}, Village Wood: {test_world['village_resources'].get('wood',0)}")
        print(f"Energy: {test_agent['status']['energy']}")
    else:
        print("Skipping gather wood with axe test as axe was not crafted.")

    print("\n--- Test Crafting Healing Salve ---")
    action_craft_salve = {
        "action_type": "PERSONAL_ACTION",
        "action_details": {"activity": "craft_item", "item_id": "basic_healing_salve"},
        "speech": "This might help someone."
    }
    narration_salve = execute_action(test_agent, action_craft_salve, test_world, test_all_agents, mock_llm_caller_test, mock_prompter_instance)
    print(narration_salve)
    print(f"Inventory: {test_agent['inventory']}, Personal Res: {test_agent['personal_resources']}")
    
    print("\n--- Test Consuming Healing Salve ---")
    if test_agent["inventory"].get("basic_healing_salve", 0) > 0:
        test_agent["status"]["health"] = 85 # Simulate some damage
        print(f"Health before salve: {test_agent['status']['health']}")
        action_eat_salve = {
            "action_type": "PERSONAL_ACTION",
            "action_details": {"activity": "eat_from_inventory", "consume_item": "basic_healing_salve", "amount": 1},
            "speech": "Feeling a bit hurt, hope this works."
        }
        narration_eat_salve = execute_action(test_agent, action_eat_salve, test_world, test_all_agents, mock_llm_caller_test, mock_prompter_instance)
        print(narration_eat_salve)
        print(f"Health after salve: {test_agent['status']['health']}")
        print(f"Inventory: {test_agent['inventory']}")
    else:
        print("Skipping consume salve test as it was not crafted.")

