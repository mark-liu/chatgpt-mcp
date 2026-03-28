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

			-- Get entire contents
			set allElements to entire contents of window 1

			-- Collect texts and buttons for completion detection
			set allTexts to {}
			set buttonsList to {}

			repeat with elem in allElements
				try
					set elemClass to class of elem

					-- Collect static texts
					if elemClass is static text then
						try
							-- Try description first (ChatGPT macOS uses
							-- SwiftUI which exposes text via description,
							-- not value)
							set textContent to missing value
							try
								set textContent to description of elem
							end try
							if textContent is missing value or textContent is "" or textContent is "text" then
								try
									set textContent to value of elem
								end try
							end if

							if textContent is not missing value and length of textContent > 0 then
								if textContent is not equal to "" and textContent is not equal to " " and textContent is not equal to "text" then
									set end of allTexts to textContent
								end if
							end if
						end try
					end if

					-- Collect buttons for sequence analysis
					if elemClass is button then
						set end of buttonsList to elem
					end if
				end try
			end repeat

			-- Universal conversation completion detection
			set conversationComplete to false
			set foundModelButton to false

			repeat with i from 1 to count of buttonsList
				try
					set currentButton to item i of buttonsList
					set btnHelp to help of currentButton
					set btnValue to value of currentButton

					-- Check if this is the model selection button
					if btnValue is not missing value and btnHelp is not missing value then
						if (btnHelp contains "model" or btnHelp contains "GPT") and (length of btnValue > 0) then
							set foundModelButton to true
							-- Check if next button exists and has voice/input related functionality
							if i < (count of buttonsList) then
								set nextButton to item (i + 1) of buttonsList
								try
									set nextBtnHelp to help of nextButton
									if nextBtnHelp is not missing value then
										if (nextBtnHelp contains "voice" or nextBtnHelp contains "Transcribe") then
											set conversationComplete to true
										end if
									end if
								end try
							end if
							exit repeat
						end if
					end if
				end try
			end repeat

			-- Fallback: Check if we have any voice-related buttons at all
			if not conversationComplete and foundModelButton then
				repeat with btnElement in buttonsList
					try
						set btnHelp to help of btnElement
						if btnHelp is not missing value then
							if (btnHelp contains "voice" or btnHelp contains "dictation" or btnHelp contains "speech") then
								set conversationComplete to true
								exit repeat
							end if
						end if
					end try
				end repeat
			end if

			-- Build simplified JSON result
			set jsonResult to "{\"status\": \"success\", "

			-- Add text count and texts
			set textCount to count of allTexts
			set jsonResult to jsonResult & "\"textCount\": " & textCount & ", \"texts\": ["

			repeat with i from 1 to textCount
				set currentText to item i of allTexts
				-- Escape JSON characters
				set currentText to my escapeJSON(currentText)

				set jsonResult to jsonResult & "\"" & currentText & "\""
				if i < textCount then
					set jsonResult to jsonResult & ", "
				end if
			end repeat

			set jsonResult to jsonResult & "], "

			-- Add only the essential indicator
			set jsonResult to jsonResult & "\"indicators\": {"
			set jsonResult to jsonResult & "\"conversationComplete\": " & conversationComplete
			set jsonResult to jsonResult & "}}"

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
