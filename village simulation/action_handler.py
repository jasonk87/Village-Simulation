# action_handler.py
# Handles the execution of specific actions chosen by agents.

import json
import random
import asyncio # Added for async operations
import config # Now includes CRAFTABLE_ITEMS with detailed properties
import game_utils

def add_memory_log(agent_data, entry):
    """Helper to add to agent's memory log, ensuring it exists."""
    agent_data.setdefault("memory_log", []).append(entry)
    if len(agent_data["memory_log"]) > config.MAX_MEMORY_LOG:
        agent_data["memory_log"] = agent_data["memory_log"][-config.MAX_MEMORY_LOG:]

def _get_equipped_item_effects(agent_data, action_type=None, target_resource=None):
    applicable_effects = []
    if not isinstance(agent_data.get("inventory"), dict): return applicable_effects
    for item_id, quantity in agent_data["inventory"].items():
        if quantity > 0 and item_id in config.CRAFTABLE_ITEMS:
            item_def = config.CRAFTABLE_ITEMS[item_id]
            item_properties = item_def.get("properties", {})
            for effect in item_properties.get("effects", []):
                is_relevant = False
                condition = effect.get("condition", "equipped")
                if condition == "equipped":
                    if effect.get("type") == "gathering_yield" and effect.get("resource") == target_resource: is_relevant = True
                    elif effect.get("type") == "action_energy_modifier" and effect.get("action") == action_type: is_relevant = True
                if item_properties.get("item_category") == "tool" and action_type and \
                   ( (item_properties.get("tool_type") == "axe" and action_type == "gather_wood") or \
                     (item_properties.get("tool_type") == "knife" and action_type == "gather_herbs") ):
                     if effect.get("type") == "gathering_yield" and effect.get("resource") == target_resource: is_relevant = True
                     elif effect.get("type") == "action_energy_modifier" and effect.get("action") == action_type: is_relevant = True
                if item_properties.get("item_category") == "weapon" and action_type == "combat":
                    if effect.get("type") == "combat_damage": is_relevant = True
                if is_relevant: applicable_effects.append(effect)
    applicable_effects = []
    inventory = agent_data.get("inventory")
    if not isinstance(inventory, dict):
        return applicable_effects

    for item_id, quantity in inventory.items():
        if quantity <= 0:
            continue

        item_def = config.CRAFTABLE_ITEMS.get(item_id)
        if not item_def:
            continue

        item_properties = item_def.get("properties", {})
        item_category = item_properties.get("item_category")
        tool_type = item_properties.get("tool_type")

        for effect in item_properties.get("effects", []):
            condition = effect.get("condition", "equipped")
            effect_type = effect.get("type")
            effect_action = effect.get("action")
            effect_resource = effect.get("resource")
            is_relevant = False

            if condition == "equipped": # Assuming all items in inventory are "equipped" for effect purposes
                if effect_type == "gathering_yield" and effect_resource == target_resource:
                    # General gathering yield, or specific tool match
                    if item_category == "tool":
                        if (tool_type == "axe" and action_type == "gather_wood") or \
                           (tool_type == "knife" and action_type == "gather_herbs") or \
                           (not tool_type and action_type): # Generic tool for any specified action
                             is_relevant = True
                    elif not tool_type: # Non-tool item that gives general gathering bonus for the resource
                        is_relevant = True
                elif effect_type == "action_energy_modifier" and effect_action == action_type:
                    is_relevant = True
                elif item_category == "weapon" and action_type == "combat" and effect_type == "combat_damage":
                    is_relevant = True

            if is_relevant:
                applicable_effects.append(effect)

    return applicable_effects

