I have a folder named whatsapp_web_ui_html that contains a WhatsApp Web UI clone built with HTML and CSS.

I want to integrate this into a Django project.

Here’s what I’m trying to achieve:
	•	I have a model called EventLog that stores event logs in a database table.
	•	This table includes different types of logs:
	•	Events with the name conversation.item.input_audio_transcription.completed contain the transcript of what the user said.
	•	Events with the name response.audio_transcript.done contain the full transcript of the AI’s spoken response.

What I want is to display these conversations inside the WhatsApp UI screen.
	•	Each unique call_session_id in the database represents a different person on the left-hand sidebar, just like a contact in WhatsApp.
	•	When a user clicks on a contact (i.e. a specific call_session_id), the messages in the conversation window should be populated using the logs related to that session, ordered by their database record ID.
	•	This way, we can visually inspect the full conversation between the user and the AI assistant.

This UI will be served through a view function inside the voice_assistant Django app.

When a user navigates to the URL /call-conversation/{CALL_SESSION_ID}, the controller should:
	•	Use the call_session_id from the URL to query the database,
	•	Dynamically render the conversation inside the HTML (instead of the current mock data),
	•	And return the rendered page.

Currently, html file includes mock data for demo. Please remove it and put necessary dynamic fields.

Start the implementation!