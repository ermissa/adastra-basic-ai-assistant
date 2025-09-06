import copy
from dataclasses import dataclass
from typing import Optional


# A dataclass representing a single state in a conversation flow (FSM).
@dataclass
class ConversationState:
    name: str  # Unique name/identifier for this state
    prompt_en: str  # Prompt to be used by the assistant at this state (can contain placeholders)
    prompt_tr: str  # Prompt to be used by the assistant at this state (can contain placeholders)
    prompt_du: str  # Prompt to be used by the assistant at this state (can contain placeholders)
    tools: list[dict]  # List of function tools available at this state (OpenAI tool-calling format)
    next_states: Optional[dict[str, str]] = None  # Mapping of expected responses to the next state names
    previous_state: Optional[str] = None  # Optional pointer to the previous state
    fallback_state: Optional[str] = None  # Optional fallback state if verification fails or unexpected input occurs
    verify_from_func: Optional[dict] = None  # Optional dictionary of verification functions
    is_build: bool = False  # Internal flag to ensure state is only built once
    lang: str = 'tr'

    @property
    def prompt(self):
        if self.lang=='en':
            return self.prompt_en
        elif self.lang=='tr':
            return self.prompt_tr
        return self.prompt_du
    # Builds and returns a new instance of this state with dynamic values injected into prompt/tool descriptions

    def build_state(self, dynamic_parameters: dict, lang):
        self.__setattr__('lang', lang)

        # Format the prompt with dynamic runtime values (e.g., user_name, location)
        # print("old prompt", self.prompt)
        new_prompt = self.prompt.format(**dynamic_parameters)
        # print("new prompt", new_prompt)

        # Deep copy tools so original list isn't mutated
        new_tools = copy.deepcopy(self.tools)
        # Inject dynamic values into tool descriptions and their parameter descriptions
        for tool in new_tools:
            tool["description"] = tool["description"].format(**dynamic_parameters)
            # print("current_tool", tool)
            for property in tool["parameters"]["properties"].values():
                property["description"] = property.get("description", "").format(**dynamic_parameters)
                # print("new description", property["description"])
    
        return self.__class__(
            name=self.name,
            prompt_en=new_prompt if lang=='en' else self.prompt_en,
            prompt_tr=new_prompt if lang=='tr' else self.prompt_tr,
            prompt_du=new_prompt if lang=='du' else self.prompt_du,
            tools=new_tools,
            next_states=self.next_states,
            previous_state=self.previous_state,
            fallback_state=self.fallback_state,
            verify_from_func=self.verify_from_func,
            is_build=False,  # Allow rebuilding when needed
            lang=lang
        )
