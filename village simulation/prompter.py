import json
import random # For selecting examples if needed
import config # To access CRAFTABLE_ITEMS and GATHERABLE_PERSONAL_RESOURCES

def format_inventory_for_prompt(inventory_dict, personal_resources_dict):
    """Formats both inventory (tools/items) and personal resources for the prompt."""
    items_str_parts = []

    # Crafted items/tools from inventory (which is a dict: {"item_id": count})
    if inventory_dict:
        crafted_items = []
        for item_id, quantity in inventory_dict.items():
            if quantity > 0:
                # Get readable name from config if available, otherwise format item_id
                item_name_cfg = config.CRAFTABLE_ITEMS.get(item_id, {})
                readable_name = item_name_cfg.get("name", item_id.replace('_', ' ').capitalize())
                crafted_items.append(f"{readable_name} (x{quantity})")
        if crafted_items:
            items_str_parts.append(f"Tools/Crafted Items: {', '.join(crafted_items)}")

    # Raw personal resources
    if personal_resources_dict:
        raw_resources = []
        for res_key, quantity in personal_resources_dict.items():
            if quantity > 0:
                 raw_resources.append(f"{res_key.replace('_',' ').capitalize()} (x{quantity})")
        if raw_resources:
            items_str_parts.append(f"Raw Materials: {', '.join(raw_resources)}")

    return "; ".join(items_str_parts) if items_str_parts else "nothing"

def get_shelter_description_for_prompt(shelter_level):
    if shelter_level == 0: return "exposed to the elements"
    if shelter_level == 1: return "a crude lean-to"
    if shelter_level == 2: return "a basic hut"
    if shelter_level == 3: return "a sturdy hut"
    if shelter_level >= 4: return "a well-built dwelling"
    return "an unknown shelter"