# --- Resource Gathering Helper ---
async def _perform_gather_resource(agent_data, resource_to_gather, skill_level, base_difficulty, base_yield_range,
                                   action_type_for_effects, is_for_need, world_data, all_agents_data,
                                   llm_caller, prompt_generator_allocation_func, activity_desc_override=None):
    """
    Handles the logic for gathering a specific resource.
    Returns a narration string of the outcome.
    """
    tool_effects = _get_equipped_item_effects(agent_data, action_type_for_effects, resource_to_gather)
    yield_bonus_flat = 0
    activity_description = activity_desc_override or f"gathering {resource_to_gather.replace('_', ' ')}"

    for effect in tool_effects:
        if effect.get("type") == "gathering_yield" and effect.get("resource") == resource_to_gather:
            yield_bonus_flat += effect.get("bonus_flat", 0)

    if yield_bonus_flat > 0:
        add_memory_log(agent_data, f"Used a tool, improving {resource_to_gather} gathering.")
        activity_description += " (using a tool)"
    else:
        add_memory_log(agent_data, f"Gathered {resource_to_gather} with basic means.")

    if game_utils.perform_skill_check(skill_level, difficulty=base_difficulty):
        amount_gained = random.randint(base_yield_range[0], base_yield_range[1]) + (skill_level // 2) + yield_bonus_flat
        amount_gained = max(0, amount_gained)

        if amount_gained > 0:
            if is_for_need:
                allocation_narration = await _decide_and_allocate_resources(agent_data, resource_to_gather, amount_gained, world_data, all_agents_data, llm_caller, prompt_generator_allocation_func)
                return f"{agent_data['name']} diligently {activity_description}, acquiring {amount_gained} {resource_to_gather}. They {allocation_narration}", amount_gained
            else: # Personal gathering
                agent_data["personal_resources"].setdefault(resource_to_gather, 0)
                agent_data["personal_resources"][resource_to_gather] += amount_gained
                add_memory_log(agent_data, f"Personally gathered {amount_gained} {resource_to_gather.replace('_',' ')}.")
                return f"{agent_data['name']} foraged and found {amount_gained} {resource_to_gather.replace('_',' ')}, adding it to their personal supply.", amount_gained
        else:
            return f"{agent_data['name']} searched for {resource_to_gather.replace('_',' ')} but found none this time.", 0
    else:
        return f"{agent_data['name']} attempted to {activity_description} but failed to gather any significant {resource_to_gather}.", 0

async def _decide_and_allocate_resources(agent_data, resource_type, amount_gained, world_data, all_agents_data, llm_caller, prompt_generator_func):
    add_memory_log(agent_data, f"Gained {amount_gained} {resource_type}. Deciding on allocation.")
    agent_data.setdefault("personal_resources", {res_type: 0 for res_type in config.INITIAL_VILLAGE_RESOURCES.keys()})
    allocation_decision_json = None
    if config.USE_MOCK_LLM:
        keep_personal = random.randint(0, amount_gained) if "selfish" in agent_data.get("personality_traits", []) else random.randint(0, amount_gained // 2)
        contribute_village = amount_gained - keep_personal
        allocation_decision_json = {"thought": "Mock allocation decision.", "allocation": {"personal_stash": keep_personal, "village_contribution": contribute_village}}
    else:
        if llm_caller and prompt_generator_func:
            allocation_prompt = prompt_generator_func(agent_data, resource_type, amount_gained, world_data)
            response_str = await llm_caller(allocation_prompt, model_name=config.OLLAMA_DEFAULT_MODEL, temperature=config.OLLAMA_TEMPERATURE)
            try:
                parsed_llm_response = json.loads(response_str)
                if "response" in parsed_llm_response and isinstance(parsed_llm_response["response"], str):
                    allocation_decision_json = json.loads(parsed_llm_response["response"])
                else:
                    allocation_decision_json = parsed_llm_response # If the response is already the JSON object
            except json.JSONDecodeError: # Handle cases where response_str might be the direct JSON
                try:
                    allocation_decision_json = json.loads(response_str)
                except json.JSONDecodeError:
                    add_memory_log(agent_data, f"Error decoding allocation decision for {resource_type}. Raw: {response_str[:100]}")
                    allocation_decision_json = {"allocation": {"personal_stash": 0, "village_contribution": amount_gained}, "thought": "Fallback: Contributed all due to unclear thought."}
        else:
            add_memory_log(agent_data, "SYSTEM ERROR: LLM components not available for allocation decision.")
            allocation_decision_json = {"allocation": {"personal_stash": 0, "village_contribution": amount_gained}, "thought": "Fallback: Contributed all due to system error."}

    allocation = allocation_decision_json.get("allocation", {})
    kept_personal = allocation.get("personal_stash", 0)
    contributed_village = allocation.get("village_contribution", 0)
    try:
        kept_personal = int(kept_personal); contributed_village = int(contributed_village)
    except ValueError:
        add_memory_log(agent_data, f"Error: Non-integer allocation for {resource_type}. Defaulting."); kept_personal = 0; contributed_village = amount_gained
    if kept_personal < 0: kept_personal = 0
    if contributed_village < 0: contributed_village = 0
    if kept_personal + contributed_village != amount_gained:
        add_memory_log(agent_data, f"Warning: LLM allocation for {resource_type} didn't sum. Prioritizing personal."); kept_personal = min(amount_gained, kept_personal); actual_contributed = amount_gained - kept_personal
    else: actual_contributed = contributed_village
    agent_data["personal_resources"].setdefault(resource_type, 0); agent_data["personal_resources"][resource_type] += kept_personal
    world_data["village_resources"].setdefault(resource_type, 0); world_data["village_resources"][resource_type] += actual_contributed
    add_memory_log(agent_data, f"Allocation thought: {allocation_decision_json.get('thought', '...')[:100]}")
    add_memory_log(agent_data, f"Allocated {resource_type}: {kept_personal} to self, {actual_contributed} to village.")
    if kept_personal > 0 and actual_contributed > 0: return f"decided to keep {kept_personal} {resource_type} and contribute {actual_contributed} to the village."
    elif kept_personal > 0: return f"kept all {kept_personal} {resource_type} for themself."
    elif actual_contributed > 0: return f"contributed all {actual_contributed} {resource_type} to the village stockpile."
    return f"gained {amount_gained} {resource_type} but didn't allocate any (or gained 0)."

def _validate_and_get_item_source(agent_data: dict, item_id: str, quantity: int) -> str | None:
    """
    Checks if the agent possesses the specified item in the given quantity.
    Returns the source ('personal_resources' or 'inventory') if found, otherwise None.

    Args:
        agent_data: The agent's data dictionary.
        item_id: The ID of the item to check.
        quantity: The required quantity of the item.

    Returns:
        A string indicating the source location ("personal_resources" or "inventory")
        if the item is found in sufficient quantity, otherwise None.
    """
    if not item_id or quantity <= 0:  # Basic validation
        return None

    # Check personal_resources first (e.g., raw materials)
    if item_id in agent_data.get("personal_resources", {}) and \
       agent_data["personal_resources"][item_id] >= quantity:
        return "personal_resources"

    # Then check inventory (e.g., crafted items, tools)
    if item_id in agent_data.get("inventory", {}) and \
       agent_data["inventory"][item_id] >= quantity:
        return "inventory"

    return None

def _transfer_items_for_trade(proposer_agent, responder_agent, proposal, world_data): # Added world_data for event logging
    """Transfers items as per the accepted proposal. Assumes pre-validation of items. Returns True if successful."""

    # Helper sub-function to handle item movement for one side of the trade
    def _move_item_stack(from_agent, to_agent, item_id, quantity_to_move, item_source_location):
        from_agent[item_source_location][item_id] -= quantity_to_move
        if from_agent[item_source_location][item_id] == 0 and item_source_location == "inventory":
            # Only delete key if it's from inventory and count is zero.
            # For personal_resources, we keep the key even if it's 0 for consistency.
            del from_agent[item_source_location][item_id]

        receiver_destination_location = "inventory" if item_id in config.CRAFTABLE_ITEMS else "personal_resources"
        to_agent.setdefault(receiver_destination_location, {})
        to_agent[receiver_destination_location][item_id] = to_agent[receiver_destination_location].get(item_id, 0) + quantity_to_move

    # Transfer items from proposer to responder
    for item_to_give in proposal['offered_by_proposer']:
        item_id = item_to_give['item_id']
        quantity = item_to_give['quantity']
        proposer_source = _validate_and_get_item_source(proposer_agent, item_id, quantity)

        if not proposer_source:
            add_memory_log(proposer_agent, f"Trade Error: Tried to give {quantity} {item_id} but no longer have it.")
            add_memory_log(responder_agent, f"Trade Error: {proposer_agent['name']} no longer has {quantity} {item_id} to give.")
            world_data["events_log"].append(f"Trade (ID: {proposal['proposal_id']}) failed: {proposer_agent['name']} missing items.")
            return False

        proposer_agent[proposer_source][item_id] -= quantity
        _move_item_stack(proposer_agent, responder_agent, item_id, quantity, proposer_source)

    # Transfer items from responder to proposer
    for item_to_take in proposal['requested_from_target']:
        item_id = item_to_take['item_id']
        quantity = item_to_take['quantity']
        responder_source = _validate_and_get_item_source(responder_agent, item_id, quantity)

        if not responder_source:
            add_memory_log(responder_agent, f"Trade Error: Tried to give {quantity} {item_id} but no longer have it.")
            add_memory_log(proposer_agent, f"Trade Error: {responder_agent['name']} no longer has {quantity} {item_id} to give.")
            world_data["events_log"].append(f"Trade (ID: {proposal['proposal_id']}) failed: {responder_agent['name']} missing items.")
            return False

        responder_agent[responder_source][item_id] -= quantity
        _move_item_stack(responder_agent, proposer_agent, item_id, quantity, responder_source)
    return True


async def execute_action(agent_data, action_json, world_data, all_agents_data, llm_caller, prompter_module):
    world_data.setdefault('pending_trade_proposals', [])
    action_type = action_json.get("action_type")
    details = action_json.get("action_details", {})
    narration = f"{agent_data['name']} seems unsure what to do."

    agent_data.setdefault("personal_resources", {res_type: 0 for res_type in config.INITIAL_VILLAGE_RESOURCES.keys()})
    if not isinstance(agent_data.get("inventory"), dict):
        agent_data["inventory"] = game_utils.convert_inventory_to_dict_format(agent_data.get("inventory", []))

    if action_type == "SOCIAL_ACTION":
        social_energy_cost = 1
        agent_data["status"]["energy"] = max(0, agent_data["status"]["energy"] - social_energy_cost)
        agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + 1)

        social_narration = await _handle_social_action(agent_data, details, world_data, all_agents_data, action_json)

        if details.get("sub_type") in ["make_statement_to_agent", "talk_general"]:
            agent_data["status"]["energy"] = min(100, agent_data["status"]["energy"] + (config.BASE_ENERGY_COST_PER_ACTION - social_energy_cost))
            if llm_caller and prompter_module:
                next_action_prompt = prompter_module.generate_agent_prompt(agent_data, world_data)
                try:
                    raw_llm_response_for_next_action = await llm_caller(next_action_prompt, model_name=config.OLLAMA_DEFAULT_MODEL, temperature=config.OLLAMA_TEMPERATURE)
                    try:
                        outer_response_obj = json.loads(raw_llm_response_for_next_action)
                        inner_json_str = outer_response_obj.get("response", raw_llm_response_for_next_action)
                        if isinstance(inner_json_str, str): next_action_json = json.loads(inner_json_str)
                        else: next_action_json = inner_json_str
                    except json.JSONDecodeError: next_action_json = json.loads(raw_llm_response_for_next_action)
                    if next_action_json.get("action_type") != "SOCIAL_ACTION": # Avoid social action loops for now
                        return f"{social_narration}\nThen, " + await execute_action(agent_data, next_action_json, world_data, all_agents_data, llm_caller, prompter_module)
                except (json.JSONDecodeError, TypeError, KeyError) as e: add_memory_log(agent_data, f"Error getting next action after social: {str(e)[:100]}")
            else: add_memory_log(agent_data, "Could not get next action: LLM or prompter missing.")
        return social_narration

    current_action_energy_cost = config.BASE_ENERGY_COST_PER_ACTION
    current_action_hunger_increase = config.BASE_HUNGER_INCREASE_PER_ACTION
    if action_type == "ADDRESS_NEED" or (action_type == "PERSONAL_ACTION" and details.get("activity","").startswith("gather_")):
        action_activity_for_effects = details.get("activity", "")
        if action_type == "ADDRESS_NEED":
            if "wood" in details.get("activity_description","").lower(): action_activity_for_effects = "gather_wood"
            elif "herb" in details.get("activity_description","").lower(): action_activity_for_effects = "gather_herbs"
        item_effects = _get_equipped_item_effects(agent_data, action_activity_for_effects)
        for effect in item_effects:
            if effect.get("type") == "action_energy_modifier" and effect.get("action") == action_activity_for_effects:
                current_action_energy_cost += effect.get("modifier", 0)
    agent_data["status"]["energy"] = max(0, agent_data["status"]["energy"] - current_action_energy_cost)
    agent_data["status"]["hunger"] = min(100, agent_data["status"]["hunger"] + current_action_hunger_increase)

    if action_type == "ADDRESS_NEED":
        narration = await _handle_address_need(agent_data, details, world_data, all_agents_data, llm_caller, prompter_module.generate_resource_allocation_prompt)
    elif action_type == "PERSONAL_ACTION":
        narration = await _handle_personal_action(agent_data, details, world_data, all_agents_data, llm_caller, prompter_module.generate_resource_allocation_prompt)
    else:
        if action_type != "SOCIAL_ACTION": # Already handled above
            narration = f"{agent_data['name']} performs an unrecognized action: '{action_type}'. They look puzzled."
            add_memory_log(agent_data, f"Attempted unknown action: {action_type}")
    for status_key in ["health", "hunger", "energy"]:
        agent_data["status"][status_key] = max(0, min(100, agent_data["status"][status_key]))
    return narration

async def _handle_address_need(agent_data, details, world_data, all_agents_data, llm_caller, prompt_generator_allocation_func):
    need_id = details.get("need_id"); skill_used_by_llm = details.get("expected_contribution_skill", "general_effort"); activity_desc = details.get("activity_description", f"working on task {need_id}")
    target_need = next((n for n in world_data["active_needs"] if n["need_id"] == need_id), None)
    if not target_need: return f"{agent_data['name']} tried to work on task '{need_id}', but it no longer exists or is invalid."
    add_memory_log(agent_data, f"Focused on task: {activity_desc} (Need ID: {need_id})"); agent_data["current_focus_need_id"] = need_id
    if agent_data["agent_id"] not in target_need.get("assigned_agents", []): target_need.setdefault("assigned_agents", []).append(agent_data["agent_id"])
    actual_skill_to_use = skill_used_by_llm
    if target_need.get("related_skills"):
        if skill_used_by_llm not in target_need["related_skills"]:
            best_skill_val = -1
            for skill_option in target_need["related_skills"]:
                if agent_data["skills"].get(skill_option, 0) > best_skill_val: best_skill_val = agent_data["skills"].get(skill_option, 0); actual_skill_to_use = skill_option
            if best_skill_val == -1 : actual_skill_to_use = "general_effort" # Fallback if no matching skills
    skill_level = agent_data["skills"].get(actual_skill_to_use, 0) if actual_skill_to_use != "general_effort" else 0; task_difficulty = target_need.get("difficulty", 3)
    resource_gathered_for_need = None; action_type_for_effects = "unknown_action"; gather_config_key = None

    if "wood" in activity_desc.lower() or (target_need.get("related_skills") and "woodcutting" in target_need["related_skills"]):
        resource_gathered_for_need = "wood"; action_type_for_effects = "gather_wood"; gather_config_key = "wood" # Assuming key in GATHERABLE_PERSONAL_RESOURCES
    elif "herb" in activity_desc.lower() or (target_need.get("related_skills") and "herbalism" in target_need["related_skills"]):
        resource_gathered_for_need = "herbs"; action_type_for_effects = "gather_herbs"; gather_config_key = "healing_herbs" # Assuming key

    if resource_gathered_for_need and gather_config_key and gather_config_key in config.GATHERABLE_PERSONAL_RESOURCES:
        gather_info = config.GATHERABLE_PERSONAL_RESOURCES[gather_config_key]
        # Use skill_level (already determined based on need or agent's best)
        # Use task_difficulty from the need as override
        main_narration, amount_gained = await _perform_gather_resource(
            agent_data, resource_gathered_for_need, skill_level, task_difficulty,
            gather_info["base_yield"], action_type_for_effects,
            is_for_need=True, world_data=world_data, all_agents_data=all_agents_data,
            llm_caller=llm_caller, prompt_generator_allocation_func=prompt_generator_allocation_func,
            activity_desc_override=activity_desc
        )
        if amount_gained > 0:
            target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (config.PROGRESS_PER_SUCCESSFUL_GATHER * amount_gained * (skill_level + 1))) # Adjusted progress factor
            return f"{main_narration} (Task progress: {target_need['progress']:.0%})"
        else:
            return main_narration # Returns the failure message from _perform_gather_resource

    # If not resource gathering for the need, or if it's a different type of need contribution
    if game_utils.perform_skill_check(skill_level, difficulty=task_difficulty):
        contribution_amount = random.randint(1, skill_level + 2) # Base contribution

        # Check for material consuming tasks like building or specific crafting needs
        if actual_skill_to_use in ["building", "crafting"] and \
           any(s in target_need.get("related_skills", []) for s in ["building", "crafting"]) and \
           "required_materials" in target_need:
            mats_ok = True; materials_consumed_this_turn = {}
            if "required_materials" in target_need:
                for mat, req_amount_per_tick in target_need["required_materials"].items():
                    if world_data["village_resources"].get(mat, 0) < req_amount_per_tick:
                        mats_ok = False; return f"{agent_data['name']} attempted to {activity_desc}, but the village lacks enough {mat} ({req_amount_per_tick} needed for this step)."
                    else: materials_consumed_this_turn[mat] = materials_consumed_this_turn.get(mat, 0) + req_amount_per_tick
            if mats_ok:
                for mat, consumed_amount in materials_consumed_this_turn.items(): world_data["village_resources"][mat] = max(0, world_data["village_resources"][mat] - consumed_amount)
                target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.05 * contribution_amount * (skill_level + 1)))
                return f"{agent_data['name']} skillfully {activity_desc}. The task is now {target_need['progress']:.0%} complete."
        else: # General contribution, not resource-gathering or material-consuming crafting/building
            target_need["progress"] = min(1.0, target_need.get("progress", 0.0) + (0.03 * contribution_amount))
            return f"{agent_data['name']} contributed to {activity_desc}. (Task progress: {target_need['progress']:.0%})"
    else: return f"{agent_data['name']} attempted to {activity_desc} using {actual_skill_to_use}, but made little headway."

