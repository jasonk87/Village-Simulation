# main.py
# Main entry point for the Primitive Village Simulation

import time
import random 
import json 

import config  
import world_manager
import agent_manager 
import prompter    
import game_utils # Added import
# ollama_client will be imported here if not using mock LLM


def print_header():
    """Prints the game header."""
    print("*" * 50)
    print("      THE PRIMITIVE VILLAGE CHRONICLES")
    print("*" * 50)
    if config.USE_MOCK_LLM:
        print(">>> Using MOCK LLM responses for this simulation. <<<")
    else:
        print(">>> Attempting to use REAL Ollama LLM responses. <<<")
        default_model_name = getattr(config, 'OLLAMA_DEFAULT_MODEL', 'gemma:2b (default)')
        print(f">>> Target Model: {default_model_name} <<<")
    print("-" * 50)

def run_one_simulation_day(world_data, all_agents_data, ollama_call_func_ref=None):
    current_day = world_data["day"]
    print(f"\n\n{'='*15} DAWN OF DAY {current_day} ({world_data['season']}, Weather: {world_data['weather']}) {'='*15}")
    
    world_manager.display_world_status(world_data)

    active_agents_today = [agent for agent_id, agent in all_agents_data.items() if agent.get("status", {}).get("health", 0) > 0]

    if not active_agents_today:
        print("\n\n" + "*"*20 + " THE VILLAGE IS LOST " + "*"*20)
        print("   All have perished. Silence falls upon the clearing.")
        if "events_log" not in world_data: world_data["events_log"] = []
        world_data["events_log"].append("The last survivor has fallen. The village is lost.")
        return False 

    random.shuffle(active_agents_today) 

    for agent_data in active_agents_today:
        # MODIFIED inventory conversion safeguard block
        if not isinstance(agent_data.get("inventory"), dict):
            agent_name = agent_data.get('name', agent_data.get('agent_id', 'Unknown Agent'))
            print(f"  CRITICAL WARNING (run_one_simulation_day): Inventory for {agent_name} is not a dict before turn! Converting.")
            try:
                agent_data["inventory"] = game_utils.convert_inventory_to_dict_format(agent_data.get("inventory", []))
            except Exception as e:
                 print(f"  ERROR: Failed to convert inventory for {agent_name} using game_utils in main.py: {e}. This may cause issues.")
                 agent_data["inventory"] = {} 


        agent_manager.process_agent_turn(
            agent_data, 
            world_data, 
            all_agents_data, 
            prompter_module=prompter, 
            ollama_client_func=ollama_call_func_ref, 
            use_mock_llm=config.USE_MOCK_LLM,
            config_module=config 
        )
        delay_agent_turn = getattr(config, 'DELAY_BETWEEN_AGENT_TURNS', 0.1)
        time.sleep(delay_agent_turn) 

    world_manager.perform_daily_world_update(world_data, all_agents_data) 
    
    return True 


def start_new_game():
    print("\nStarting a new chronicle...")
    
    world_data = world_manager.initialize_new_world()
    num_initial_agents = getattr(config, 'INITIAL_AGENT_COUNT', 5)
    print(f"A band of {num_initial_agents} survivors begins their journey...")
    
    all_agents_data = agent_manager.create_initial_agents(
        num_initial_agents, 
        prompter_module_ref=prompter, 
        config_module_ref=config      
    )
    
    if all_agents_data and hasattr(agent_manager, 'migrate_all_loaded_agents_inventories'):
        agent_manager.migrate_all_loaded_agents_inventories(all_agents_data) 

    return world_data, all_agents_data

def continue_game():
    print("\nResuming the chronicle...")
    save_file_to_load = getattr(config, 'SAVE_GAME_FILE', 'save_game.json') # MODIFIED variable name

    game_state = world_manager.load_game_state() 

    if game_state:
        world_data_loaded = game_state.get("world_data")
        all_agents_data_loaded = game_state.get("all_agents_data")

        if world_data_loaded and all_agents_data_loaded:
            print(f"Successfully loaded game state from {save_file_to_load} (Day {world_data_loaded.get('day', '?')}).")
            if hasattr(agent_manager, 'migrate_all_loaded_agents_inventories'):
                print("Checking and migrating agent inventories from save file...")
                agent_manager.migrate_all_loaded_agents_inventories(all_agents_data_loaded) 
            else:
                print("WARNING: agent_manager.migrate_all_loaded_agents_inventories function not found. Old save files might cause inventory errors.")
            return world_data_loaded, all_agents_data_loaded
        else:
            print(f"Error: Save file {save_file_to_load} is incomplete or corrupted.")
            return None, None 
    else:
        # print(f"No saved game found at {save_file_to_load}.") # Message handled by load_game_state
        # print("ADVICE: Ensure 'SAVE_GAME_FILE' is defined in your config.py (e.g., SAVE_GAME_FILE = \"save_game.json\")") # Corrected variable name
        # print("        and that your world_manager.load_game_state() function uses it.")
        return None, None 

if __name__ == "__main__":
    print_header()
    
    actual_ollama_client_call_model = None
    if not config.USE_MOCK_LLM:
        try:
            import ollama_client 
            actual_ollama_client_call_model = ollama_client.call_model
            print("Successfully imported ollama_client for real LLM calls.")
        except ImportError:
            print("ERROR: Could not import ollama_client.py. Real LLM calls will fail.")
            print("Ensure ollama_client.py is in the same directory and has no errors.")
            print("Falling back to MOCK LLM mode for safety.")
            config.USE_MOCK_LLM = True 
    
    world_data = None
    all_agents_data = None

    world_data, all_agents_data = continue_game()

    if not world_data or not all_agents_data: 
        print("Starting a new game as no valid save was loaded.")
        time.sleep(1)
        world_data, all_agents_data = start_new_game()

    if world_data and all_agents_data:
        sim_days_this_session = getattr(config, 'SIM_DAYS_TO_RUN', 10) 
        start_day_of_session = world_data.get("day", 1)
        target_end_day_for_session = start_day_of_session + sim_days_this_session -1


        while world_data.get("day", 1) <= target_end_day_for_session:
            if not any(agent.get("status", {}).get("health", 0) > 0 for agent_id, agent in all_agents_data.items()):
                print("Village has perished. Ending simulation.")
                break

            day_completed_successfully = run_one_simulation_day( 
                world_data, 
                all_agents_data, 
                ollama_call_func_ref=actual_ollama_client_call_model
            )
            
            if not day_completed_successfully: 
                break 
            
            world_manager.save_game_state(world_data, all_agents_data) 
            
            delay_end_of_day_value = getattr(config, 'DELAY_END_OF_DAY', 0.5)
            time.sleep(delay_end_of_day_value)

            if world_data.get("day", float('inf')) > target_end_day_for_session: 
                print(f"\n--- SIMULATION SESSION ENDED: {sim_days_this_session} days have been simulated in this session (or max day reached). ---")
                break
        
        world_manager.display_simulation_summary(world_data, all_agents_data)
    else:
        print("Critical error: Could not initialize or load game data. Exiting.")

    print("\n--- The Chronicle Ends ---")