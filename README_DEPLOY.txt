SENEI KOTSU Invoice HTML App V11 - Vercel Static Deploy

Folder structure:
- index.html        Main app file
- vercel.json       Vercel static routing config

How to deploy with Vercel:
1. Create a GitHub repository, for example: senei-kotsu-invoice-v11
2. Upload everything inside this folder to that repository.
3. Go to https://vercel.com/new
4. Import the GitHub repository.
5. Framework Preset: Other
6. Build Command: leave blank
7. Output Directory: leave blank
8. Deploy

Data storage note:
- This V11 uses browser Local Storage.
- Data is saved only on the computer/browser that opens the app.
- If you open the Vercel link from another computer, customer/invoice data will not automatically appear.
- Use Backup/Restore JSON to move data between browsers or computers.

Future upgrade:
- Add Supabase database for shared data across devices/users.
