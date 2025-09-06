import re
from datetime import datetime, timedelta

log_message = ' INFO root - incoming message ---'

def filter_dash_lines(log_path):
    events = []
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if log_message in line:
                log_time_str, data = line.strip().replace(log_message, '||').replace('---', '').split('||')
                clean_str = log_time_str.strip('[]')

                # Parse with milliseconds
                dt = datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S,%f')
                events.append((dt, data))
    
    events_time_diffs = []

    with open('test_events_1.log', 'a') as f:
        for i in range(len(events)):
            dt, data = events[i]
            if i+1 < len(events):
                next_time_diff = events[i+1][0] - dt
            else:
                next_time_diff = timedelta(seconds=0)
            f.write(f'{next_time_diff.microseconds}||{data}\n')
    

if __name__ == '__main__':
    filter_dash_lines('logs/django.log')
