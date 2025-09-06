// Import required modules
import fastifyFormBody from '@fastify/formbody';
import fastifyWs from '@fastify/websocket';
import dotenv from 'dotenv';
import Fastify from 'fastify';
import fetch from 'node-fetch';
import Twilio from 'twilio';
import WebSocket from 'ws';
import { SYSTEM_MESSAGE } from './prompt.js'; // Import the prompt

// Load environment variables from .env file
dotenv.config();

// Retrieve the OpenAI API key and Twilio credentials from environment variables
const { OPENAI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER } = process.env;

// Check if required credentials are missing
if (!OPENAI_API_KEY || !TWILIO_ACCOUNT_SID || !TWILIO_AUTH_TOKEN || !TWILIO_NUMBER) {
    console.error('Missing environment variables. Please set them in the .env file.');
    process.exit(1);
}

// Initialize Fastify server and Twilio client
const fastify = Fastify();
fastify.register(fastifyFormBody);
fastify.register(fastifyWs);
const twilioClient = Twilio(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN);

// Some default constants used throughout the application
const VOICE = 'sage';
const HOST = '0.0.0.0';
const PORT = process.env.PORT || 5050;
const TRANSCRIPT_WEBHOOK_URL = "<url>";
const BOOKING_WEBHOOK_URL = "https://hook.eu2.make.com/s2i4ntg7acs38vv1axe2fnt3zow623cq";


// Session management: Store session data for ongoing calls
const sessions = new Map();

// Event types to log to the console for debugging purposes
const LOG_EVENT_TYPES = [
    'response.content.done',
    'rate_limits.updated',
    'response.done',
    'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started',
    'session.created',
    'response.text.done',
    'conversation.item.input_audio_transcription.completed'
];

// Helper function to end the call using Twilio
async function endCall(callSid) {
    try {
        await twilioClient.calls(callSid).update({ status: 'completed' });
        console.log(`Call ${callSid} has been ended successfully.`);
    } catch (error) {
        console.error('Error ending the call:', error);
    }
}

// Root route - just for checking if the server is running
fastify.get('/', async (request, reply) => {
    reply.send({ message: 'Twilio Media Stream Server is running!' });
});

// Route for outbound calls from Make.com
fastify.post('/outgoing-call', async (request, reply) => {
    const { firstMessage, number } = request.body;
    console.log(`Initiating outbound call to ${number} with message: ${firstMessage}`);

    try {
        const call = await twilioClient.calls.create({
            from: TWILIO_NUMBER,
            to: number,
            url: `https://${request.headers.host}/outgoing-call-twiml?firstMessage=${encodeURIComponent(firstMessage)}&number=${encodeURIComponent(number)}`
        });
        reply.send({ message: 'Call initiated', callSid: call.sid });
    } catch (error) {
        console.error('Error initiating outbound call:', error);
        reply.status(500).send({ error: 'Failed to initiate call' });
    }
});

const firstMessage = "You are calling the customer Zafer, who has just submitted a form to be contacted about a batarya degisimi. The next availability is Monday 17th March at 9AM. As if they are happy with this time, or if they want to propose another time. You will book in the slot while on the call, so after it is booked in confirm with the customer that it is booked in and that they will receive an SMS reminder closer to the date. Ok, the call is starting now, make sure to introduce yourself as Sophie from Bart's automative, state the purpose of your call, and remember, your primary objective is to schedule them in. Begin your conversation now."

fastify.post('/incoming-call', async (request, reply) => {
    console.log('Incoming call received');

    const twimlResponse = `<?xml version="1.0" encoding="UTF-8"?>
                            <Response>
                              <Connect>
                                  <Stream url="wss://${request.headers.host}/media-stream">
                                      <Parameter name="firstMessage" value="${firstMessage}" />
                                      <Parameter name="callerNumber" value="${request.body.From}" />
                                  </Stream>
                              </Connect>
                            </Response>`;
    reply.type('text/xml').send(twimlResponse);
});


