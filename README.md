# Practice Log

Track daily practice time with simple JSON entries and visualize progress.

## How to Create a New Log Entry

1. **Choose a "slug"**  
   - The slug is whatever you are tracking (e.g., `violin`, `piano`, `language`).  
   - **Do not use sensitive or personally identifiable information.**  
   - For private subjects (e.g., kids' progress), use a pseudonym like `C582-3`.

2. **Add a New File**  
   - In GitHub, click **Add file > Create new file**.

3. **Name the File**  
   - Use the format:  
     ```
     [slug]/[year]/[month]/[day].json
     ```
   - Example: For January 1, 2026, and a slug of `violin`, the file should be:  
     ```
     violin/2026/01/01.json
     ```
   - **Remember:** Use leading zeros for months and days (e.g., `01`, `02`).

4. **Add Practice Data**  
   - Copy and paste this JSON object into the file:  
     ```json
     [{"minutes":0}]
     ```
   - Replace `0` with the number of minutes practiced that day.

5. **Commit Changes**  
   - Click **Commit changes...**  
   - Add any details or a message in the commit description.  
   - Click **Commit changes** to save.

6. **Check GitHub Actions**  
   - Go to the **Actions** tab.  
   - After a few minutes, the progress dot will change from brown to green (refresh if needed).

7. **View Your Progress**  
   - Visit [practice.benchantech.com](https://practice.benchantech.com).  
   - Click **Show Settings** and fill in your information.  
   - Click **Update** to see your minutes visualized in the graph.
