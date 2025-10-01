Instructions..

I want you to take the yt2audio.py and and break it off into the necessary projects 
Include any additions that are presented in the project instructions

Updated Directory: ( Follow this for reference when it comes to the building blocks of the project) 

yt2aws (Main folder);
- check.py 
- start.py
- getlink.py //disregard for now//
- complete.py
- getlink.py 
- - methods (folder)
- - - youtube (folder)
- - - - method1.py = yt_dlp method
- - - - method2.py = selemium download method 
- - - instagram (folder) //disregard for now//
- - - tiktok (folder) //disregard for now//
- - - splits
- - - - splitter.py = demucs stem splitter
- - - - basicsplitter.py = simplified demucs stem splitter 
- details (folder) //disregard for now//
- - summarize.py //disregard for now//
- - findkey //disregard for now//
- - findtemp //disregard for now//


//check.py//
Structure: 
- Determine whether OS is either mac or windows.
- - If mac, run future commands as if it's a mac device
- - If Windows, run future commands as if it was on a windows device
- Look for all dependencies listed in requirements.txt
- - Provide a log that tells me whether each dependency has been found or needs to be installed. 
[LOG EXAMPLE =
    (IF FOUND) dependency1 ==> Found (indlude file path)
    (IF NOT FOUND) dependency1 ==> !MIA! (provide a list of all the places you looked)
]

- Use the list of missing depencencies and install them. 
- If everything was downloaded successfully, return "DONE!" and close the program 
- If something went wrong, close project and include a log of everything leading up to what went wrong.
..........................................................................................................................................

//start.py//

[CHECKS =
    1)Determine what OS is running
    - Display txt = "Windows" if Windows, "Mac" if MacOS
    2)Locate necessary dependencies
    - Give me a log of everything that found. If any dependency was not found, make note of it in the log. 

]

[Adapt =
    - If windows was detected, make sure that the project uses file paths and installation paths, if detected Mac then do the same but for MacOS
    - 
    
]

Run getlink.py

Run Methods

(assuming everything works fine)
upon completion, send .wav file and continue to..

findtemp.py
- use the downloaded wav file as the input file for this project 
- when everything previous to this point has been executed, run the checkpoint 

[CHECKPOINT = 
    - Give the user 2 options
    - - OPTION 1 = Basic Stem Seperation = 
    - - OPTION 2 = Complex Stem Seperation = splitter.py
    - User must respond with either "1" or "2"
    - - If user inputs "1", run option 1
    - - If user inputs "2", run option 2
    - - If user inputs any option that isn't "1" or "2", reply with "This is not valid, try again"
    - - - repeat process until user inputs valid response
]

If everything runs properly, 

run complete.py
.................................................................................
//getlink.py//
= Display txt
= = txt = "==INSERT==LINK=="
- User will paste a valid link 
- - typeoflink: Youtube, Youtube shorts, Instagram, Tiktok (for right now, just use youtube/youtube shorts link only)
- - input = [link : "user inserts link here"]
- - If the link the user inputs is not a valid link, return with the message, "invalid, try again" and repeat the prompt
- - If the link is a valid youtube link, reply with "This works!"
- Use the inputted ink as the input 
..............................................
//method1.py//
[Method 1 
    - If the method is able to start the download, display a txt 
    - - txt = "===Methodrunning==="
    - If the method is not able to start downloading, display a txt
    - - txt = "===MethodFail==="
    - Run method2
]
.....................................................................................
//method2.py//
[Method 2
    - If the method is able to start the download, display a txt 
    - - txt = "===Methodrunning==="
    - If the method is not able to start downloading, display a txt
    - - txt = "===MethodFail==="
    - Provide an entire log of the Method events
    - close project
]
....................................................................................
//splitter.py//

- I am already happy with the functionality of the AI splitter, I donot want anything ot be chaged about htat. 
- Make the progress log a little more minimal
[progress logs =
    - Include 2 progress bars
    - - 1 => entire stem splitting progress (drums, bass, vocals, instruments)
    - - 2 => stem splitting section (whatever the project is focussing on)
    - After each section is finished, return = "Finished, next is ()"
    - Only include a detailed version of the progress if the splitter fails
]
- instead of exporting all the seperated stems at once..
- - try to export each stem one at a time
- Include another log once stems have been split to show save progress
[Progress Log 2 =
    - Include simple progress log for file saving
]

..........................................
//basicsplitter.py//
- do not change the functionality of the project, from here on out, only add features and edit to include the features if needed. 
- Make the progress log a little more minimal
[progress logs =
    - Include 2 progress bars
    - - 1 => entire stem splitting progress (drums, bass, vocals, instruments)
    - - 2 => stem splitting section (whatever the project is focussing on)
    - After each section is finished, return = "Finished, next is ()"
    - Only include a detailed version of the progress if the splitter fails
    - make sure that both progress logs are accurate with demucs workflow
]

......................................
//complete.py//
- If everything worked
- - [   ===============================================================
        PROCESS COMPLETE !
        (FILE LOCATIONS OF EVERYTHING SHOULD GO HERE)
        ===============================================================

]

SUMMARY (do not include this section in the project yet) = [
    - Display txt file details from summary.py 
    - If there is an error
    - - Display ":( no bueno :("
    - - Provide error log 
]

METHOD 1 BREAKDOWN = [
    - Gather progress log from method 1, Determine if method was executed properly, or if it failed
    - if method failed
    - - copy a log of what led to the fail 
    - - paste log in this section

]

METHOD 2 BREAKDOWN = [
    - Gather progress log from method 2, Determine if method was executed properly, or if it failed
    - if method failed
    - - copy a log of what led to the fail 
    - - paste log in this section

]

........................................................................
//summarize.py//
- takes results and puts all properties into a text file
- gather output from 
- - findtemp.py
- - findkey.py
- return output 
- [output = 
    Tempo = "tempo"
    Key = "key"
    
]
- put the output into a txt file
txtfilename = details.txt


...............................................................
//findkey//

..................................................................
//findtemp
- the goal of this project is to find the key of an audio file 
- takes audio file input
- audio analysis
- determine tempo 
- - If tempo has a decimal, round to the nearest hundredth (0.00)
- Output: "Tempo = []bpm"
...........................................................................
//notes//
- Provide an updated requirements.txt if there are any additions to the project for each time if needed
- Provide a readme.md that gets updated if there are any changes. To explain how to properly use and run the project
........................................................................................

Virtual Environment Stuff
ACTIVATION = 
MAC = source ytmusic/bin/activate
WINDOWS = .\musicwin\Scripts\Activate.ps1