def generate_agent_prompt(agent_data, world_state):
    hunger_status_text = ""
    if agent_data['status']['hunger'] > 80: hunger_status_text = "You are STARVING."
    elif agent_data['status']['hunger'] > 50: hunger_status_text = "You are VERY HUNGRY."
    elif agent_data['status']['hunger'] > 20: hunger_status_text = "You are feeling peckish."

    energy_status_text = ""
    if agent_data['status']['energy'] < 20: energy_status_text = "You are EXHAUSTED."
    elif agent_data['status']['energy'] < 50: energy_status_text = "You are FATIGUED."

    health_status_text = ""
    if agent_data['status']['health'] < 30: health_status_text = "You are CRITICALLY INJURED."
    elif agent_data['status']['health'] < 70: health_status_text = "You are injured."

    current_shelter_level = agent_data.get('shelter_level', 0)
    shelter_desc_for_prompt = get_shelter_description_for_prompt(current_shelter_level)

    prompt = (
        f"You are {agent_data['name']}, a {agent_data['background']}. "
        f"This is a desperate fight for survival in a harsh, unforgiving world. Every decision matters. "
        f"Failure to secure resources or protect yourself could mean death. "
        f"{hunger_status_text} {energy_status_text} {health_status_text} "
        f"Your current shelter is {shelter_desc_for_prompt}. "
        f"Your personality traits are: {', '.join(agent_data.get('personality_traits',[]))}. "
        f"Remember these traits and your dire situation when deciding your actions and speech.\n"
    )

    prompt += f"\nIt is Day {world_state['day']}, the weather is {world_state['weather']} during the {world_state['season']}."
    prompt += f"\nYour current raw status: Health {agent_data['status']['health']}/100, Hunger {agent_data['status']['hunger']}/100, Energy {agent_data['status']['energy']}/100."

    skill_strings = []
    for skill, value in agent_data.get('skills', {}).items():
        skill_strings.append(f"{skill.capitalize()}: {value}/{config.MAX_SKILL_LEVEL}")
    prompt += f"\nYour skills: {', '.join(skill_strings) if skill_strings else 'None listed'}."

    prompt += f"\nYour personal inventory & resources: {format_inventory_for_prompt(agent_data.get('inventory', {}), agent_data.get('personal_resources', {}))}."
    prompt += f"\nYour current shelter level: {current_shelter_level} ({shelter_desc_for_prompt})."

    if agent_data.get('memory_log'):
        # First, extract any recent messages from memory log
        recent_messages = [m for m in agent_data['memory_log'][-5:] if "said to you:" in m or "You said to" in m]
        other_memories = [m for m in agent_data['memory_log'][-3:] if "said to you:" not in m and "You said to" not in m]

        # Show messages first for emphasis
        if recent_messages:
            prompt += f"\nRecent conversations:\n  " + "\n  ".join(recent_messages)

        # Show other memories
        if other_memories:
            prompt += f"\nOther recent memories: {' | '.join(other_memories)}"
    else:
        prompt += "\nRecent memories: None yet."

    prompt += "\n\nVillage Overview:"
    village_res_list = []
    for res, quant in world_state['village_resources'].items():
        if quant > 0 :
             village_res_list.append(f"{res.replace('_',' ').capitalize()}: {quant}")
    prompt += f"\n  Communal Resources: {', '.join(village_res_list) if village_res_list else 'None available'}"

    prompt += "\n  Active Village Needs:"
    if not world_state['active_needs']:
        prompt += "\n    - No pressing needs currently identified."
    else:
        for i, need in enumerate(world_state['active_needs']):
            assigned_count = len(need.get('assigned_agents', []))
            progress_percent = need.get('progress', 0.0) * 100
            req_mats_str = ""
            if need.get("required_materials"):
                mats = [f"{k.replace('_',' ')}: {v}" for k,v in need["required_materials"].items()]
                req_mats_str = f" (Needs: {', '.join(mats)})"
            prompt += f"\n    {i+1}. ID: {need['need_id']} - {need['description']} (Urgency: {need['urgency']}, Progress: {progress_percent:.0f}%, Assigned: {assigned_count}){req_mats_str}"

    prompt += "\n\nRecent Happenings in the World:"
    recent_events = world_state.get('events_log', [])[-3:] # Get last 3 events
    if recent_events:
        for event_entry in recent_events:
            prompt += f"\n  - {event_entry}"
    else:
        prompt += "\n  - The days have been uneventful."

    prompt += "\n\nBeyond the immediate needs, what long-term improvements or goals could benefit you or the village? (e.g., better tools, more secure food sources, improved defenses, new discoveries). Consider these in your thought process."

    # Hinting at available actions based on config
    prompt += "\n\n--- Consider Your Options ---"
    prompt += "\nAvailable Craftable Items (if you have materials & skill):"
    craftable_examples = []
    # Show up to 3 examples, prioritizing items the agent might actually be able to craft or find useful
    # This could be made smarter by checking agent's current resources against recipes
    shown_craft_examples = 0
    for item_id, item_def in config.CRAFTABLE_ITEMS.items():
        if shown_craft_examples >= 3:
            break
        recipe_str = ", ".join([f"{count} {mat.replace('_',' ')}" for mat, count in item_def['recipe'].items()])
        craftable_examples.append(f"- {item_def['name']} (ID: {item_id}): Needs {recipe_str}. Skill: {item_def['skill_required']} Lvl {item_def['min_skill_level']}. Desc: {item_def['description']}")
        shown_craft_examples +=1

    if craftable_examples:
        prompt += "\n" + "\n".join(craftable_examples)
    else:
        prompt += "\n  (No specific craftable items defined in config for examples right now)."

    prompt += "\n\nPossible Personal Resources to Gather (check your skills):"
    gatherable_examples = []
    shown_gather_examples = 0
    for res_id, res_def in config.GATHERABLE_PERSONAL_RESOURCES.items():
        if shown_gather_examples >= 3:
            break
        gatherable_examples.append(f"- {res_id.replace('_',' ').capitalize()} (ID: {res_id}): Uses '{res_def['skill']}' skill.")
        shown_gather_examples += 1
    if gatherable_examples:
        prompt += "\n" + "\n".join(gatherable_examples)
    else:
        prompt += "\n  (No specific gatherable resources defined in config for examples right now)."

    # Remind about tool use
    if agent_data.get("inventory", {}).get("stone_axe", 0) > 0: # Check quantity
        prompt += "\nREMINDER: You have a Stone Axe, which is good for gathering wood!"
    if agent_data.get("inventory", {}).get("flint_knife", 0) > 0:
        prompt += "\nREMINDER: You have a Flint Knife, useful for gathering herbs or skinning."
    # Add more reminders for other tools if present.

    prompt += """

What is your primary thought process, and what single action will you attempt today?
Consider your traits, skills, status, personal inventory/resources, shelter, communal resources, and the village's needs.
If you are hungry, tired, or injured, address those needs first. If your shelter is poor, consider improving it.

Possible action_types: ADDRESS_NEED, PERSONAL_ACTION, SOCIAL_ACTION.

Respond ONLY in JSON format like this:
{
  "thought": "My reasoning for the action, reflecting my current state, traits, and available options...",
  "action_type": "ACTION_TYPE_HERE",
  "action_details": { /* specific details for the action, see examples */ },
  "speech": "Optional: anything I say to others, reflecting my current mood and situation."
}

--- DETAILED ACTION EXAMPLES ---

PERSONAL_ACTION - Craft Item:
{
  "thought": "I need a tool. I have the materials for a Stone Axe (1 sturdy_branch, 1 sharpened_stone, 1 vine_rope) and my crafting skill is adequate. The recipe for stone_axe is: sturdy_branch: 1, sharpened_stone: 1, vine_rope: 1.",
  "action_type": "PERSONAL_ACTION",
  "action_details": {
    "activity": "craft_item",
    "item_id": "stone_axe" /* Use EXACT item_id from config. 'stone_axe' is valid and craftable. */
  }, "speech": "I will try to make an axe."
}

PERSONAL_ACTION - Gather Personal Resource:
{
  "thought": "I need some sturdy branches for crafting or shelter. My gathering skill should be enough.",
  "action_type": "PERSONAL_ACTION",
  "action_details": {
    "activity": "gather_resource",
    "resource_id": "sturdy_branch" /* Use EXACT resource_id from config. 'sturdy_branch' is valid and gatherable. */
  }, "speech": "Looking for some good branches."
}

PERSONAL_ACTION - Eat from Inventory (Crafted Consumable or Basic Ration):
{
  "thought": "I'm very hungry and have 'food_rations' in my inventory. I must eat one.",
  "action_type": "PERSONAL_ACTION",
  "action_details": {
    "activity": "eat_from_inventory",
    "consume_item": "food_rations", /* item_id from your inventory. 'food_rations' is a valid default initial inventory item. */
    "amount": 1
  }, "speech": ""
}

PERSONAL_ACTION - Upgrade Shelter:
{
  "thought": "My current shelter (level 0) is just exposed ground. I need at least a lean-to (level 1). I should check if I have materials like wood scraps and herbs bundle from my personal resources.",
  "action_type": "PERSONAL_ACTION",
  "action_details": {
    "activity": "upgrade_shelter", /* This activity is handled by agent_manager.py's old shelter logic */
    "target_shelter_level": 1
  },
  "speech": "I need to build some basic shelter."
}

PERSONAL_ACTION - Rest:
{
  "thought": "I'm exhausted. I must rest to regain energy.",
  "action_type": "PERSONAL_ACTION",
  "action_details": {"activity": "rest"},
  "speech": "Need to rest for a bit."
}

ADDRESS_NEED - Contributing to a Village Need:
(If gathering resources for a need, the allocation of those resources will be decided in a separate step if successful.)
{
  "thought": "The village desperately needs food (N_Sys_001). My gathering skill is decent. I'll try to find edible plants.",
  "action_type": "ADDRESS_NEED",
  "action_details": {
    "need_id": "N_Sys_001", /* Exact ID of the need. 'N_Sys_001' is a valid initial need. */
    "activity_description": "Forage for edible plants and roots for the village stockpile.", /* What you are doing for the need */
    "expected_contribution_skill": "gathering" /* Skill you are using */
  },
  "speech": "I'll search for food for everyone."
}

ADDRESS_NEED - Using a tool (e.g. Stone Axe for a wood-related need):
{
  "thought": "Need ID N_Sys_002 requires wood. I have a stone_axe which will help me gather wood more effectively.",
  "action_type": "ADDRESS_NEED",
  "action_details": {
    "need_id": "N_Sys_002", /* 'N_Sys_002' is a valid initial need. */
    "activity_description": "Gather wood using my stone_axe for the village shelters.",
    "expected_contribution_skill": "gathering" /* Or a more specific skill like 'woodcutting' if defined and relevant. 'stone_axe' is craftable. */
  },
  "speech": "I'll use my axe to get wood for the shelters!"
}

SOCIAL_ACTION - Propose New Need:
{
  "thought": "The village defenses are weak. We should build a simple palisade. I'll suggest it.",
  "action_type": "SOCIAL_ACTION",
  "action_details": {
    "sub_type": "propose_new_need",
    "need_description": "Build a simple defensive palisade around the camp.",
    "related_skills": ["building", "woodcutting"], /* Skills involved */
    "urgency": "medium"
  },
  "speech": "Friends, I think we need to build a wall for safety!"
}

SOCIAL_ACTION - Make Statement to Agent:
{
  "thought": "Gorok looks worried and tired. As someone who knows about herbs, I should suggest they try some healing tea.",
  "action_type": "SOCIAL_ACTION",
  "action_details": {
    "sub_type": "make_statement_to_agent",
    "target_agent_id": "agent_005", /* ID of the agent to talk to */
    "target_description": "Gorok", /* Used if agent_id is unknown or invalid */
    "statement_content": "You look exhausted. I know a recipe for healing tea if you'd like to try it." /* Optional, can use speech field instead */
  },
  "speech": "You look exhausted. I know a recipe for healing tea if you'd like to try it."
}
"""
    return prompt