// // TwiML for outgoing calls
fastify.all('/outgoing-call-twiml', async (request, reply) => {
    const firstMessage = request.query.firstMessage || 'Hi, how are you?';
    const number = request.query.number || 'Unknown';
    console.log(`First Message: ${firstMessage}`);

    const twimlResponse = `<?xml version="1.0" encoding="UTF-8"?>
                            <Response>
                              <Connect>
                                  <Stream url="wss://${request.headers.host}/media-stream">
                                      <Parameter name="firstMessage" value="${firstMessage}" />
                                      <Parameter name="callerNumber" value="${number}" />
                                  </Stream>
                              </Connect>
                          </Response>`;

    reply.type('text/xml').send(twimlResponse);
});

// WebSocket route to handle the media stream for real-time interaction
fastify.register(async (fastify) => {
    fastify.get('/media-stream', { websocket: true }, (connection, req) => {
        console.log('Client connected to media-stream');

        let firstMessage = '';
        let streamSid = '';
        let openAiWsReady = false;
        let queuedFirstMessage = null;
        let callSid = req.headers['x-twilio-call-sid'] || `session_${Date.now()}`;

        // Use Twilio's CallSid as the session ID
        const sessionId = callSid;
        let session = sessions.get(sessionId) || { transcript: '', streamSid: null };
        sessions.set(sessionId, session);

        // Open a WebSocket connection to the OpenAI Realtime API
        const openAiWs = new WebSocket('wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview', {
            headers: {
                Authorization: `Bearer ${OPENAI_API_KEY}`,
                "OpenAI-Beta": "realtime=v1"
            }
        });

        // Function to send the session configuration to OpenAI
        const sendSessionUpdate = () => {
            const sessionUpdate = {
                type: 'session.update',
                session: {
                    turn_detection: { type: 'server_vad' },
                    input_audio_format: 'g711_ulaw',
                    output_audio_format: 'g711_ulaw',
                    voice: VOICE,
                    instructions: SYSTEM_MESSAGE,
                    modalities: ["text", "audio"],
                    temperature: 0.8,
                    input_audio_transcription: {
                        "model": "whisper-1"
                    },
                    tools: [
                        {
                            type: "function",
                            name: "end_call",
                            description: "End the call and say goodbye to the user.",
                            parameters: {
                                type: "object",
                                properties: {
                                    "message": { "type": "string", "default": "Goodbye! Ending the call now." }
                                },
                                required: ["message"]
                            }
                        },
                        {
                            type: "function",
                            name: "book_service",
                            description: "Book a car service for the customer",
                            parameters: {
                                type: "object",
                                properties: {
                                    "booking_time": { "type": "string" }
                                },
                                required: ["booking_time"]
                            }
                        }
                    ],
                    tool_choice: "auto"
                }
            };

            console.log('Sending session update:', JSON.stringify(sessionUpdate));
            openAiWs.send(JSON.stringify(sessionUpdate));
        };

        // Function to send the first message once OpenAI WebSocket is ready
        const sendFirstMessage = () => {
            if (queuedFirstMessage && openAiWsReady) {
                console.log('Sending queued first message:', queuedFirstMessage);
                openAiWs.send(JSON.stringify(queuedFirstMessage));
                openAiWs.send(JSON.stringify({ type: 'response.create' }));
                queuedFirstMessage = null;
            }
        };

        // Open event for when the OpenAI WebSocket connection is established
        openAiWs.on('open', () => {
            console.log('Connected to the OpenAI Realtime API');
            openAiWsReady = true;
            sendSessionUpdate();
            sendFirstMessage();
        });

        // Handle messages from Twilio (media stream) and send them to OpenAI
        connection.on('message', (message) => {
            try {
                const data = JSON.parse(message);

                if (data.event === 'start') {
                    streamSid = data.start.streamSid;
                    callSid = data.start.callSid;
                    const customParameters = data.start.customParameters;

                    console.log('CallSid:', callSid);
                    console.log('StreamSid:', streamSid);
                    console.log('Custom Parameters:', customParameters);

                    const callerNumber = customParameters?.callerNumber || 'Unknown';
                    session.callerNumber = callerNumber;
                    firstMessage = customParameters?.firstMessage || "Hello, how can I assist you?";
                    console.log('First Message:', firstMessage);
                    console.log('Caller Number:', callerNumber);

                    queuedFirstMessage = {
                        type: 'conversation.item.create',
                        item: {
                            type: 'message',
                            role: 'user',
                            content: [{ type: 'input_text', text: firstMessage }]
                        }
                    };

                    if (openAiWsReady) {
                        sendFirstMessage();
                    }

                } else if (data.event === 'media') {
                    if (openAiWs.readyState === WebSocket.OPEN) {
                        const audioAppend = {
                            type: 'input_audio_buffer.append',
                            audio: data.media.payload
                        };
                        openAiWs.send(JSON.stringify(audioAppend));
                    }
                }
            } catch (error) {
                console.error('Error parsing message:', error, 'Message:', message);
            }
        });

        // Handle incoming messages from OpenAI
        openAiWs.on('message', async (data) => {
            try {
                const response = JSON.parse(data);

                // Handle speech interruption
                if (response.type === 'input_audio_buffer.speech_started') {
                    console.log('Speech Start:', response.type);

                    // Clear Twilio buffer
                    const clearTwilio = {
                        streamSid: streamSid,
                        event: "clear"
                    };
                    connection.send(JSON.stringify(clearTwilio));
                    console.log('Cleared Twilio buffer.');

                    // Send interrupt message to OpenAI
                    const interruptMessage = {
                        type: "response.cancel"
                    };
                    openAiWs.send(JSON.stringify(interruptMessage));
                    console.log('Cancelling AI speech from the server.');
                }


                // Handle audio responses from OpenAI
                if (response.type === 'response.audio.delta' && response.delta) {
                    connection.send(JSON.stringify({
                        event: 'media',
                        streamSid: streamSid,
                        media: { payload: response.delta }
                    }));
                }

                // Handle function calls
                if (response.type === 'response.function_call_arguments.done') {
                    console.log("Function called:", response);
                    const functionName = response.name;
                    const args = JSON.parse(response.arguments);

                    if (functionName === 'end_call') {
                        const goodbyeMessage = args.message || "Goodbye!";
                        console.log("Received end_call function. Goodbye message:", goodbyeMessage);

                        // Step 1: Create a system message for the goodbye text
                        const functionOutputEvent = {
                            type: "conversation.item.create",
                            item: {
                                type: "function_call_output",
                                role: "system",
                                output: goodbyeMessage
                            }
                        };
                        openAiWs.send(JSON.stringify(functionOutputEvent));

                        // Step 2: Trigger AI to generate an audio response for the goodbye message
                        openAiWs.send(JSON.stringify({
                            type: "response.create",
                            response: {
                                modalities: ["text", "audio"],
                                instructions: `Say: "${goodbyeMessage}".`,
                            }
                        }));

                        // Step 3: Simulate a user input to extend the conversation
                        setTimeout(() => {
                            console.log('Simulating user response: "Thank you, goodbye!"');
                            openAiWs.send(JSON.stringify({
                                type: "conversation.item.create",
                                item: {
                                    type: "message",
                                    role: "user",
                                    content: [{ type: 'input_text', text: "Thank you, goodbye!" }]
                                }
                            }));

                            // Step 4: After the simulated user response, end the call
                            setTimeout(async () => {
                                if (callSid) {
                                    console.log('Ending the call after the simulated user response.');
                                    await endCall(callSid);
                                } else {
                                    console.error('CallSid not found, cannot end call');
                                }
                            }, 6000); // Delay to ensure AI response is spoken
                        }, 3000); // Initial delay to play the goodbye message
                    }

                    else if (functionName === 'book_service') { // If the book_service function is called
                        const bookingTime = args.booking_time; // Get the booking time
                        console.log(`Booking service for: ${bookingTime}`);

                        try {
                            const webhookResponse = await sendToWebhook({
                                number: session.callerNumber,
                                message: bookingTime
                            }, BOOKING_WEBHOOK_URL);  // Use the constant here

                            console.log("Webhook response:", webhookResponse);

                            // Parse the webhook response
                            const parsedResponse = JSON.parse(webhookResponse);
                            const status = parsedResponse.Status || "unknown";
                            const bookingMessage = parsedResponse.Booking ||
                                "I'm sorry, I couldn't book the service at that time. Do you have an alternative time?";

                            // Handle the response based on status
                            const responseMessage = (status === "Successful")
                                ? `The booking was successful: ${bookingMessage}`
                                : `Unfortunately, the booking was unsuccessful. Here's the update: ${bookingMessage}`;

                            // Send the booking status back to OpenAI
                            const functionOutputEvent = {
                                type: "conversation.item.create",
                                item: {
                                    type: "function_call_output",
                                    role: "system",
                                    output: responseMessage, // Provide the booking status
                                }
                            };
                            openAiWs.send(JSON.stringify(functionOutputEvent));

                            // Trigger AI to generate a response based on the booking status
                            openAiWs.send(JSON.stringify({
                                type: "response.create",
                                response: {
                                    modalities: ["text", "audio"],
                                    instructions: `Inform the user: ${responseMessage}. Be concise and friendly.`,
                                }
                            }));
                        } catch (error) {
                            console.error('Error booking installation:', error);

                            // Send an error response to OpenAI
                            sendErrorResponse();
                        }
                    }

                }

                // Log agent response
                if (response.type === 'response.done') {
                    const agentMessage = response.response.output[0]?.content?.find(content => content.transcript)?.transcript || 'Agent message not found';
                    session.transcript += `Agent: ${agentMessage}\n`;
                    console.log(`Agent (${sessionId}): ${agentMessage}`);
                }

                // Log user transcription
                if (response.type === 'conversation.item.input_audio_transcription.completed' && response.transcript) {
                    const userMessage = response.transcript.trim();
                    session.transcript += `User: ${userMessage}\n`;
                    console.log(`User (${sessionId}): ${userMessage}`);
                }

                // Log other relevant events
                if (LOG_EVENT_TYPES.includes(response.type)) {
                    console.log(`Received event: ${response.type}`, response);
                }

            } catch (error) {
                console.error('Error processing OpenAI message:', error, 'Raw message:', data);
            }
        });

        // Handle when the connection is closed
        connection.on('close', async () => {
            if (openAiWs.readyState === WebSocket.OPEN) {
                openAiWs.close();
            }
            console.log(`Client disconnected (${sessionId}).`);
            console.log('Full Transcript:');
            console.log(session.transcript);

            console.log('Final Caller Number:', session.callerNumber);

            // await sendToWebhook({
            //     data1: session.callerNumber,
            //     data2: session.transcript
            // }, TRANSCRIPT_WEBHOOK_URL);

            sessions.delete(sessionId);
        });

        // Handle WebSocket errors
        openAiWs.on('error', (error) => {
            console.error('Error in the OpenAI WebSocket:', error);
        });

        // Helper function for sending error responses
        function sendErrorResponse() {
            openAiWs.send(JSON.stringify({
                type: "response.create",
                response: {
                    modalities: ["text", "audio"],
                    instructions: "I apologize, but I'm having trouble processing your request right now. Is there anything else I can help you with?",
                }
            }));
        }
    });
});

// Function to send data to the Make.com webhook
async function sendToWebhook(payload, webhookUrl) {
    console.log('Sending data to webhook:', JSON.stringify(payload, null, 2));  // Log the data being sent
    try {
        const response = await fetch(webhookUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'  // Set content type as JSON
            },
            body: JSON.stringify(payload)  // Send the payload as a JSON string
        });

        console.log('Webhook response status:', response.status);
        if (response.ok) {
            const responseText = await response.text();  // Get the text response from the webhook
            console.log('Webhook response:', responseText);
            return responseText;  // Return the response
        } else {
            console.error('Failed to send data to webhook:', response.statusText);
            throw new Error('Webhook request failed');  // Throw an error if the request fails
        }
    } catch (error) {
        console.error('Error sending data to webhook:', error);  // Log any errors in the request
        throw error;
    }
}


// Start the Fastify server
fastify.listen({ port: PORT, host: HOST }, (err) => {
    if (err) {
        console.error(err);
        process.exit(1);
    }
    console.log(`Server is listening on port ${PORT}`);
});