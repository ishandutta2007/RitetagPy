#!/bin/bash

# The following is an example of a cron scheduled every alternate day
# 0 3 * * * bash /path/to/RitetagPy/run_all_ritetagpy_only_once_for_mac.sh /path/to/RitetagPy/multiuser_quickstart.py

/usr/bin/osascript -e 'tell application "System Events" to keystroke "hm" using {command down, option down}'

TEMPLATE_PATH=$1
if [ -z "$1" ]
then
   echo "Error: Missing arguments"
   echo "Usage: bash $0 <script-path>"
   exit 1
fi

if ps aux | grep $TEMPLATE_PATH | awk '{ print $11 }' | grep python
then
   echo "$TEMPLATE_PATH is already running"
else
   echo "Starting $TEMPLATE_PATH"
   /Users/ishandutta2007/.pyenv/shims/python $TEMPLATE_PATH
fi

