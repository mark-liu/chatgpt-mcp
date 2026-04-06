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

					-- Collect static texts via multi-attribute fallback chain
					if elemClass is static text then
						try
							set textContent to missing value

							-- 1. description (SwiftUI primary path)
							try
								set textContent to description of elem
							end try
							if textContent is missing value or textContent is "" or textContent is "text" then
								-- 2. value
								try
									set textContent to value of elem
								end try
							end if
							if textContent is missing value or textContent is "" or textContent is "text" then
								-- 3. accessibility description
								try
									set textContent to accessibility description of elem
								end try
							end if
							if textContent is missing value or textContent is "" or textContent is "text" then
								-- 4. help attribute
								try
									set textContent to help of elem
								end try
							end if

							if textContent is not missing value and length of textContent > 0 then
								if textContent is not equal to "" and textContent is not equal to " " and textContent is not equal to "text" then
									set end of allTexts to textContent
								end if
							end if
						end try
					end if

					-- Check groups/buttons for text via name or title
					if elemClass is group or elemClass is button then
						if elemClass is button then
							set end of buttonsList to elem
						end if
						try
							set textContent to missing value
							try
								set textContent to name of elem
							end try
							if textContent is missing value or textContent is "" then
								try
									set textContent to title of elem
								end try
							end if
							-- Only collect if it looks like real content (>2 chars)
							if textContent is not missing value and length of textContent > 2 then
								set end of allTexts to textContent
							end if
						end try
					end if

					-- Collect remaining buttons (not group-or-button)
					if elemClass is button then
						-- already added above
					end if
				end try
			end repeat

			-- Fallback: if zero texts found, try AXValue on scroll area content
			if (count of allTexts) is 0 then
				try
					set scrollAreas to every scroll area of window 1
					repeat with sa in scrollAreas
						try
							set saVal to value of sa
							if saVal is not missing value and saVal is not "" then
								set end of allTexts to saVal
							end if
						end try
						-- Try AXValue on children of the scroll area
						try
							set saChildren to entire contents of sa
							repeat with sc in saChildren
								try
									set scVal to value of sc
									if scVal is not missing value and length of scVal > 0 then
										if scVal is not equal to "" and scVal is not equal to " " then
											set end of allTexts to scVal
										end if
									end if
								end try
							end repeat
						end try
					end repeat
				end try
			end if

			-- Universal conversation completion detection
			set conversationComplete to false
			set foundModelButton to false
			set isGenerating to false

			repeat with i from 1 to count of buttonsList
				try
					set currentButton to item i of buttonsList
					set btnHelp to help of currentButton
					set btnValue to value of currentButton

					-- Detect active generation: "Stop" button present
					if btnHelp is not missing value then
						if (btnHelp contains "Stop" or btnHelp contains "stop") then
							set isGenerating to true
						end if
					end if
					if btnValue is not missing value then
						if (btnValue contains "Stop" or btnValue is "Stop generating") then
							set isGenerating to true
						end if
					end if

					-- Check for "thinking" indicator via button name
					try
						set btnName to name of currentButton
						if btnName is not missing value then
							if (btnName contains "Stop" or btnName contains "stop") then
								set isGenerating to true
							end if
						end if
					end try

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

			-- Also detect "Thinking" / "Searching" static text as generation signal
			repeat with txtItem in allTexts
				try
					if txtItem starts with "Thinking" or txtItem starts with "Searching" or txtItem starts with "Browsing" or txtItem starts with "Analyzing" or txtItem starts with "Reading" then
						set isGenerating to true
						exit repeat
					end if
				end try
			end repeat

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

			-- Add indicators
			set jsonResult to jsonResult & "\"indicators\": {"
			set jsonResult to jsonResult & "\"conversationComplete\": " & conversationComplete
			set jsonResult to jsonResult & ", \"isGenerating\": " & isGenerating
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
