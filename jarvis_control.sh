#!/bin/bash
# Script to control the JARVIS background daemon

PLIST="~/Library/LaunchAgents/com.seleemaleshinloye.jarvis.plist"
PLIST_EVAL=$(eval echo $PLIST)

function show_help() {
    echo "Usage: ./jarvis_control.sh [start|stop|restart|status|logs]"
}

case "$1" in
    start)
        echo "Starting JARVIS daemon..."
        launchctl load -w "$PLIST_EVAL"
        ;;
    stop)
        echo "Stopping JARVIS daemon..."
        launchctl unload -w "$PLIST_EVAL"
        ;;
    restart)
        echo "Restarting JARVIS daemon..."
        launchctl unload -w "$PLIST_EVAL" 2>/dev/null
        sleep 1
        launchctl load -w "$PLIST_EVAL"
        ;;
    status)
        launchctl list | grep jarvis
        ;;
    logs)
        tail -f ~/Javis/jarvis.log
        ;;
    *)
        show_help
        ;;
esac
