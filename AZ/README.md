# BYD Mod Studio User Guide

1. **Set Up Folder Structure**

   - Place `byd_mod_studio.exe` in an empty folder.
   - Double‑click to run it once; this will automatically create the following subfolders:
     - `bak\` – for backups in case you forget
     - `source\` – where you put your original AssetBundle files
     - `decrypt\` – where decrypted bundles are placed
     - `export\` – where exported textures go (and where you replace them)
     - `encrypt\` – where re‑encrypted bundles (your mods) are saved

2. **Locate the Bundle Files to Process**

   - Open `assetbundle.Chs.strip.json`.

   - Each entry has a `Hash` field—this hash is the filename of the actual AssetBundle. Copy every bundle you want to mod into the `source\` folder.

   - Or, to automate:

     - Set `dat_path` to your `dat` directory.

     - Create a `source.txt` listing the bundle paths you want (one per line), e.g.:

       ```
       Assets/_Wizard2Resources/Card/Textures/100011300
       ```

     - When you start the tool, it will ask if you’d like it to find the matching hash files and copy them into `source\` for you.

3. **Decrypt & Export**

   - In the program window, press **Enter**.
   - Decrypted and renamed AssetBundle files will appear in `decrypt\`.
   - If a bundle contains any `Texture2D` resources, the tool will ask whether to export them; exported images go into `export\`.

4. **(Optional) Edit Files**

   - Use your preferred Unity asset‑editing tool to open and modify files in `decrypt\`, or edit the PNGs in `export\`.
   - Save your changes when you’re done.

5. **(Optional) Re‑import Edited Textures**

   - If you’ve changed images in `export\`, choose whether to run the import step to bake them back into the decrypted bundles.

6. **Re‑encrypt Bundles**

   - In the program window, press **Enter** again.
   - The tool will re‑encrypt your modified bundles and save them (under their original names) to `encrypt\`.

7. **Done**

   - Take the files from `encrypt\` and deploy them to your game or other workflow.

## Changelog

**2025‑06‑26 v0.2.1**

- Fixed a bug that prevented texture exports for main‑server files; improved directory layout.
- Added a prompt before each step—press Y or Enter to proceed, any other key to skip—so you can interrupt and resume without redoing earlier steps.

**2025‑07‑03 v0.2.2**

- Added automatic file‑copying and backup features; updated the guide accordingly.

**2025‑07‑18 v0.2.3**

- If you have a full `assetbundle.Chs.manifest.json` (captured via packet‑sniffing), place it in the root folder—the tool will load that first. Useful when the tool itself isn’t up to date or for the CN region.

## Note

- Tested with Unity **2022.3.18f1**.