async def _handle_personal_action(agent_data, details, world_data, all_agents_data, llm_caller, prompt_generator_allocation_func):
    activity = details.get("activity", "act personally")
    if activity == "rest":
        energy_gained = config.REST_ENERGY_GAIN + random.randint(-5, 5); agent_data["status"]["energy"] = min(100, agent_data["status"]["energy"] + energy_gained)
        return f"{agent_data['name']} took a moment to rest, regaining {energy_gained} energy. (Energy: {agent_data['status']['energy']})"
    elif activity == "observe_environment":
        focus = details.get("focus"); observation_made = "Observed nothing of particular interest in the immediate surroundings."; narration = f"{agent_data['name']} "
        gathering_skill = agent_data['skills'].get('gathering', 0); hunting_skill = agent_data['skills'].get('hunting', 0); healing_skill = agent_data['skills'].get('healing', 0)
        if focus == "flora":
            narration += "carefully scans the nearby bushes and trees."
            if gathering_skill > 3: observation_made = "Noticed some edible-looking berries a short distance away."
            elif gathering_skill > 1: observation_made = "Spotted a patch of common herbs nearby."
            elif healing_skill > 2: observation_made = "Identified some plants that might have medicinal properties, but unsure."
        elif focus == "fauna_tracks":
            narration += "kneels down to examine the ground for tracks."
            if hunting_skill > 3: observation_made = "Found fresh deer tracks leading east."
            elif hunting_skill > 1: observation_made = "Saw signs of rabbits in the undergrowth."
        elif focus == "danger_signs":
            narration += "sniffs the air and listens intently for any signs of danger."
            if hunting_skill > 2: observation_made = "The area seems clear, but there's an old predator scent lingering."
            else: observation_made = "Everything seems calm and peaceful here."
        else:
            narration += "takes a moment to observe the surroundings."
            if gathering_skill > 2: observation_made = "The forest seems quiet here. Some common birds are chirping. Spotted a few common plants."
            elif hunting_skill > 2: observation_made = "A few squirrels are chattering nearby. No immediate threats visible."
            elif healing_skill > 1: observation_made = "Some common mosses and fungi are present on the trees."
        add_memory_log(agent_data, observation_made); return f"{narration} They noted: \"{observation_made}\""
    elif activity == "eat_from_inventory":
        item_to_eat_id = details.get("consume_item", "food_rations"); amount_to_eat = details.get("amount", 1)
        if agent_data["inventory"].get(item_to_eat_id, 0) >= amount_to_eat:
            item_def = config.CRAFTABLE_ITEMS.get(item_to_eat_id); hunger_reduced = 0; health_gained = 0
            if item_def and item_def["properties"]["item_category"] == "consumable":
                for effect in item_def["properties"].get("effects", []):
                    if effect.get("type") == "stat_change_on_consume":
                        if effect.get("stat") == "hunger": hunger_reduced += effect.get("change", 0)
                        elif effect.get("stat") == "health": health_gained += effect.get("change", 0)
                agent_data["inventory"][item_to_eat_id] -= amount_to_eat
                if agent_data["inventory"][item_to_eat_id] <= 0: del agent_data["inventory"][item_to_eat_id]
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] + hunger_reduced); agent_data["status"]["health"] = min(100, agent_data["status"]["health"] + health_gained)
                narration_eat = f"{agent_data['name']} consumed {amount_to_eat} {item_def['name']}.";
                if hunger_reduced != 0: narration_eat += f" Hunger now {agent_data['status']['hunger']}."
                if health_gained != 0: narration_eat += f" Health now {agent_data['status']['health']}."
                return narration_eat
            else: # Generic non-defined consumable item like 'food_rations' if not in CRAFTABLE_ITEMS
                agent_data["inventory"][item_to_eat_id] -= amount_to_eat
                if agent_data["inventory"][item_to_eat_id] <= 0: del agent_data["inventory"][item_to_eat_id]
                hunger_reduced_generic = random.randint(15, 30) * amount_to_eat; agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - hunger_reduced_generic)
                return f"{agent_data['name']} ate {amount_to_eat} {item_to_eat_id.replace('_',' ')}. (Hunger: {agent_data['status']['hunger']})"
        else:
            if item_to_eat_id in agent_data.get("personal_resources", {}) and agent_data["personal_resources"].get(item_to_eat_id,0) >= amount_to_eat: # Eating raw resource
                agent_data["personal_resources"][item_to_eat_id] -= amount_to_eat; hunger_reduced_raw = random.randint(5, 15) * amount_to_eat
                agent_data["status"]["hunger"] = max(0, agent_data["status"]["hunger"] - hunger_reduced_raw)
                return f"{agent_data['name']} ate {amount_to_eat} raw {item_to_eat_id.replace('_',' ')}. (Hunger: {agent_data['status']['hunger']})"
            else: return f"{agent_data['name']} wanted to eat {amount_to_eat} {item_to_eat_id.replace('_',' ')} but didn't have enough."
    elif activity == "gather_resource": # Personal gathering
        resource_to_gather = details.get("resource_id", None)
        if not resource_to_gather or resource_to_gather not in config.GATHERABLE_PERSONAL_RESOURCES:
            return f"{agent_data['name']} tried to gather an unknown resource: '{resource_to_gather or 'unspecified'}'. They look confused."

        gather_info = config.GATHERABLE_PERSONAL_RESOURCES[resource_to_gather]
        skill_to_use = gather_info["skill"]
        skill_level = agent_data["skills"].get(skill_to_use, 0)
        difficulty = gather_info["base_difficulty"]
        action_type_for_effects = f"gather_{resource_to_gather}" # e.g., "gather_wood", "gather_healing_herbs"

        narration, _ = await _perform_gather_resource( # amount_gained is handled internally by _perform_gather_resource for personal
            agent_data, resource_to_gather, skill_level, difficulty,
            gather_info["base_yield"], action_type_for_effects,
            is_for_need=False, world_data=world_data, all_agents_data=all_agents_data,
            llm_caller=llm_caller, prompt_generator_allocation_func=prompt_generator_allocation_func
        )
        return narration
    elif activity == "craft_item":
        item_id_to_craft = details.get("item_id", None)
        if not item_id_to_craft or item_id_to_craft not in config.CRAFTABLE_ITEMS:
            return f"{agent_data['name']} tried to craft an unknown item: '{item_id_to_craft or 'unspecified'}'. They look confused."
        item_def = config.CRAFTABLE_ITEMS[item_id_to_craft]; recipe = item_def["recipe"]; skill_req_name = item_def["skill_required"]; min_skill = item_def["min_skill_level"]
        agent_skill_level = agent_data["skills"].get(skill_req_name, 0); crafting_energy_cost = item_def.get("energy_cost", config.BASE_ENERGY_COST_PER_ACTION)
        agent_data["status"]["energy"] -= (crafting_energy_cost - config.BASE_ENERGY_COST_PER_ACTION)
        if agent_skill_level < min_skill: return f"{agent_data['name']} lacks the required {skill_req_name} skill (needs {min_skill}, has {agent_skill_level}) to craft a {item_def['name']}."
        has_materials = True; missing_mats_str = []
        for material, count_needed in recipe.items():
            if agent_data["personal_resources"].get(material, 0) < count_needed: has_materials = False; missing_mats_str.append(f"{count_needed} {material.replace('_',' ')}")
        if not has_materials: return f"{agent_data['name']} wanted to craft a {item_def['name']} but lacked: {', '.join(missing_mats_str)}."
        crafting_difficulty = item_def.get("difficulty", 3)
        if game_utils.perform_skill_check(agent_skill_level, difficulty=crafting_difficulty):
            for material, count_needed in recipe.items(): agent_data["personal_resources"][material] -= count_needed
            items_yielded = item_def.get("yield", 1); agent_data["inventory"].setdefault(item_id_to_craft, 0); agent_data["inventory"][item_id_to_craft] += items_yielded
            add_memory_log(agent_data, f"Successfully crafted {items_yielded}x {item_def['name']}.")
            return f"{agent_data['name']} successfully crafted {items_yielded}x {item_def['name']} ({item_id_to_craft})!"
        else:
            add_memory_log(agent_data, f"Fumbled while trying to craft a {item_def['name']}."); return f"{agent_data['name']} fumbled while trying to craft a {item_def['name']}."
    elif activity == "upgrade_shelter":
        current_level = agent_data.get("shelter_level", 0)
        next_level = current_level + 1
        if next_level not in config.SHELTER_UPGRADE_COSTS:
            return f"{agent_data['name']} feels their current shelter (Level {current_level}) is the best it can be for now."
        cost = config.SHELTER_UPGRADE_COSTS[next_level]
        can_afford = True
        missing_shelter_mats = []
        for item, required_qty in cost.items():
            if agent_data["personal_resources"].get(item, 0) < required_qty:
                can_afford = False
                missing_shelter_mats.append(f"{required_qty} {item.replace('_',' ')}")
        if can_afford:
            for item, required_qty in cost.items():
                agent_data["personal_resources"][item] -= required_qty
            agent_data["shelter_level"] = next_level
            add_memory_log(agent_data, f"Upgraded shelter to level {next_level}.")
            return f"{agent_data['name']} worked hard and improved their shelter to level {next_level} ({game_utils.get_shelter_description(next_level)})!"
        else:
            return f"{agent_data['name']} wanted to upgrade their shelter to level {next_level}, but lacked: {', '.join(missing_shelter_mats)}."
    elif activity == "error_idle": return f"{agent_data['name']} {random.choice(['seems dazed.', 'is momentarily confused.', 'stares blankly for a moment.'])}"
    return f"{agent_data['name']} decided to {activity.replace('_',' ')} for their own reasons."

