import requests
from datetime import datetime, timedelta 
from configparser import SectionProxy
from azure.identity import  InteractiveBrowserCredential
from msgraph import GraphServiceClient
import configparser
import asyncio 


config = configparser.ConfigParser()
config.read(['config.cfg', 'config.dev.cfg'])
azure_settings = config['azure']
events = ''
headers = ''


class Account:
    settings: SectionProxy
    user_client: GraphServiceClient

    def __init__(self, config: SectionProxy):
        self.settings = config
        client_id = self.settings['clientId']
        tenant_id = self.settings['tenantId']
        graph_scopes = self.settings['graphUserScopes'].split(' ')

        self.device_code_credential = InteractiveBrowserCredential(client_id = client_id, tenant_id = tenant_id, redirect_uri="http://localhost:8400")
        self.user_client = GraphServiceClient(self.device_code_credential, scopes=graph_scopes)

    async def get_user_token(self):
        global headers
        graph_scopes = self.settings['graphUserScopes']
        access_token = self.device_code_credential.get_token(graph_scopes)
        headers = {
            'Authorization': f'Bearer {access_token.token}',
            'Prefer': 'outlook.timezone = "Eastern Standard Time"',
            'Content-Type': 'application/json'
        }
        return access_token.token


#Helper function to get the weekday of the date 
def get_weekday(date_time):
        date = datetime.fromisoformat(date_time).date()
        weekday = date.strftime('%A')
        return weekday   

#rEVAMPING TO GOOGLE Function calling 
def get_events(start_date_time:str, end_date_time:str):
    '''
    Gets all the events in the specified time frame
    
    ARGS:
    start_date_time: The user specified starting time in the format of year-month-dayTmilitaryHour:minutes:seconds 
    end_date_time: The user specified end time frame in the format of year-month-dayTmilitaryHour:minutes:seconds
    
    Returns the set of event that is listed within the time frame and all their informations
    ''' 
    #Debuggging
    print(start_date_time)
    print(end_date_time)
    events = ''
    calendar_url_single = f'https://graph.microsoft.com/v1.0/me/events?$filter=type eq \'singleInstance\' and start/dateTime ge \'{start_date_time}\' and end/dateTime le \'{end_date_time}\'&$select=subject,start,end,location'
    calendar_url_series = f'https://graph.microsoft.com/v1.0/me/events?$filter=type eq \'seriesMaster\'&$select=subject'

    if start_date_time and end_date_time:
        #Getting only the first occurrence from a recurring event 
        series_data = requests.get(calendar_url_series, headers=headers)
        for series_event in series_data.json()['value']:#Goes through each recurrence event
            series_master_id = series_event['id'] #Gets their ID
            instance_url = f'https://graph.microsoft.com/v1.0/me/events/{series_master_id}/instances?startDateTime={start_date_time}&endDateTime={end_date_time}&$select=subject,start,end,location'
            instance_data = requests.get(instance_url, headers=headers).json() 
            try:
                if instance_data['value'][0]: #Only gets the first instance' event and adds it to event 
                    first_instance = instance_data['value'][0] 
                    event_start_date_time = first_instance['start']['dateTime']
                    event_end_date_time = first_instance['end']['dateTime']
                    events += f"Event: Title = {first_instance['subject']}, Time = {event_start_date_time} {get_weekday(event_start_date_time)} - {event_end_date_time} {get_weekday(event_end_date_time)}, Location = {first_instance['location']['displayName']}, Event ID = {first_instance['id']}\n"
            except: 
                pass
        #Gets only the single instance events 
        singe_data = requests.get(calendar_url_single, headers=headers)
        for event in singe_data.json()['value']: 
            event_start_date_time = event['start']['dateTime']
            event_end_date_time = event['end']['dateTime']
            events += f"Event: Title = {event['subject']}, Time = {event_start_date_time} {get_weekday(event_start_date_time)} - {event_end_date_time} {get_weekday(event_end_date_time)}, Location = {event['location']['displayName']}, Event ID = {event['id']}\n"
    else:
        #Getting only the first occurrence from a recurring event 
        series_data = requests.get(calendar_url_series, headers=headers)
        for event in series_data.json()['value']: 
            events += f"Event: Title = {event['subject']}, Event ID = {event['id']}\n"
        #Gets only the single instance events 
        singe_data = requests.get(f'https://graph.microsoft.com/v1.0/me/events?$filter=type eq \'singleInstance\' and start/dateTime ge \'{datetime.now().isoformat()}\'&$select=subject,start,end,location', headers=headers)
        for event in singe_data.json()['value']: 
            event_start_date_time = event['start']['dateTime']
            event_end_date_time = event['end']['dateTime']
            events += f"Event: Title = {event['subject']}, Event ID = {event['id']}\n"
    print(events)
    return events 
    
    
def create_event(event_name:str, start_date:str, end_date:str, start_time:str, end_time:str, location_name:str=None, categories:str=None, notes:str = None):
        '''
        Create the event(s) in the Outlook calendar. Call this whenever the user requests an event to be added/created
        
        ARGS:
        event_name: The event's name
        start_date: The event's start date in year-month-date format
        end_date: The event's end date in year-month-date format
        start_time: The event's start time in hr:min:sec format
        end_time: The event's end time in hr:min:sec format
        location_name(optional): The event's location
        categories(optional): The event's category, look for existing category first if there is no existing category, tell the user to specify which further
        notes(optional): The event's description such as if user wants to add a little info regarding the event.
        
        Returns
        None
        '''
        
        calendar_url = 'https://graph.microsoft.com/v1.0/me/events'
        request_body = {
            'subject': f'{event_name}',
            'start': {
                'dateTime': f'{start_date}T{start_time}',
                'timeZone': 'America/New_York'
            },
            'end': {
                'dateTime': f'{end_date}T{end_time}',
                'timeZone': 'America/New_York'
            },
        }
        if location_name:
            request_body['location'] = {}
            request_body['location']['displayName'] = location_name
            
        if categories:
            request_body['categories'] = []
            request_body['categories'].append(categories)
            
                
        if notes:
            request_body['body'] = {}
            request_body['body']['contentType'] = 'HTML'
            request_body['body']['content'] = f'{notes}'
            
        response = requests.post(calendar_url, json=request_body, headers=headers)
        if response.status_code == 201:
            return 'Event created successfully!'
        else:
            return 'Event not created successfully'


