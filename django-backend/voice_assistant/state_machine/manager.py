from voice_assistant.state_machine.fsm import ConversationFSM
from voice_assistant.state_machine.order_flow import order_flow_states

fsm_instances = {}


def get_fsm_for_call(call_sid: str) -> ConversationFSM:
    if call_sid not in fsm_instances:
        fsm_instances[call_sid] = ConversationFSM(order_flow_states, initial_state="ask_item")
    return fsm_instances[call_sid]
