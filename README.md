# DSTS: Dark Souls Texture Studio
A simple GUI application for managing icons and UI textures in FromSoftware games.  
  
For more information, please visit the [Documentation](https://darksoulstexturestudio.readthedocs.io/en/latest/).  

## Supports:
| Game       | Preview | Export | Replace | Add |
|------------|---------|--------|---------|-----|
| DeS        |   ✅    |  ✅    |   ✅    | ✅  |
| DS1        |   ✅    |  ✅    |   ✅    | ✅  |
| DS2        |   ✅    |  ✅    |   ✅    | ✅  |
| DS3        |   ✅    |  ✅    |   ✅    | ✅  |
| BB         |   ✅    |  ✅    |   ✅    | ✅  |
| SDT        |   ✅    |  ✅    |   ✅    | ✅  |
| AC6        |   ✅    |  ✅    |   ✅    | ✅  |
| ER         |   ✅    |  ✅    |   ✅    | ✅  |
| NR         |   ✅    |  ✅    |   ✅    | ✅  |  
  
*DS1 refers to both PTDE and Remastered, and DS2 refers to both the original and SOTFS  
  
# Prerequisites (pip install):
rich  
constrata  
PySide6  
Pillow  
zstandard  
  
# Basic Usage
Install either [UXM](https://github.com/Nordgaren/UXM-Selective-Unpack) or [NUXE](https://github.com/JKAnderson/Nuxe), then run it and unpack the Menu folder — or the whole game if you want.

After launching DSTS, you can either open a dcx/tpf file or a directory of them (such as your menu folder) from the File menu.
If the game's root folder is found in the path, it will automatically load everything. Otherwise, it will ask that you select a game type and find layout files if needed. Simply select "Cancel" for said prompt, and atlases will be loaded without processing their subtextures.  

The leftmost scrollarea are your atlases, the middle is for subtextures, and the right is the preview.  
Modern games (Sekiro and newer) use a layout system to define where subtextures start and end in the atlas.  
This means that they can be automatically cropped to the correct size when loading.  
Older games (DSR and DS3) instead just use a numbered grid system. I have already mapped some of the more uniform atlases in defs.
which will be split correctly into subtextures.  
Dark Souls 2 doesn't use atlases and just keeps a folder of thousands of images, making it hard to organize.  
  
_**Note**_: The high resolution versions of Elden Ring and Nightreigns's icons are stored in 00_solo(_h/l).tpfbdt which you can unpack with [WitchyBND](https://github.com/ividyon/WitchyBND).  
Be aware that opening this directory in DSTS will use a LOT of resources. (~3.4GB of RAM for ER and ~1.3GB for NR)  
  
# Credits:
Grimrukh for making soulstruct, which this application heavily depends on.  
Kmstr and Managarm for their suggestions, feedback and testing throughout development! :)) 
   
# Licensing and info:
This project includes code from the SoulStruct library:  
SoulStruct: https://github.com/Grimrukh/soulstruct  
License: [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)  
Reference: [SoulStruct Licensing Statement](https://github.com/Grimrukh/soulstruct/blob/main/pyproject.toml#L6)  

Only a small subset of SoulStruct's source code is included in this project. These source files are heavily modified. Please refer to the original source.     
These files remain under the original GPL-3 license.  

This project is also licensed under [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html),
and any portions that derive from SoulStruct must comply with GPL-3 when redistributed.  
