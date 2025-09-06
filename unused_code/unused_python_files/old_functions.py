import requests
import json
import math
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytz
import pandas as pd
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
import dateutil.parser
from openai import OpenAI
import os
import dropbox
from dotenv import load_dotenv
import io

# Load environment variables
load_dotenv()

class Functions:
    SERVICE_ACCOUNT_FILE = '.credentials.json'
    CALENDAR_ID = 'adastraaicenter@gmail.com'
    AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    MEETING_DURATION_MIN = 30
    WORK_START_HOUR = 9
    WORK_END_HOUR = 17

    def __init__(self):
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize Dropbox client
        self.dbx = dropbox.Dropbox(os.getenv('DROPBOX_ACCESS_TOKEN'))
        
        # Initialize Google Calendar credentials
        self.credentials = service_account.Credentials.from_service_account_file(
            self.SERVICE_ACCOUNT_FILE, 
            scopes=self.SCOPES + ['https://www.googleapis.com/auth/calendar.events']
        )
        self.calendar_service = build('calendar', 'v3', credentials=self.credentials)

    def interpret_user_input(self, user_message: str, current_time: str) -> dict:
        prompt = f"""
    You will receive:
    - A user input: {{1.message}} (e.g. "tomorrow at 9 AM")
    - A reference time: {{15.currentTime}} (e.g. "2024-11-25 01:00:00 CET+0100")

    Your job:
    1. Interpret the user input as a datetime in Amsterdam local time.
    2. Use the reference time to resolve relative terms like "tomorrow".
    3. Return a JSON object like this:

    {{
    "start-date": "yyyy-mm-dd",
    "full-date": "yyyy-mm-ddTHH:MM:SS+01:00"
    }}

    Use Amsterdam time with correct DST handling.
    Only return the JSON. No explanation.
    """

        response = self.openai_client.chat.completions.create(
            model="gpt-4-0125-preview",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"My input is: {user_message}\nCurrent time: {current_time}"}
            ],
            temperature=0,
            max_tokens=256
        )

        return json.loads(response.choices[0].message.content)

    def get_calendar_events(self, start_iso: str, end_iso: str) -> list:
        tz = self.AMSTERDAM_TZ
        start_date = tz.localize(datetime.fromisoformat(start_iso))
        end_date = tz.localize(datetime.fromisoformat(end_iso))

        events_result = self.calendar_service.events().list(
            calendarId=self.CALENDAR_ID,
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            timeZone='Europe/Amsterdam'
        ).execute()

        return [
            {"start": e['start'].get('dateTime'), "end": e['end'].get('dateTime')}
            for e in events_result.get('items', [])
        ]

    def is_within_working_hours(self, start: datetime, end: datetime) -> bool:
        if start.weekday() >= 5:
            return False
        work_start = start.replace(hour=self.WORK_START_HOUR, minute=0, second=0, microsecond=0)
        work_end = start.replace(hour=self.WORK_END_HOUR, minute=0, second=0, microsecond=0)
        return work_start <= start and end <= work_end

    def has_overlap(self, start: datetime, end: datetime, busy_list: list) -> bool:
        for entry in busy_list:
            busy_start = dateutil.parser.parse(entry["start"])
            busy_end = dateutil.parser.parse(entry["end"])

            if busy_start.tzinfo is None:
                busy_start = self.AMSTERDAM_TZ.localize(busy_start)
            if busy_end.tzinfo is None:
                busy_end = self.AMSTERDAM_TZ.localize(busy_end)

            busy_start = busy_start.astimezone(self.AMSTERDAM_TZ)
            busy_end = busy_end.astimezone(self.AMSTERDAM_TZ)

            if not (end <= busy_start or start >= busy_end):
                return True
        return False

    def find_next_available_slot(self, proposed_start: datetime, busy_times: list) -> str:
        offset = 1
        for _ in range(20):
            for direction in [+1, -1]:
                delta = timedelta(minutes=30 * offset * direction)
                search_start = proposed_start + delta
                search_end = search_start + timedelta(minutes=30)

                if not self.is_within_working_hours(search_start, search_end):
                    continue
                if not self.has_overlap(search_start, search_end, busy_times):
                    return search_start.isoformat()
            offset += 1
        return None

    def schedule_meeting(self, user_message: str) -> dict:
        current_time = datetime.now(self.AMSTERDAM_TZ).strftime('%Y-%m-%d %H:%M:%S %Z%z')

        # Step 1: Interpret user input using GPT
        parsed = self.interpret_user_input(user_message, current_time)
        start_date = parsed['start-date']
        full_date = parsed['full-date']

        # Step 2: Build full date range for the calendar query
        start_date_obj = datetime.fromisoformat(start_date)
        end_date_obj = start_date_obj + timedelta(days=1)

        # Step 3: Get calendar busy times
        busy_times = self.get_calendar_events(
            start_date_obj.strftime('%Y-%m-%dT00:00:00'),
            end_date_obj.strftime('%Y-%m-%dT00:00:00')
        )

        # Step 4: Check meeting availability
        proposed_start = dateutil.parser.parse(full_date)
        if proposed_start.tzinfo is None:
            proposed_start = self.AMSTERDAM_TZ.localize(proposed_start)

        proposed_end = proposed_start + timedelta(minutes=self.MEETING_DURATION_MIN)

        if not self.is_within_working_hours(proposed_start, proposed_end):
            return {
                "result": "Outside",
                "message": "Please select a time within working hours (09:00–17:00) on weekdays"
            }

        elif self.has_overlap(proposed_start, proposed_end, busy_times):
            next_available = self.find_next_available_slot(proposed_start, busy_times)
            if next_available:
                return {
                    "result": "Deny",
                    "message": next_available
                }
            else:
                return {
                    "result": "Outside",
                    "message": "Please select another day — that day seems full"
                }

        else:
            return {
                "result": "Accept",
                "message": {
                    "start": proposed_start.isoformat(),
                    "end": proposed_end.isoformat()
                }
            }

    def create_google_calendar_event(self, summary: str, start_time: str, end_time: str, description: str = "") -> dict:
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/Amsterdam',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/Amsterdam',
            },
        }

        created_event = self.calendar_service.events().insert(calendarId=self.CALENDAR_ID, body=event).execute()
        return {
            "id": created_event.get("id"),
            "htmlLink": created_event.get("htmlLink"),
            "summary": created_event.get("summary"),
            "start": created_event["start"].get("dateTime"),
            "end": created_event["end"].get("dateTime")
        }

    def get_battery_info(self, user_message: str, phone_number: str) -> str:
        """Get battery information from database.csv in user's Dropbox folder"""
        dropbox_path = f"/{phone_number}/database.csv"
        
        try:
            # Download and read the CSV file from Dropbox
            metadata, res = self.dbx.files_download(dropbox_path)
            csv_content = res.content.decode("utf-8")
            
            # Convert CSV content to DataFrame
            df = pd.read_csv(io.StringIO(csv_content))
            
            # Create prompt for GPT
            system_prompt = '''You are a helpful assistant that answers user questions about batteries based on the provided CSV data. 
                Respond only with the specific information requested. Be concise and direct.
                Example: What is the name of the 10 volt battery?
                Answer: Battery A'''

            user_prompt = f"""Here is the battery database:
        {df.to_csv(index=False)}

        Answer this question about the batteries:
        {user_message}
        """

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2
            )

            return response.choices[0].message.content.strip()

        except dropbox.exceptions.ApiError as e:
            raise FileNotFoundError(f"❌ Database file not found in Dropbox: {dropbox_path}")
        except Exception as e:
            raise Exception(f"Error processing battery information: {str(e)}")

    def get_user_language_file_content(self, user_message: str, phone_number: str) -> dict:
        language_extraction_prompt = f"""
        You will receive a user message that includes a language preference.
        Your task is to identify the language the user wants to use, based on the meaning of their message—not the language it's written in.

        Return only one of the following keywords:
        english
        dutch
        turkish
        other

        Instructions:
        Focus on the intended language preference the user expresses.
        For example, if the user says "ingilizce", return english (because "ingilizce" means English).
        Do not return the language the message is written in—return the language the user wants.

        User message:
        \"\"\"{user_message}\"\"\"

        Return ONLY one of: english, dutch, turkish or other. No explanation.
        """

        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": language_extraction_prompt}],
            temperature=0,
            max_tokens=10
        )

        language = response.choices[0].message.content.strip().lower()

        if language not in ["english", "dutch", "turkish"]:
            raise ValueError("We are not supporting this language")

        file_map = {
            "english": "english.txt",
            "dutch": "dutch.txt",
            "turkish": "turkish.txt"
        }

        dropbox_path = f"/{phone_number}/{file_map[language]}"

        try:
            metadata, res = self.dbx.files_download(dropbox_path)
            file_content = res.content.decode("utf-8")

            return {
                "phone_number": phone_number,
                "language": language,
                "messages": [
                    {"role": "user", "content": file_content}
                ]
            }

        except dropbox.exceptions.ApiError:
            raise FileNotFoundError(f"❌ File not found in Dropbox: {dropbox_path}")
