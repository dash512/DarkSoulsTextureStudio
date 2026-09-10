# Merging files

As of version 3.10.0, DSTS contains a Delta Patcher, which allows for merging modded files. This currently only supports modern games (Sekiro and newer).  
You can find it in `Tools -> Merging` after you load file(s) into the workspace.  
  
`Generate Delta` creates a file with the .delta extention that contains all the modifications for a file, and `Import Delta` prompts you for one of these files, where all the changes are then queued up in your current workspace.  
Upon selecting `Generate Delta`, you will be given 2 choices:  
  
### Generate Delta from queued modifications:
Quite simply, this option takes all the changes you have made in your currently loaded project and writes them all to a .delta file.  
  
Notes:  
 - Only changes you have made in this instance are saved. Previous modifications to the file are not accounted for.
  

### Create Delta from diffs against a vanilla file:
You will be prompted for a vanilla layout file (.sblytbnd.dcx). DSTS then compares the subtextures defined within it to those you have loaded. Any subtexture that is present in the local file but not the vanilla file is treated as a modification and added to the delta patch.  
  
Notes:
 - This option only finds subtextures that are entirely original to the modded file. Icon replacements are not accounted for.

### Create Delta from custom selection:
Opens a window with a tree list of all loaded subtextures. All subtextures you select are then added to the delta file.  
This is currently the only way to export replacements from external files that aren't your own.  
  
