#!/usr/bin/env bash
# macOS Permissions Helper for JARVIS

echo "========================================================="
echo "        J.A.R.V.I.S. macOS PERMISSION SETUP"
echo "========================================================="
echo ""
echo "Because JARVIS runs in the background and can control your mouse,"
echo "camera, and microphone, macOS requires you to grant explicit permissions."
echo ""
echo "Please do the following:"
echo "1. Open System Settings > Privacy & Security"
echo "2. Go to 'Full Disk Access', click +, and add Terminal (or iTerm2)."
echo "3. Go to 'Accessibility', click +, and add Terminal (for mouse control)."
echo "4. Go to 'Microphone' and ensure Terminal is checked."
echo "5. Go to 'Camera' and ensure Terminal is checked."
echo ""
echo "Note: If you run JARVIS via launchd (background daemon), you may need"
echo "to add '/bin/bash' or '/usr/bin/python3' to Accessibility instead."
echo ""
echo "Press any key to open Privacy & Security settings..."
read -n 1 -s
open "x-apple.systempreferences:com.apple.preference.security?Privacy"