def generate_resource_allocation_prompt(agent_data, newly_acquired_resource_type, newly_acquired_amount, world_state): # Added world_state
    """Generates the prompt for an agent to decide on resource allocation."""
    hunger_status_text = "You are hungry." if agent_data['status']['hunger'] > 50 else "Your hunger is manageable."

    # Village resource status to help LLM make informed decision
    village_food_status = world_state['village_resources'].get('food', 0)
    village_wood_status = world_state['village_resources'].get('wood', 0)
    # Add other key village resources if relevant to the type of resource acquired

    prompt = (
        f"You are {agent_data['name']}. Traits: {', '.join(agent_data.get('personality_traits',[]))}. "
        f"Remember, this is a fight for survival. {hunger_status_text}\n"
    )

    prompt += f"\nYou just successfully acquired {newly_acquired_amount} {newly_acquired_resource_type.replace('_', ' ')}."
    prompt += f"\nYour current personal inventory & resources: {format_inventory_for_prompt(agent_data.get('inventory', {}), agent_data.get('personal_resources',{}))}."
    prompt += f"\nYour current hunger: {agent_data['status']['hunger']}/100, energy: {agent_data['status']['energy']}/100."
    prompt += f"\nVillage stockpiles relevant to this resource: Food: {village_food_status}, Wood: {village_wood_status}."

    prompt += f"""

How do you want to allocate these newly acquired {newly_acquired_resource_type.replace('_',' ')}?
Consider your personality (e.g., 'greedy', 'generous', 'selfish', 'pragmatic'), your personal needs (hunger, materials for crafting), and the village's current resource levels.

Respond ONLY in JSON format with the following keys:
{{
  "thought": "Your reasoning for this allocation, reflecting your traits, personal needs, and awareness of village supplies.",
  "allocation": {{
    "personal_stash": How_many_units_to_keep_for_yourself, /* goes into your personal_resources */
    "village_contribution": How_many_units_to_contribute_to_the_communal_stockpile /* goes to village_resources */
  }}
}}

Ensure 'personal_stash' + 'village_contribution' equals the total amount acquired ({newly_acquired_amount}).
Example (if generous, acquired 3 food, and village food is low):
{{
  "thought": "The village is very low on food, and I only got a little. They need this more than I do right now.",
  "allocation": {{ "personal_stash": 0, "village_contribution": 3 }}
}}
Example (if selfish/desperate and acquired 3 wood, and you need it for a personal axe):
{{
  "thought": "I need this wood to craft an axe for myself. The village has some wood already.",
  "allocation": {{ "personal_stash": 3, "village_contribution": 0 }}
}}
"""
    return prompt