# --- Social Action Sub-Handlers ---
async def _social_make_statement(agent_data: dict, details: dict, target_agent: dict | None, target_description: str, full_action_json: dict) -> str:
    """Handles an agent making a statement to another agent."""
    statement_content = details.get("statement_content") or full_action_json.get("speech")
    if not statement_content or not target_agent: # target_agent is now the resolved object
        return f"{agent_data['name']} seems to want to say something to {target_description}, but remains silent."
    add_memory_log(agent_data, f"You said to {target_description}: \"{statement_content}\"")
    # target_agent is already the agent object, no need to look up with all_agents_data
    add_memory_log(target_agent, f"{agent_data['name']} said to you: \"{statement_content}\"")
    return f"{agent_data['name']} says to {target_description}: \"{statement_content}\""

async def _social_talk_general(agent_data: dict, target_agent: dict | None, target_description: str) -> str:
    """Handles an agent performing a general interaction."""
    return f"{agent_data['name']} interacts with {target_description if target_agent else 'the surroundings'}."

async def _social_propose_new_need(agent_data: dict, details: dict, world_data: dict, full_action_json: dict) -> str:
    """Handles an agent proposing a new need or suggesting for an existing one."""
    need_desc = details.get("need_description", "a new task for the village")
    related_skills_prop = details.get("related_skills", ["general_effort"]) # Ensure this is a list
    urgency_prop = details.get("urgency", "medium")
    target_need_id_suggestion = details.get("target_need_id")

    if target_need_id_suggestion:
        existing_need = next((n for n in world_data["active_needs"] if n["need_id"] == target_need_id_suggestion), None)
        if existing_need:
            suggestion_content = details.get("suggestion_content") or full_action_json.get("speech", "a suggestion")
            existing_need["description"] += f" (Suggestion by {agent_data['name']}: {suggestion_content})"
            event_message = f"{agent_data['name']} made a suggestion regarding task: '{existing_need['description'][:30]}...'"
            world_data["events_log"].append(event_message)
            add_memory_log(agent_data, f"Offered a suggestion for task {existing_need['need_id']}: {suggestion_content}")
            return f"{agent_data['name']} offered a suggestion for the task '{existing_need['description'][:50]}...'"
        else:
            add_memory_log(agent_data, f"Tried to suggest for non-existent task ID {target_need_id_suggestion}, will propose as new.")

    if len(world_data["active_needs"]) < 10: # Max needs
        new_need_id = f"N_User_{agent_data['name'][:3]}_{random.randint(100,999)}"
        while any(n['need_id'] == new_need_id for n in world_data['active_needs']):
            new_need_id = f"N_User_{agent_data['name'][:3]}_{random.randint(100,999)}"
        world_data["active_needs"].append({
            "need_id": new_need_id,
            "description": f"(Proposed by {agent_data['name']}) {need_desc}",
            "urgency": urgency_prop,
            "related_skills": related_skills_prop,
            "progress": 0.0,
            "assigned_agents": [agent_data["agent_id"]] # Automatically assign proposer
        })
        world_data["events_log"].append(f"{agent_data['name']} proposed a new village task: '{need_desc}'")
        add_memory_log(agent_data, f"Proposed a new task: {need_desc}")
        return f"{agent_data['name']} proposed a new task for the village: '{need_desc}'."
    else: # Max needs reached
        add_memory_log(agent_data, f"Wanted to propose '{need_desc}', but village has too many tasks.")
        return f"{agent_data['name']} wanted to propose '{need_desc}', but the village already has many tasks on its mind."

