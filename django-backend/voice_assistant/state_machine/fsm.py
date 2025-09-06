from voice_assistant.state_machine.states import ConversationState


class ConversationFSM:
    def __init__(self, states: dict[str, ConversationState], initial_state: str, collected_info: dict):
        self.states = states
        self.current_state = initial_state
        self.collected_info = collected_info
        self.lang = None

    def get_current(self) -> ConversationState:
        return self.states[self.current_state].build_state(self.collected_info.get("params", {}), self.lang)

    def advance(self, condition: str= '', new_state: str = None):
        state = self.get_current()
        if state.verify_from_func is None and condition not in state.next_states:
            raise ValueError(f"Invalid transition for condition: {condition}")
        
        print("advance with", condition, new_state)
        if state.verify_from_func is not None:
            self.current_state = new_state
            return 
        self.current_state = state.next_states[condition]

    def go_back(self):
        self.current_state = self.get_current().previous_state or self.current_state

    def fallback(self):
        self.current_state = self.get_current().fallback_state or self.current_state
    
    def set_lang(self, lang):
        self.lang = lang
        # Force rebuild of current state with new language
        if self.current_state in self.states:
            # Reset the state to allow rebuilding
            self.states[self.current_state].is_build = False