if __name__ == '__main__':
    # Updated sample agent to reflect new inventory/resource structure
    sample_agent_data = {
        "agent_id": "A001", "name": "Elara", "background": "Exiled Herbalist's Apprentice",
        "personality_traits": ["cautious", "observant", "generous", "desperate"],
        "skills": {"hunting": 1, "gathering": 4, "building": 1, "crafting": 3, "healing": 3, "social": 2, "fighting": 1},
        "status": {"health": 60, "hunger": 70, "energy": 40},
        "inventory": {"flint_chip": 1, "food_rations": 1}, # Agent has 1 food_ration
        "personal_resources": {"sturdy_branch": 2, "healing_herbs": 5, "vine_rope": 1},
        "shelter_level": 0,
        "current_focus_need_id": None,
        "memory_log": ["Woke up shivering.", "Saw Gorok looking strong."]
    }
    sample_world_state = {
        "day": 5, "season": "Spring", "weather": "Cold Rain",
        "village_resources": {"food": 20, "wood": 30, "stone": 10, "herbs":5, "healing_herbs": 3, "sturdy_branch": 5},
        "active_needs": [{
            "need_id": "N_Sys_001", "description": "CRITICAL: Find food before we starve!",
            "urgency": "critical", "related_skills": ["gathering", "hunting"], "progress": 0.0,
            "assigned_agents": []
            },
            {
            "need_id": "N_Sys_002", "description": "Improve shelters",
            "urgency": "high", "related_skills": ["building", "crafting"], "progress": 0.1,
            "required_materials": {"wood": 10, "vine_rope": 2},
            "assigned_agents": ["A002"]
            }
            ],
        "events_log": ["A wolf was heard howling nearby last night.", "The river seems higher than usual.", "A strange bird was seen flying south."]
    }
    print("--- Example Main Agent Prompt (Precision Focus with Shelter Example) ---")
    # print(generate_agent_prompt(sample_agent_data, sample_world_state)) # Original print

    # Test assertions for new prompt sections
    generated_prompt_output = generate_agent_prompt(sample_agent_data, sample_world_state)
    print(generated_prompt_output) # Print the prompt so it's visible in output

    assert "Recent Happenings in the World:" in generated_prompt_output, "Test Failed: 'Recent Happenings' section missing."
    # Check for one of the specific events from the sample data
    assert sample_world_state['events_log'][0] in generated_prompt_output, f"Test Failed: Sample event '{sample_world_state['events_log'][0]}' missing."
    # If events_log could be shorter than 3, this assertion might need to be more robust
    # For now, sample_world_state['events_log'] has 3 items, so [-3:] will include the first one.

    assert "Beyond the immediate needs, what long-term improvements or goals could benefit you or the village?" in generated_prompt_output, "Test Failed: Long-term goal encouragement missing."

    print("\n\nSUCCESS: Prompt content assertions passed!")

    print("\n--- Example Resource Allocation Prompt (Precision Focus) ---")
    print(generate_resource_allocation_prompt(sample_agent_data, "sturdy_branch", 3, sample_world_state))
