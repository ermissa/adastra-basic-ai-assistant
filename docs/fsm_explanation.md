# Voice Assistant FSM (Finite State Machine) Explanation

This document explains how the Finite State Machine (FSM) is implemented and operates in the voice assistant order flow for Pizzadam.

## What is the FSM?

The FSM (Finite State Machine) is a structured way to manage the conversation flow between the user and the voice assistant. Each **state** represents a step in the dialog, and transitions between states are determined by user input, tool outputs, or validation functions.

---

## How the FSM Works

### 1. **States**
- Each state represents a specific point in the conversation (e.g., greeting, asking for delivery type, confirming order).
- States are defined as instances of `ConversationState` in a dictionary (e.g., `order_flow_states`).
- Each state has:
  - A **name**
  - A **prompt** (what the assistant says)
  - A list of **tools** (functions to process/validate user input)
  - A way to determine the **next state** (either direct mapping or via a validation function)

### 2. **Prompts**
- The prompt is the message spoken to the user at each state.
- Example: `"Will you pick it up or should we deliver it?"`

### 3. **Tools**
- Tools are function-like objects that process user input and extract/validate information (e.g., intent, address, order items).
- Each state specifies which tool(s) to use.
- Tool output is used to determine the next state.

### 4. **State Transitions**
- Transitions are defined in two ways:
  - **Direct Mapping:** The tool output directly maps to the next state (e.g., yes/no, pickup/delivery).
  - **Validation Function:** A function checks the tool output and returns a result (e.g., is the address valid?), which determines the next state.
- The FSM moves from one state to another based on these transitions, guiding the conversation logically.

---

## Example Flow

1. **Entry State**
   - Prompt: Welcome message
   - Tool: Intent chooser
   - Next: Pickup/Delivery or Status Check

2. **Pickup or Delivery**
   - Prompt: Pickup or delivery?
   - Tool: Delivery type chooser
   - Next: Confirm branch (pickup) or Ask address (delivery)

3. **Ask Address**
   - Prompt: Ask for address
   - Tool: Address extractor
   - Next: Confirm address (if valid) or Ask address failed (if invalid)

4. **Confirm Address**
   - Prompt: Confirm the extracted address
   - Tool: Yes/No confirmation
   - Next: Ask item (if yes) or Ask address failed (if no)

5. **Ask Item**
   - Prompt: What would you like to order?
   - Tool: Order item extractor
   - Next: Ask size (if valid) or Entry (if invalid)

6. **Ask Size**
   - Prompt: Specify pizza sizes
   - Tool: Size extractor
   - Next: Confirm order (if valid) or Ask size failed (if invalid)

7. **Confirm Order**
   - Prompt: Confirm the order
   - Tool: Yes/No confirmation
   - Next: End call (if confirmed) or Ask item (if not)

8. **End Call**
   - Prompt: Thank you message
   - Tool: End call
   - Next: Conversation ends

---

## Key Points
- The FSM ensures a logical, step-by-step conversation.
- Each state is responsible for a single dialog action.
- Tools process and validate user input at each step.
- Transitions are clear and deterministic, making the flow easy to follow and extend.

---

For more details, see the implementation in `order_flow.py` and the tool definitions in `conversation_openai_tools.py`. 