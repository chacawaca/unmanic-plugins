
<div style="background-color:#cfd;border-radius:4px;border-left:solid 5px #2b4;padding:10px;">
<b>Tip:</b>
<br>It is recommended to have this as the <b>first</b> Plugin in your <b>Worker - Processing file</b></b> flow.
</div>

### Overview

This plugin will install <a href="https://ccextractor.org/">CCextractor </a> and extract closed captions / subtitles extraction from any media file.
It will output .srt file with the same name as source file.



### Config description:

#### <span style="color:blue">Only run when the original source file matches specified extensions</span>
When selected, you may specify a list of file extensions that this Plugin will be limited to processing.

This list is matched against the original source file. Not the current cached file.
For this reason you can remux the original file to another container prior to processing.

Eg: If you limit to `ts` files only and then, in your Plugin flow prior to this Plugin running, another Plugin remuxes
the file `.ts` -> `.mkv`, this Plugin will still process the `.mkv` file.