async def _social_give_item(agent_data: dict, details: dict, target_agent: dict | None, target_description: str, world_data: dict) -> str:
    """Handles an agent giving an item to another agent."""
    item_id = details.get("item_id")
    quantity = details.get("quantity", 1)

    if not target_agent: # target_agent is the resolved object
        return f"{agent_data['name']} wanted to give {item_id or 'an item'} to {target_description}, but couldn't find them."
    if not item_id or not isinstance(quantity, int) or quantity <= 0:
        add_memory_log(agent_data, f"Tried to give an invalid item or quantity to {target_description}.")
        return f"{agent_data['name']} fumbled trying to give something to {target_description} (invalid item/quantity)."

    source_location_giver = None # Will be agent_data["personal_resources"] or agent_data["inventory"]
    item_name_display = item_id.replace('_', ' ')
    if item_id in agent_data.get("personal_resources", {}) and agent_data["personal_resources"][item_id] >= quantity:
        source_location_giver = agent_data["personal_resources"]
    elif item_id in agent_data.get("inventory", {}) and agent_data["inventory"][item_id] >= quantity:
        source_location_giver = agent_data["inventory"]
        item_name_display = config.CRAFTABLE_ITEMS.get(item_id, {}).get("name", item_id.replace('_', ' '))
    else:
        add_memory_log(agent_data, f"Tried to give {quantity} {item_name_display} to {target_description}, but didn't have enough.")
        return f"{agent_data['name']} wanted to give {quantity} {item_name_display} to {target_description} but didn't have it."

    target_location_receiver = None
    if item_id in config.CRAFTABLE_ITEMS:
        target_agent.setdefault("inventory", {})
        target_location_receiver = target_agent["inventory"]
    else:
        target_agent.setdefault("personal_resources", {})
        target_location_receiver = target_agent["personal_resources"]

    source_location_giver[item_id] -= quantity
    if source_location_giver[item_id] == 0 and source_location_giver is agent_data["inventory"]:
        del source_location_giver[item_id]

    target_location_receiver[item_id] = target_location_receiver.get(item_id, 0) + quantity

    add_memory_log(agent_data, f"You gave {quantity} {item_name_display} to {target_description}.")
    # target_agent is already the agent object
    add_memory_log(target_agent, f"{agent_data['name']} gave you {quantity} {item_name_display}.")
    world_data["events_log"].append(f"{agent_data['name']} gave {quantity} {item_name_display} to {target_description}.")
    return f"{agent_data['name']} gave {quantity} {item_name_display} to {target_description}."

