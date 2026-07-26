import os
import base64
from twilio.rest import Client
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from groq import Groq

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def get_google_services():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    gmail = build('gmail', 'v1', credentials=creds)
    calendar = build('calendar', 'v3', credentials=creds)
    return gmail, calendar

def get_emails(gmail):
    since = (datetime.now() - timedelta(hours=24)).strftime('%Y/%m/%d')
    results = gmail.users().messages().list(
        userId='me',
        q=f'after:{since} -category:promotions -category:social',
        maxResults=20
    ).execute()
    messages = results.get('messages', [])
    emails = []
    for msg in messages:
        detail = gmail.users().messages().get(
            userId='me', id=msg['id'], format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()
        headers = {h['name']: h['value'] for h in detail['payload']['headers']}
        snippet = detail.get('snippet', '')
        emails.append(f"From: {headers.get('From', '')}\nSubject: {headers.get('Subject', '')}\nPreview: {snippet}")
    return emails

def get_calendar_events(calendar):
    now = datetime.utcnow().isoformat() + 'Z'
    end = (datetime.utcnow() + timedelta(hours=24)).isoformat() + 'Z'
    events_result = calendar.events().list(
        calendarId='primary', timeMin=now, timeMax=end,
        maxResults=10, singleEvents=True, orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    event_list = []
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        event_list.append(f"- {e.get('summary', 'No title')} at {start}")
    return event_list

def generate_digest(emails, events):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    email_text = "\n\n".join(emails) if emails else "No emails in last 24 hours"
    event_text = "\n".join(events) if events else "No events today"
    
    prompt = f"""You are an AI chief of staff for a recruiter. Look through these emails and identify:
1. Candidates waiting for a reply
2. Clients who need an update  
3. Follow-ups that are about to go cold
4. Interviews to confirm or schedule
5. What can wait

Keep it short, actionable, formatted for WhatsApp. No fluff.

EMAILS (last 24 hours):
{email_text}

CALENDAR (next 24 hours):
{event_text}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    return response.choices[0].message.content
def send_whatsapp(message):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    client = Client(account_sid, auth_token)
    
    client.messages.create(
        from_='whatsapp:+14155238886',
        body=message,
        to='whatsapp:+919949226084'
    )
    print("Sent to WhatsApp!")
def main():
    print("Connecting to Gmail and Calendar...")
    gmail, calendar = get_google_services()
    
    print("Fetching emails...")
    emails = get_emails(gmail)
    print(f"Found {len(emails)} emails")
    
    print("Fetching calendar events...")
    events = get_calendar_events(calendar)
    print(f"Found {len(events)} events")
    
    print("\nGenerating your morning digest...\n")
    digest = generate_digest(emails, events)
    
    print("=" * 50)
    print("YOUR MORNING DIGEST")
    print("=" * 50)
    print(digest)
    send_whatsapp(digest)
    print("=" * 50)

if __name__ == '__main__':
    main()
    
