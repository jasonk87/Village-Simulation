import random # Though not strictly needed for this step if personalities are hardcoded for tests

# --- Relationship Score Constants ---
RELATIONSHIP_SCORE_MAX = 10
RELATIONSHIP_SCORE_MIN = -10
RELATIONSHIP_SCORE_NEUTRAL = 0
DEFAULT_RELATIONSHIP_SCORE_CHANGE_POSITIVE = 1
DEFAULT_RELATIONSHIP_SCORE_CHANGE_NEGATIVE = -1
STRONG_RELATIONSHIP_SCORE_CHANGE_POSITIVE = 3
STRONG_RELATIONSHIP_SCORE_CHANGE_NEGATIVE = -3

# --- Interaction Type Constants ---
INTERACTION_TYPE_I_TALKED_TO_THEM = "I_TALKED_TO_THEM"
INTERACTION_TYPE_TALKED_TO_BY_ME = "TALKED_TO_BY_ME"
INTERACTION_TYPE_I_IGNORED_THEM = "I_IGNORED_THEM"
INTERACTION_TYPE_IGNORED_ME = "IGNORED_ME"
INTERACTION_TYPE_I_FLED_FROM_THEM = "I_FLED_FROM_THEM"
INTERACTION_TYPE_FLED_FROM_ME = "FLED_FROM_ME"
INTERACTION_TYPE_I_THREATENED_THEM = "I_THREATENED_THEM"
INTERACTION_TYPE_THREATENED_ME = "THREATENED_ME"
INTERACTION_TYPE_I_OFFERED_GIFT_TO_THEM = "I_OFFERED_GIFT_TO_THEM"
INTERACTION_TYPE_OFFERED_GIFT_TO_ME = "OFFERED_GIFT_TO_ME"
INTERACTION_TYPE_I_ASKED_FOR_HELP_FROM_THEM = "I_ASKED_FOR_HELP_FROM_THEM"
INTERACTION_TYPE_ASKED_FOR_HELP_FROM_ME = "ASKED_FOR_HELP_FROM_ME"
# From ascii_game.py, ensure all are here
INTERACTION_TYPE_DIALOGUE_EXCHANGE = "DIALOGUE_EXCHANGE"


NPC_POSSIBLE_PERSONALITIES = ["friendly", "neutral", "gruff", "timid", "suspicious"] # For NpcTest init

class NpcTest:
    def __init__(self, id, personality=None):
        self.id = id
        if personality:
            self.personality = personality
        else:
            self.personality = random.choice(NPC_POSSIBLE_PERSONALITIES)
        self.relationships = {}

    def get_or_initialize_relationship(self, target_npc_id):
        if target_npc_id not in self.relationships:
            self.relationships[target_npc_id] = {
                'score': RELATIONSHIP_SCORE_NEUTRAL,
                'last_interaction_type': None,
                'interaction_count': 0
            }
        # Ensure structure for potentially older "saves" if this were a real game,
        # but for this test script, new entries will always have all fields.
        if 'interaction_count' not in self.relationships[target_npc_id]:
             self.relationships[target_npc_id]['interaction_count'] = 0
        if 'last_interaction_type' not in self.relationships[target_npc_id]:
             self.relationships[target_npc_id]['last_interaction_type'] = None
        return self.relationships[target_npc_id]

    def update_relationship_towards(self, target_npc_id, score_change, interaction_type_string):
        rel = self.get_or_initialize_relationship(target_npc_id)

        # Store old score for logging before updating
        # old_score = rel['score'] # This line was for logging within the method, not needed here
                                 # if logging is done after calling the method.

        new_score = rel['score'] + score_change
        rel['score'] = max(RELATIONSHIP_SCORE_MIN, min(RELATIONSHIP_SCORE_MAX, new_score))
        rel['last_interaction_type'] = interaction_type_string
        rel['interaction_count'] += 1
        # Logging of the update will be done in the test scenario part of the script.

    def __str__(self):
        return f"NPC {self.id} (Personality: {self.personality}, Relationships: {self.relationships})"

if __name__ == "__main__":
    # Test scenarios will be added in the next step
    print("test_relationships.py: Minimal NpcTest class and constants defined.")
    npc1 = NpcTest(id=1, personality="friendly")
    npc2 = NpcTest(id=2, personality="gruff")
    print(npc1)
    print(npc2)
