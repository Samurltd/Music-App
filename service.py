import time
from os import environ
from jnius import autoclass

# Prevent Kivy from initializing a window inside a background service
environ['KIVY_NO_ARGS'] = '1'

# Simple cross-process communication loop
if __name__ == '__main__':
    while True:
        # Your python-audio or native MediaPlayer instance plays here
        time.sleep(1)