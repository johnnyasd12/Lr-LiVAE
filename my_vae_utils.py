import datetime

import time

class Timer2:
    def __init__(self, name, enable):
        # TODO: accumulate the time interval of all iterations
#         self.name = name
        self.start_t = {}
        self.last_t = {}
#         self.start_t['name'] = self.last_t['name'] = name
#         self.start_t['time'] = self.last_t['time'] = time.time()
#         self.start_t['clock'] = self.last_t['clock'] = time.clock()
#         self.start_t['process_time'] = self.last_t['process_time'] = time.process_time()
        self.start_t['name'] = name
        self.start_t['time'] = time.time()
        self.start_t['clock'] = time.clock()
        self.start_t['process_time'] = time.process_time()
        self.last_t = self.start_t.copy()
        
        self.end_t = {}
        self.duration = {}
        self.duration['from'] = name
        self.enable = enable
        if self.enable:
            print(name,'start.')
    
    def __call__(self, name):
        self.keys = ['time', 'clock', 'process_time']
        self.end_t['name'] = name
        self.end_t['time'] = time.time()
        self.end_t['clock'] = time.clock()
        self.end_t['process_time'] = time.process_time()
        
        self.duration['from'] = self.last_t['name']
        self.duration['to'] = name
        for k in self.keys:
            self.duration[k] = self.end_t[k] - self.last_t[k]
        
        if self.enable:
#         print('since last time:', self.duration)
            print('Duration from "' + self.duration['from'] + '" to "' + self.duration['to'] +'": ')
            print('time:', self.duration['time'], ', process time:', self.duration['process_time'])
        self.last_t = self.end_t.copy()
