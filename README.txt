MAIK'S SPOOFER
==============

LOCAL USE
---------
1. Keep Spoofer.exe and config.json in the same folder.
2. Run Spoofer.exe.
3. Complete the first-time setup if asked.
4. Choose "1. Start server" and leave the window open.
5. Install Maiks_Spoofer_Plugin.lua in Roblox Studio's Plugins folder.
6. Open the plugin, choose CONNECT, then choose SPOOF.

The service is local-only and listens on localhost. Do not expose its port to
the internet.

UPDATES
-------
The app can check a GitHub Release manifest before opening the main menu.
Configure it from Settings > Set Update URL with:

https://github.com/OWNER/REPOSITORY/releases/latest/download/update-manifest.json

Updates require HTTPS and are verified with SHA-256 before installation.
The app asks for confirmation before replacing itself.

RELEASE BUILD
-------------
Run build_exe.ps1 in PowerShell. The result is Spoofer.exe in this folder.

GITHUB RELEASES
---------------
Create a GitHub repository and push these source files. Then create a tag,
for example:

git add .
git commit -m "Prepare release"
git tag v2.2.0
git push origin main --tags

GitHub Actions will build and publish the EXE and update manifest. After the
first release, set the update URL in the app to:

https://github.com/OWNER/REPOSITORY/releases/latest/download/update-manifest.json

SECURITY
--------
Never share config.json. It contains Roblox credentials and an API key.
Rotate credentials immediately if config.json is exposed.