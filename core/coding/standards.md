# Coding Standards

## 1. Technology Stack
*   **Backend/Platform**: **Frappe** (Python) for custom apps and backend logic.
*   **Frontend**: **Next.js** + **Vercel AI SDK** for web interfaces.
*   **Mobile**: **Flutter** for cross-platform apps. 
*   **Native Mobile**: **Kotlin** for Android-specific needs.
*   **Styling**: Vanilla CSS for flexibility. Avoid TailwindCSS unless explicitly requested.

## 2. Implementation Rules
*   **No Placeholders**: Never use placeholders. Use generation tools to create working demonstrations.
*   **Absolute Paths**: Always use absolute paths for file operations.

## 3. SEO Best Practices
*   **Tags**: Proper Title tags and Meta descriptions.
*   **Structure**: Single `<h1>`, semantic HTML5.
*   **Performance**: Optimize for fast load times.

## 4. Operational Hygiene
*   **Trust but Verify**: After **every** file edit (`replace_file_content`, `write_to_file`), you MUST use `view_file` to confirm the change was applied correctly. Do not assume success.
*   **Folder Hygiene**: If you move or delete files:
    1.  Check if the source folder is now empty.
    2.  **If Empty**: Delete the folder OR add a `.gitkeep` file if the structure is needed.
    3.  **Why**: Prevents "Ghost Folders" cluttering the repo.