async def _social_steal_item(agent_data: dict, details: dict, target_agent: dict | None, target_description: str, world_data: dict) -> str:
    """Handles an agent attempting to steal an item from another agent."""
    item_id = details.get("item_id")
    quantity = details.get("quantity", 1)

    if not target_agent: # target_agent is the resolved object
        return f"{agent_data['name']} looked for someone to steal from but {target_description} was not clear."
    if not item_id or not isinstance(quantity, int) or quantity <= 0:
        add_memory_log(agent_data, f"My attempt to steal from {target_description} was ill-conceived (invalid item/quantity).")
        return f"{agent_data['name']} reconsidered stealing from {target_description} (invalid item/quantity)."

    attacker_skill = agent_data['skills'].get('thievery', 0) # Default to 0 if skill not present
    target_awareness = target_agent['skills'].get('awareness', 0)
    difficulty_mod = min(3, max(-3, target_awareness - attacker_skill)) # Max difficulty adjustment of +/-3
    steal_difficulty = max(1, 3 + difficulty_mod) # Base difficulty 3, adjusted by skill difference

    item_name_display = item_id.replace('_', ' ')
    source_location_target = None
    if item_id in target_agent.get("personal_resources", {}) and target_agent["personal_resources"][item_id] >= quantity:
        source_location_target = target_agent["personal_resources"]
    elif item_id in target_agent.get("inventory", {}) and target_agent["inventory"][item_id] >= quantity:
        source_location_target = target_agent["inventory"]
        item_name_display = config.CRAFTABLE_ITEMS.get(item_id, {}).get("name", item_id.replace('_', ' '))
    else:
        add_memory_log(agent_data, f"Tried to steal {item_name_display} from {target_description}, but they didn't have enough.")
        return f"{agent_data['name']} tried to steal {item_name_display} from {target_description}, but they didn't seem to have it."

    if game_utils.perform_skill_check(attacker_skill, difficulty=steal_difficulty):
        target_notices_difficulty = 3 + (attacker_skill // 2) # Higher attacker skill makes it harder for target to notice
        target_noticed_theft = not game_utils.perform_skill_check(target_awareness, difficulty=target_notices_difficulty)

        destination_thief = None
        if item_id in config.CRAFTABLE_ITEMS:
            agent_data.setdefault("inventory", {})
            destination_thief = agent_data["inventory"]
        else:
            agent_data.setdefault("personal_resources", {})
            destination_thief = agent_data["personal_resources"]

        source_location_target[item_id] -= quantity
        if source_location_target[item_id] == 0 and source_location_target is target_agent["inventory"]:
            del source_location_target[item_id]
        destination_thief[item_id] = destination_thief.get(item_id, 0) + quantity

        add_memory_log(agent_data, f"You successfully stole {quantity} {item_name_display} from {target_description}.")
        world_data["events_log"].append(f"A theft occurred: {agent_data['name']} stole from {target_description}.")
        if target_noticed_theft:
            add_memory_log(target_agent, f"You realized {quantity} {item_name_display} was stolen from you by {agent_data['name']}!")
            return f"{agent_data['name']} stole {quantity} {item_name_display} from {target_description}, who noticed the act!"
        else:
            add_memory_log(target_agent, f"You noticed {quantity} {item_name_display} is missing. You feel uneasy.")
            return f"{agent_data['name']} successfully stole {quantity} {item_name_display} from {target_description}."
    else: # Failed skill check for stealing
        target_notices_attempt_difficulty = 2 + attacker_skill # Easier for target to notice a failed attempt
        target_noticed_attempt = not game_utils.perform_skill_check(target_awareness, difficulty=target_notices_attempt_difficulty)
        if target_noticed_attempt:
            add_memory_log(agent_data, f"You failed to steal {item_name_display} from {target_description}, and they saw you!")
            add_memory_log(target_agent, f"{agent_data['name']} clumsily tried to steal {item_name_display} from you, but you caught them!")
            world_data["events_log"].append(f"{target_description} caught {agent_data['name']} trying to steal!")
            return f"{agent_data['name']} failed to steal {item_name_display} from {target_description} and was caught in the act!"
        else:
            add_memory_log(agent_data, f"You tried to steal {item_name_display} from {target_description} but failed without them noticing.")
            return f"{agent_data['name']} tried to steal {item_name_display} from {target_description} but failed."

async def _social_propose_trade(agent_data: dict, details: dict, target_agent: dict | None, target_description: str, world_data: dict, all_agents_data: dict) -> str:
    """Handles an agent proposing a trade to another agent."""
    items_offered = details.get("items_offered", [])
    items_requested = details.get("items_requested", [])

    if not target_agent: # target_agent is the resolved object
        return f"{agent_data['name']} looked for someone to trade with, but {target_description} was not clear."

    if not items_offered or not items_requested: # Basic check for empty offers/requests
        add_memory_log(agent_data, f"Tried to propose a trade with {target_description} but didn't specify items correctly.")
        return f"{agent_data['name']} started to propose a trade but didn't specify all items."

    for item_offer in items_offered:
        item_id_offer = item_offer.get('item_id')
        quantity_offer = item_offer.get('quantity', 0)
        if quantity_offer <= 0 or not _validate_and_get_item_source(agent_data, item_id_offer, quantity_offer):
            item_name_offer = item_id_offer.replace('_',' ') if item_id_offer else "unknown_item"
            add_memory_log(agent_data, f"Tried to offer {quantity_offer} {item_name_offer} for trade with {target_description} but didn't have enough or invalid quantity.")
            return f"{agent_data['name']} tried to offer {quantity_offer} {item_name_offer} for trade with {target_description} but didn't have enough or quantity was invalid."

    proposal_id = f"trade_{agent_data['agent_id']}_{random.randint(1000,9999)}"
    proposal = {
        "proposal_id": proposal_id, "proposer_id": agent_data['agent_id'],
        "proposer_name": agent_data['name'], "target_id": target_agent.get('agent_id'), # Use target_agent.id
        "target_name": target_description, "offered_by_proposer": items_offered,
        "requested_from_target": items_requested, "status": "pending"
    }
    world_data['pending_trade_proposals'].append(proposal)
    offered_str = ", ".join([f"{i['quantity']} {i['item_id']}" for i in items_offered])
    requested_str = ", ".join([f"{i['quantity']} {i['item_id']}" for i in items_requested])

    add_memory_log(agent_data, f"You proposed a trade (ID: {proposal_id}) to {target_description}, offering {offered_str} for {requested_str}.")
    # target_agent is already the agent object
    add_memory_log(target_agent, f"{agent_data['name']} proposed a trade (ID: {proposal_id}). They offer: {offered_str}. They want: {requested_str}.")
    world_data["events_log"].append(f"{agent_data['name']} proposed a trade to {target_description}.")
    return f"{agent_data['name']} proposes a trade to {target_description} offering {offered_str} for {requested_str}."

async def _social_respond_to_trade(agent_data: dict, details: dict, world_data: dict, all_agents_data: dict) -> str:
    """Handles an agent responding to a trade proposal."""
    proposal_id_resp = details.get("proposal_id")
    response_decision = details.get("response") # "accept" or "reject"

    if not proposal_id_resp or not response_decision:
        return f"{agent_data['name']} considered a trade but didn't specify the proposal or response."

    found_proposal = None
    # Iterate safely: do not modify list while iterating if possible, though here we only change status
    for p in world_data.get('pending_trade_proposals', []):
        if p['proposal_id'] == proposal_id_resp:
            found_proposal = p
            break # Found the proposal

    if not found_proposal:
        return f"{agent_data['name']} tried to respond to trade {proposal_id_resp}, but it doesn't exist."
    if found_proposal['target_id'] != agent_data['agent_id']: # Agent trying to respond to a trade not meant for them
        return f"{agent_data['name']} tried to respond to trade {proposal_id_resp}, but it wasn't for them."
    if found_proposal['status'] != "pending": # Trade already actioned
        return f"Trade {proposal_id_resp} is no longer pending ({found_proposal['status']})."

    proposer_agent = all_agents_data.get(found_proposal['proposer_id'])
    if not proposer_agent: # Proposer agent no longer exists (edge case)
        found_proposal['status'] = "failed_proposer_missing"
        world_data["events_log"].append(f"Trade (ID: {proposal_id_resp}) failed: Proposer {found_proposal['proposer_name']} is missing.")
        return f"The original proposer of trade {proposal_id_resp} is no longer around."

    if response_decision == "accept":
        # Validate both parties can fulfill the trade at the moment of acceptance
        can_proposer_give = all(_validate_and_get_item_source(proposer_agent, item['item_id'], item['quantity'])
                                for item in found_proposal['offered_by_proposer'])
        can_responder_give = all(_validate_and_get_item_source(agent_data, item['item_id'], item['quantity'])
                                 for item in found_proposal['requested_from_target'])

        if can_proposer_give and can_responder_give:
            if _transfer_items_for_trade(proposer_agent, agent_data, found_proposal, world_data):
                found_proposal['status'] = "accepted"
                world_data["events_log"].append(f"Trade (ID: {proposal_id_resp}) between {proposer_agent['name']} and {agent_data['name']} was accepted.")
                add_memory_log(proposer_agent, f"Your trade with {agent_data['name']} (ID: {proposal_id_resp}) was accepted. Items exchanged.")
                add_memory_log(agent_data, f"You accepted trade with {proposer_agent['name']} (ID: {proposal_id_resp}). Items exchanged.")
                return f"{agent_data['name']} accepted the trade (ID: {proposal_id_resp}) with {proposer_agent['name']}. Items were exchanged."
            else: # Should be rare if _validate_and_get_item_source is accurate and no race conditions
                found_proposal['status'] = "failed_transfer_error"
                return f"Trade (ID: {proposal_id_resp}) between {proposer_agent['name']} and {agent_data['name']} failed during transfer."
        else: # One or both parties cannot fulfill their side
            found_proposal['status'] = "failed_items_missing"
            missing_items_proposer_msg = "" if can_proposer_give else f"{proposer_agent['name']} is missing items. "
            missing_items_responder_msg = "" if can_responder_give else f"{agent_data['name']} is missing items. "
            full_fail_msg = f"Trade (ID: {proposal_id_resp}) could not be completed: {missing_items_proposer_msg}{missing_items_responder_msg}".strip()
            world_data["events_log"].append(full_fail_msg)
            add_memory_log(proposer_agent, full_fail_msg)
            add_memory_log(agent_data, full_fail_msg)
            return full_fail_msg
    elif response_decision == "reject":
        found_proposal['status'] = "rejected"
        world_data["events_log"].append(f"Trade (ID: {proposal_id_resp}) between {proposer_agent['name']} and {agent_data['name']} was rejected by {agent_data['name']}.")
        add_memory_log(proposer_agent, f"Your trade proposal (ID: {proposal_id_resp}) with {agent_data['name']} was rejected.")
        add_memory_log(agent_data, f"You rejected trade proposal (ID: {proposal_id_resp}) from {proposer_agent['name']}.")
        return f"{agent_data['name']} rejected the trade (ID: {proposal_id_resp}) with {proposer_agent['name']}."
    else: # Unclear response
        return f"{agent_data['name']} gave an unclear response to trade proposal {proposal_id_resp}."

# Main Social Action Handler
async def _handle_social_action(agent_data: dict, details: dict, world_data: dict, all_agents_data: dict, full_action_json: dict) -> str:
    """
    Routes social actions to specific sub-handler functions.
    """
    sub_type = details.get("sub_type", "interact")
    target_agent_id = details.get("target_agent_id")
    target_description = details.get("target_description", "another villager") # Fallback description

    target_agent_obj = None # Use a different variable name to avoid confusion with 'target_agent' in outer scope
    if target_agent_id and target_agent_id in all_agents_data:
        target_agent_obj = all_agents_data[target_agent_id]
        # target_description is already set, or defaults to "another villager"
        if not target_description or target_description == "another villager":
             target_description = target_agent_obj.get("name", "another villager")


    if sub_type == "make_statement_to_agent":
        return await _social_make_statement(agent_data, details, target_agent_obj, target_description, full_action_json)
    elif sub_type == "talk_general":
        return await _social_talk_general(agent_data, target_agent_obj, target_description)
    elif sub_type == "propose_new_need":
        return await _social_propose_new_need(agent_data, details, world_data, full_action_json)
    elif sub_type == "give_item_to_agent":
        return await _social_give_item(agent_data, details, target_agent_obj, target_description, world_data)
    elif sub_type == "steal_item_from_agent":
        return await _social_steal_item(agent_data, details, target_agent_obj, target_description, world_data)
    elif sub_type == "propose_trade":
        return await _social_propose_trade(agent_data, details, target_agent_obj, target_description, world_data, all_agents_data)
    elif sub_type == "respond_to_trade":
        return await _social_respond_to_trade(agent_data, details, world_data, all_agents_data)

    return f"{agent_data['name']} attempts to {sub_type.replace('_',' ')} with {target_description}."


async def mock_llm_caller_test(prompt, model_name, temperature):
    """Async mock LLM caller for testing."""
    if "ALLOCATE_PROMPT" in prompt: # Specific check for allocation prompt
        amount_in_prompt = 0
        try: # Attempt to parse amount from a typical allocation prompt structure
            parts = prompt.split("acquired ")[1].split(" ") # Example: "acquired 3 sturdy_branch"
            amount_in_prompt = int(parts[0])
        except Exception: pass # Default to 0 if parsing fails
        k = amount_in_prompt // 2
        v = amount_in_prompt - k
        # Direct JSON string, not nested under "response" for allocation mock
        return json.dumps({"thought": f"Mock allocation: keep {k}, share {v}.", "allocation": {"personal_stash": k, "village_contribution": v }})

    # Fallback for main action decision, ensure it's a string containing JSON, like actual Ollama client.
    mock_action_decision = {"thought": "Mock action from __main__: Decided to rest.", "action_type": "PERSONAL_ACTION", "action_details": {"activity": "rest"}}
    # This structure mimics the real ollama_client.py response which has an outer shell.
    return json.dumps({"model": model_name, "created_at": "mock_time", "response": json.dumps(mock_action_decision), "done": True })

class MockPrompterModuleTest: # Renamed to avoid conflict if prompter.py has same class name
    def generate_resource_allocation_prompt(self, agent, res_type, amount, world): return f"ALLOCATE_PROMPT for {amount} {res_type}"
    def generate_agent_prompt(self, agent, world): return "MAIN_AGENT_PROMPT_MOCK"


async def main_test_logic():
    print("Action Handler - Async Test with Enhanced Craftable Items and Social Actions")

    mock_prompter_instance = MockPrompterModuleTest()

    test_world_main = {
        "day":1, "village_resources": {"food":100, "wood":50, "healing_herbs": 10, "sturdy_branch": 20, "flint_chip":10}, # Added more resources for trade tests
        "active_needs": [], "events_log": [], "pending_trade_proposals": []
    }

    agent_alpha = {"agent_id": "alpha01", "name": "Alpha", "skills": {"thievery":1, "awareness":1}, "status": {"health":100, "hunger":10, "energy":90}, "inventory": {"food_rations": 5}, "personal_resources": {"sturdy_branch": 10, "flint_chip": 5, "healing_herbs": 0}, "memory_log": []}
    agent_beta = {"agent_id": "beta02", "name": "Beta", "skills": {"awareness":2}, "status": {"health":100, "hunger":10, "energy":90}, "inventory": {"stone_axe": 1}, "personal_resources": {"healing_herbs": 5, "sturdy_branch": 0}, "memory_log": []}
    agent_gamma = {"agent_id": "gamma03", "name": "Gamma", "skills": {}, "status": {"health":100, "hunger":10, "energy":90}, "inventory": {}, "personal_resources": {"wood_scraps": 20}, "memory_log": []}

    current_all_agents = {"alpha01": agent_alpha, "beta02": agent_beta, "gamma03": agent_gamma}

    # --- Test Propose Trade ---
    print("\n--- Test Propose Trade ---")
    action_propose = {
        "action_type": "SOCIAL_ACTION", "action_details": {
            "sub_type": "propose_trade", "target_agent_id": "beta02",
            "items_offered": [{"item_id": "sturdy_branch", "quantity": 3}],
            "items_requested": [{"item_id": "healing_herbs", "quantity": 2}]
        }, "speech": "Want to trade, Beta?"
    }
    narration_propose = await execute_action(agent_alpha, action_propose, test_world_main, current_all_agents, mock_llm_caller_test, mock_prompter_instance)
    print(narration_propose)
    assert len(test_world_main['pending_trade_proposals']) == 1, "Proposal not added"
    assert test_world_main['pending_trade_proposals'][0]['proposer_id'] == "alpha01"
    assert test_world_main['pending_trade_proposals'][0]['target_id'] == "beta02"
    print(f"Alpha memory: {agent_alpha['memory_log'][-1]}")
    print(f"Beta memory: {agent_beta['memory_log'][-1]}")
    current_proposal_id = test_world_main['pending_trade_proposals'][0]['proposal_id']

    # --- Test Respond to Trade (Accept Success) ---
    print("\n--- Test Respond to Trade (Accept Success) ---")
    # Reset personal resources for clarity
    agent_alpha['personal_resources']['sturdy_branch'] = 10
    agent_alpha['personal_resources']['healing_herbs'] = 0
    agent_beta['personal_resources']['healing_herbs'] = 5
    agent_beta['personal_resources']['sturdy_branch'] = 0

    action_accept_trade = {
        "action_type": "SOCIAL_ACTION", "action_details": {
            "sub_type": "respond_to_trade", "proposal_id": current_proposal_id, "response": "accept"
        }, "speech": "Sounds like a good deal."
    }
    narration_accept = await execute_action(agent_beta, action_accept_trade, test_world_main, current_all_agents, mock_llm_caller_test, mock_prompter_instance)
    print(narration_accept)
    assert test_world_main['pending_trade_proposals'][0]['status'] == "accepted"
    assert agent_alpha['personal_resources']['sturdy_branch'] == 7, f"Alpha sturdy_branch incorrect: {agent_alpha['personal_resources']['sturdy_branch']}" # Was 10, gave 3
    assert agent_beta['personal_resources']['healing_herbs'] == 3, f"Beta healing_herbs incorrect: {agent_beta['personal_resources']['healing_herbs']}" # Was 5, gave 2
    assert agent_alpha['personal_resources']['healing_herbs'] == 2, f"Alpha healing_herbs received incorrect: {agent_alpha['personal_resources']['healing_herbs']}"# Received 2
    assert agent_beta['personal_resources']['sturdy_branch'] == 3, f"Beta sturdy_branch received incorrect: {agent_beta['personal_resources']['sturdy_branch']}"# Received 3
    print(f"Alpha memory: {agent_alpha['memory_log'][-1]}")
    print(f"Beta memory: {agent_beta['memory_log'][-1]}")

    # --- Test Respond to Trade (Reject) ---
    print("\n--- Test Respond to Trade (Reject) ---")
    test_world_main['pending_trade_proposals'] = []
    agent_alpha['inventory']['food_rations'] = 2
    agent_gamma['personal_resources']['wood_scraps'] = 10
    action_propose_2 = {
        "action_type": "SOCIAL_ACTION", "action_details": {
            "sub_type": "propose_trade", "target_agent_id": "gamma03",
            "items_offered": [{"item_id": "food_rations", "quantity": 1}],
            "items_requested": [{"item_id": "wood_scraps", "quantity": 5}]
        }}
    await execute_action(agent_alpha, action_propose_2, test_world_main, current_all_agents, mock_llm_caller_test, mock_prompter_instance)
    proposal_id_2 = test_world_main['pending_trade_proposals'][0]['proposal_id']
    action_reject_trade = {
        "action_type": "SOCIAL_ACTION", "action_details": {
            "sub_type": "respond_to_trade", "proposal_id": proposal_id_2, "response": "reject"
        }}
    narration_reject = await execute_action(agent_gamma, action_reject_trade, test_world_main, current_all_agents, mock_llm_caller_test, mock_prompter_instance)
    print(narration_reject)
    assert test_world_main['pending_trade_proposals'][0]['status'] == "rejected"
    print(f"Alpha memory: {agent_alpha['memory_log'][-1]}")
    print(f"Gamma memory: {agent_gamma['memory_log'][-1]}")

    # --- Test Respond to Trade (Accept Fails - Responder Missing Items) ---
    print("\n--- Test Respond to Trade (Accept Fails - Responder Missing Items) ---")
    test_world_main['pending_trade_proposals'] = []
    agent_alpha['personal_resources']['flint_chip'] = 5
    agent_beta['inventory']['stone_axe'] = 0 # Beta no longer has the axe
    action_propose_3 = {
        "action_type": "SOCIAL_ACTION", "action_details": {
            "sub_type": "propose_trade", "target_agent_id": "beta02",
            "items_offered": [{"item_id": "flint_chip", "quantity": 2}],
            "items_requested": [{"item_id": "stone_axe", "quantity": 1}]
        }}
    await execute_action(agent_alpha, action_propose_3, test_world_main, current_all_agents, mock_llm_caller_test, mock_prompter_instance)
    proposal_id_3 = test_world_main['pending_trade_proposals'][0]['proposal_id']
    action_accept_fail = {
        "action_type": "SOCIAL_ACTION", "action_details": {
            "sub_type": "respond_to_trade", "proposal_id": proposal_id_3, "response": "accept"
        }}
    narration_accept_fail = await execute_action(agent_beta, action_accept_fail, test_world_main, current_all_agents, mock_llm_caller_test, mock_prompter_instance)
    print(narration_accept_fail)
    assert test_world_main['pending_trade_proposals'][0]['status'] == "failed_items_missing"
    assert "Beta is missing items" in narration_accept_fail
    print(f"Alpha memory: {agent_alpha['memory_log'][-1]}")
    print(f"Beta memory: {agent_beta['memory_log'][-1]}")
    assert agent_alpha['personal_resources']['flint_chip'] == 5
    assert agent_beta['inventory'].get('stone_axe', 0) == 0

    print("\n--- Test Propose Trade (Proposer does not have items) ---")
    action_propose_fail_items = {
        "action_type": "SOCIAL_ACTION", "action_details": {
            "sub_type": "propose_trade", "target_agent_id": "beta02",
            "items_offered": [{"item_id": "non_existent_item", "quantity": 1}],
            "items_requested": [{"item_id": "healing_herbs", "quantity": 1}]
        }}
    narration_propose_fail = await execute_action(agent_alpha, action_propose_fail_items, test_world_main, current_all_agents, mock_llm_caller_test, mock_prompter_instance)
    print(narration_propose_fail)
    assert "didn't have enough" in narration_propose_fail

    # Check that no new proposal was added if the proposer check fails.
    # It's okay if 'pending_trade_proposals' still contains the one from the previous failed_items_missing test.
    # We just need to ensure this specific failure didn't add another one.
    active_pending_proposals_after_fail = [p for p in test_world_main['pending_trade_proposals'] if p['proposer_id'] == 'alpha01' and p['offered_by_proposer'][0]['item_id'] == 'non_existent_item']
    assert len(active_pending_proposals_after_fail) == 0, "A proposal was added even though proposer lacked items."

    agent_beta['inventory']['stone_axe'] = 1 # Restore

if __name__ == '__main__':
    asyncio.run(main_test_logic())
