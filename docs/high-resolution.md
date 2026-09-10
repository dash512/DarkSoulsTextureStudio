# Creating High Resolution Textures for Inventory/Codex

Every item's icon has a high resolution version that's used in details previews. In the case of Elden Ring, this is the inventory view, and for Nightreign, the Visual Codex.  
  
There are two ways to accomplish this: the vanilla and "correct" way, and the easier distributable way.  

## Method 1 (original):  
1. Unpack `00_solo.tpfbdt` with [WitchyBND](https://github.com/ividyon/WitchyBND)
2. Follow the [Creating a Custom File](custom-files.md) guide to create a compressed file. Be sure to name it `MENU_Knowledge_{id}` where `id` is the same iconId you used for the regular icon. (Use DCX_KRAK and encoding 1 on export)
3. Paste the outputted file into the directory created by Witchy
4. Open `_witchy-bxf4.xml` in a text editor of your choice and add entries for each custom texture. For example:

    ```xml
    <file>
        <flags>Flag1</flags>
        <id>3052</id>
        <path>MENU_Knowledge_69420.tpf.dcx</path>
    </file>
    ```

    The `<id>` should just be the next increment for the file. If there are 3200 files, your first new one would be 3201 etc.

    `<path>` should obviously be the relative path to your custom file.
  
After saving your changes, repack the unpacked directory with Witchy.   
  
### Pros:
- The 00_solo archives are lazy loaded, meaning textures are only fetched when needed and don't take up additional memory.
- This is the more correct way of doing things, as it's how the game stores the vanilla versions.
  
### Cons:
- If you redistribute your mod, such as publishing it on Nexusmods, you have to include the ENTIRE `00_solo` file, which can be *very* large.
- It's harder to find your additions at a later date.
- Repack times are longer and more temporary storage is required.
  
  
## Method 2 (new):
With `01_common` open, as with adding the regular icon, simply add a custom atlas with the "+" button, and use the high-res texture for it.  
As long as the name is still `MENU_Knowledge_{id}`, the game will be able to load it, regardless of it being in the "wrong" file.  

### Pros:
- This is way more storage efficient, and takes up minimal space in your mod, making it easier to upload.
- Your custom additions will be the only `MENU_Knowledge` files in `01_common`, making it very easy to tell what's modded.
- Saves time you would have spent editing Witchy's xml.

### Cons:
- Common textures are always loaded in RAM, and will thus bloat up the game. <- IMPORTANT!
- This is not a commonly used or known method, and as such, other people trying to look around or work on your mod may be confused.
- If you add a LOT of textures, load times for `01_common` will increase.  
  
### Which to choose?
If you're only adding a few icons, Method 2 is probably fine and will only add a few megabytes to memory consumption.  
If you're making an expansive mod with many items, or if you are on a low end PC, use Method 1.
  
### Acknowledgements:
Big thanks to Kaivo on discord for bringing the latter method to my attention as well as Ivi for clarifying on how they differ in terms of memory usage :)