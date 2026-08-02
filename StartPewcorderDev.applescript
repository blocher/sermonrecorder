-- Get screen dimensions
tell application "Finder"
	set screenBounds to bounds of window of desktop
	set screenWidth to item 3 of screenBounds
	set screenHeight to item 4 of screenBounds
end tell

set projectRoot to "~/projects/sermonrecorder"
set backendDir to projectRoot & "/backend"
set activateVenv to "source " & backendDir & "/.venv/bin/activate"
-- Listeners only; escalate to SIGKILL if the port is still held.
set freeRedisPort to "pids=$(lsof -t -iTCP:6379 -sTCP:LISTEN 2>/dev/null || true); if [ -n \"$pids\" ]; then kill $pids 2>/dev/null || true; sleep 0.5; pids=$(lsof -t -iTCP:6379 -sTCP:LISTEN 2>/dev/null || true); if [ -n \"$pids\" ]; then kill -9 $pids 2>/dev/null || true; sleep 0.3; fi; fi"

tell application "iTerm"
	activate
	
	-- Close any existing windows with our specific session names to avoid duplicates
	set windowList to windows
	repeat with w in windowList
		try
			set sessionList to sessions of current tab of w
			repeat with s in sessionList
				tell s
					set pewSession to variable named "user.PewcorderSession"
					if pewSession is not missing value then
						close w
						exit repeat
					end if
				end tell
			end repeat
		end try
	end repeat
	
	-- Create new window and set its bounds (75% width, 100% height)
	set newWindow to (create window with default profile)
	set bounds of newWindow to {0, 0, screenWidth * 0.75, screenHeight}
	
	-- Pane 1: Redis
	tell current session of newWindow
		set variable named "user.PewcorderSession" to "Redis"
		set name to "Pewcorder Redis"
		write text "cd " & projectRoot
		write text activateVenv
		write text freeRedisPort
		write text "redis-server"
		set pane2 to (split horizontally with default profile)
	end tell
	
	-- Pane 2: Django API
	tell pane2
		set variable named "user.PewcorderSession" to "Backend"
		set name to "Pewcorder Backend"
		write text "cd " & backendDir
		write text activateVenv
		write text "kill $(lsof -t -iTCP:8000 -sTCP:LISTEN 2>/dev/null) 2>/dev/null || true"
		write text "python manage.py runserver"
		set pane3 to (split horizontally with default profile)
	end tell
	
	-- Pane 3: Celery worker + beat (local-dev combined)
	tell pane3
		set variable named "user.PewcorderSession" to "Celery"
		set name to "Pewcorder Celery"
		write text "cd " & backendDir
		write text activateVenv
		write text "celery -A config worker --beat --loglevel=INFO"
		set pane4 to (split horizontally with default profile)
	end tell
	
	-- Pane 4: Vite frontend
	tell pane4
		set variable named "user.PewcorderSession" to "Frontend"
		set name to "Pewcorder Frontend"
		write text "cd " & projectRoot & "/frontend"
		write text activateVenv
		write text "kill $(lsof -t -iTCP:5173 -sTCP:LISTEN 2>/dev/null) 2>/dev/null || true"
		write text "npm run dev"
		set pane5 to (split horizontally with default profile)
	end tell
	
	-- Pane 5: Working panel
	tell pane5
		set variable named "user.PewcorderSession" to "Working"
		set name to "Pewcorder Working Session"
		write text "cd " & projectRoot
		write text activateVenv
		write text "git status"
	end tell
end tell

-- Open Chrome to the frontend once Vite is likely up
try
	do shell script "sleep 2; open -a 'Google Chrome' 'http://localhost:5173/' > /dev/null 2>&1 &"
end try
