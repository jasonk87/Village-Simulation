print("Attempting to import config...")
import config
print("Successfully imported config.")

print("Attempting to import game_utils...")
import game_utils
print("Successfully imported game_utils.")

print("Attempting to import prompter...")
import prompter
print("Successfully imported prompter.")

# Deferring agent_manager and world_manager as they might have more complex imports or top-level code

print("Minimal import test script finished.")