def delete_event(event_id:str):
    '''
    Deletes an event by using the 'Event ID' or 'event recurring ID'
    
    ARGS:
    event_id: The event id or event recurring ID
    
    Returns None 
    '''
    url = f'https://graph.microsoft.com/v1.0/me/events/{event_id}'
    response = requests.delete(url, headers=headers)
    return 'success in deleting event' if response.status_code == 204 else 'Not successful'

def Create_event_with_recurrence(event_name:str, start_date:str, end_date:str, start_time:str, end_time:str, pattern_type:str, interval:int=1, end_type:str='noEnd', recurring_end_date:str=None, location_name:str=None, categories:str=None, daysOfWeek:list[str]=None, dayOfMonth:int = None, numberOfOccurrences:int = None, notes:str = None):
        '''
        Creates an event with the events reccuring either weekly or monthly
        
        ARGS:
        event_name: The event's name
        start_date: The event's start date in year-month-date format
        end_date: The event's end date in year-month-date format
        start_time: The event's start time in hr:min:sec format
        end_time: The event's end time in hr:min:sec format
        recurring_end_date: The ending date of this reccuring event, NOT the instance, the recurring itself
        interval: The number of units between occurrences.
        pattern_type: The type of reccurence the user wants which can be 'daily', 'weekly', 'absoluteMonthly', 'absoluteYearly'
        end_type: How the user wants the recurrance to end which can be 'numbered', 'endDate'. Default to 'noEnd'. if the user wants to create event on multiple days in a week just for one week, use 'numbered' and set numberofoccurrence to 1. If user has a date in mind which the recurrence should end, use 'endDate'. Else if the user wants it to repeat a certain time, user 'numbered'.
        daysOfWeek: The day of the week that the user wants the event to be repeated on if the type parameter is weekly. It can be multiple days which can be 'monday','tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'. format it into [], ex. ['monday', 'tuestday'], ['monday'].
        dayOfMonth: The day of the month that the user wants the event to be repeated on, if none are specified, assume its the current date
        location_name: The event's location
        categories: The event's category, such as School events, club events etc.
        notes: The event's description such as if user wants to add a little info regarding the event.
        numberOfOccurrences: If end_type is numbered, this is the number of times that the set of event repeat for.
        
        returns 
        None
        '''
        
        
        calendar_url = 'https://graph.microsoft.com/v1.0/me/events'
        request_body = {
            'subject': f'{event_name}',
            'start': {
                'dateTime': f'{start_date}T{start_time}',
                'timeZone': 'America/New_York'
            },
            'end': {
                'dateTime': f'{end_date}T{end_time}',
                'timeZone': 'America/New_York'
            },
            'recurrence': {
                'pattern': {
                    'type': f'{pattern_type.lower()}',
                    'interval': f'{int(interval)}'
                },
                'range': {
                    'type': f'{end_type}',
                    'startDate': f'{start_date}'
                }
            }
        }

        if location_name:
            request_body['location'] = {}
            request_body['location']['displayName'] = location_name
            
        if categories:
            request_body['categories'] = []
            request_body['categories'].append(categories)
        
        if daysOfWeek:
            request_body['recurrence']['pattern']['daysOfWeek'] = [day.lower() for day in daysOfWeek]
            
        if dayOfMonth:
            request_body['recurrence']['pattern']['dayOfMonth'] = dayOfMonth 
            
        if recurring_end_date:
            request_body['recurrence']['range']['endDate'] = recurring_end_date
        
        if numberOfOccurrences:
            request_body['recurrence']['range']['numberOfOccurrences'] = numberOfOccurrences
            
        if notes:
            request_body['body'] = {}
            request_body['body']['contentType'] = 'HTML'
            request_body['body']['content'] = f'{notes}'

        #Testing 
        print(request_body)
        
        
        response = requests.post(calendar_url, json=request_body, headers=headers)
        
        if response.status_code == 201:
            return 'Event created successfully!'
            
        else:
            return 'Event not created successfully' 
        
        
        
def get_categories():
    '''
    Gets all of the existing categories information such as name, color and id

    ARGS:
    None
    
    Returns the categories in a list    
    '''
    Category_url = 'https://graph.microsoft.com/v1.0/me/outlook/masterCategories/'
    Response = requests.get(Category_url, headers = headers)
    data = Response.json()
    
    if Response.status_code == 200:
        categories = [] 
        for category in data['value']:
            categories.append([category['id'], category['displayName'], category['color']])
        return categories
    else:
        return 'Not successful'


#Testing to create categories 
def create_categories(color, display_name):
    global headers 
    Create_category_url = 'https://graph.microsoft.com/v1.0/me/outlook/masterCategories'
    body_type = {
        'color' : color ,
        'displayName': display_name 
    }
    
    Response = requests.get(Create_category_url, headers = body_type)
    
    if Response.status_code == 201:
        return 'Successful'
    return 'Not successful'


#Add a create category function
 
user = Account(azure_settings)

async def run_data():
    await user.get_user_token()
    return None 




