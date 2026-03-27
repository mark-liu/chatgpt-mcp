on run
	tell application "System Events"
		-- Check if ChatGPT process exists
		if not (exists process "ChatGPT") then
			return "{\"status\": \"error\", \"message\": \"ChatGPT process not found\"}"
		end if

		tell process "ChatGPT"
			-- DO NOT activate or set frontmost — read without stealing focus

			-- Check if window exists
			if not (exists window 1) then
				return "{\"status\": \"error\", \"message\": \"No ChatGPT window found\"}"
			end if

			-- Get entire contents to find sidebar conversation items
			set allElements to entire contents of window 1
			set conversationTitles to {}

			-- The sidebar contains list items or static texts representing conversations.
			-- We look for static texts inside the navigation/sidebar area.
			-- ChatGPT macOS app uses a sidebar with clickable conversation rows,
			-- each containing a static text with the conversation title.
			repeat with elem in allElements
				try
					set elemClass to class of elem
					if elemClass is static text then
						-- Check if this static text is inside a list or outline (sidebar)
						set elemRole to role description of elem
						set parentElem to missing value
						try
							set parentElem to value of attribute "AXParent" of elem
						end try

						if parentElem is not missing value then
							try
								set parentRole to role description of parentElem
								-- Sidebar items are typically inside a "cell" or "row" or "group"
								-- that is a child of a list/outline in the sidebar
								if parentRole is "cell" or parentRole is "row" or parentRole is "group" then
									set textContent to value of elem
									if textContent is missing value then
										set textContent to description of elem
									end if
									if textContent is not missing value and length of textContent > 0 then
										-- Filter out known non-conversation UI elements
										if textContent is not "New chat" and textContent is not "ChatGPT" and textContent is not "Search" and textContent is not "Explore GPTs" and textContent is not "Temporary chat" then
											-- Check grandparent to confirm sidebar context
											set grandparentElem to missing value
											try
												set grandparentElem to value of attribute "AXParent" of parentElem
											end try
											if grandparentElem is not missing value then
												try
													set gpRole to role description of grandparentElem
													if gpRole is "list" or gpRole is "outline" or gpRole is "group" or gpRole is "row" then
														set end of conversationTitles to textContent
													end if
												end try
											end if
										end if
									end if
								end if
							end try
						end if
					end if
				end try
			end repeat

			-- Build JSON array
			set jsonResult to "{\"status\": \"success\", \"conversations\": ["
			set titleCount to count of conversationTitles
			repeat with i from 1 to titleCount
				set currentTitle to item i of conversationTitles
				set currentTitle to my escapeJSON(currentTitle)
				set jsonResult to jsonResult & "{\"index\": " & i & ", \"title\": \"" & currentTitle & "\"}"
				if i < titleCount then
					set jsonResult to jsonResult & ", "
				end if
			end repeat
			set jsonResult to jsonResult & "]}"

			return jsonResult
		end tell
	end tell
end run

-- JSON escape function
on escapeJSON(txt)
	set txt to my replaceText(txt, "\\", "\\\\")
	set txt to my replaceText(txt, "\"", "\\\"")
	set txt to my replaceText(txt, return, "\\n")
	set txt to my replaceText(txt, linefeed, "\\n")
	set txt to my replaceText(txt, tab, "\\t")
	return txt
end escapeJSON

-- Text replacement function
on replaceText(someText, oldItem, newItem)
	set {tempTID, AppleScript's text item delimiters} to {AppleScript's text item delimiters, oldItem}
	try
		set {textItems, AppleScript's text item delimiters} to {text items of someText, newItem}
		set {someText, AppleScript's text item delimiters} to {textItems as text, tempTID}
	on error errorMessage number errorNumber
		set AppleScript's text item delimiters to tempTID
		error errorMessage number errorNumber
	end try
	return someText
end replaceText
