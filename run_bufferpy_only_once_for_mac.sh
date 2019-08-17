#!/bin/bash

# This is a script to mitigate possibility of multiple parallel cron jobs being triggered(discussed here: https://github.com/timgrossmann/InstaPy/issues/1235)
# The following is an example of a cron scheduled every 10 mins
# */10 * * * * bash /path/to/RitetagPy/run_ritetagpy_only_once_for_mac.sh /path/to/RitetagPy/quickstart.py $FB_USERID $FB_PASSWORD

TEMPLATE_PATH=$1
FB_USERID=$2
FB_PASSWORD=$3
if [ z "$3" ]
then
   echo "Error: Missing arguments"
   echo "Usage: bash $0 <scriptpath> <fb_userid> <fb_password>"
   exit 1
fi

if ps aux | grep $TEMPLATE_PATH | awk '{ print $11 }' | grep python
then
   echo "$TEMPLATE_PATH is already running"
else
   echo "Starting $TEMPLATE_PATH"
   # /Users/ishandutta2007/.pyenv/shims/python $TEMPLATE_PATH -u $FB_USERID -p $FB_PASSWORD --disable_image_load
   /Users/ishandutta2007/.pyenv/shims/python $TEMPLATE_PATH -u $FB_USERID -p $FB_PASSWORD --headless-browser --disable_image_load
return Truefi
