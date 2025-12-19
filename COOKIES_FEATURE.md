# Cookie Management Feature

## Overview

The Flow Browser now includes a dedicated cookie management system that stores and manages cookies in a `flow-cookies` folder located in the project root directory.

## Features

### 1. **Cookies Dialog**
Access the cookies manager from the main menu (**...** button → **Cookies**). This displays:
- A list of all stored cookies organized by domain
- Cookie name, value preview, and expiration time
- Action buttons for managing cookies

### 2. **Cookie Storage**
Cookies are stored in a JSON file (`flow-cookies/cookies.json`) for:
- Easy inspection and manual editing
- Portability across different systems
- Backup and export capabilities

### 3. **Cookie Operations**

#### View Cookies
- Click **Cookies** from the menu to view all stored cookies
- Each entry shows: `domain | name=value (expires: date)`
- Values longer than 30 characters are truncated with "..."

#### Open Cookies Folder
- Click **Open Cookies Folder** button to browse the cookies directory in your file explorer
- This allows you to manually inspect or edit the `cookies.json` file

#### Clear All Cookies
- Click **Clear All Cookies** to remove all stored cookies
- You'll be prompted for confirmation before deletion
- This clears both the stored JSON file and WebEngine's cookie store

#### Refresh List
- Click **Refresh** to reload the cookies list from disk
- Useful if you've manually edited the cookies.json file

## Cookie Data Format

Cookies are stored in `flow-cookies/cookies.json` in the following format:

```json
{
  "example.com": [
    {
      "name": "session_id",
      "value": "abc123xyz",
      "expires": "2025-12-31",
      "path": "/",
      "domain": "example.com",
      "secure": true,
      "httponly": true
    }
  ],
  "another-site.org": [
    {
      "name": "user_preference",
      "value": "dark_mode",
      "expires": "Session",
      "path": "/",
      "domain": "another-site.org"
    }
  ]
}
```

## How It Works

1. **Persistent Profile**: The browser initializes a persistent WebEngine profile stored at `~/.flow-browser/` on startup. This ensures cookies, cache, and session data persist between application restarts.
2. **WebEngine Integration**: The browser uses PyQt6's WebEngine with persistent storage paths configured for both cache and local storage
3. **Cookie Persistence**: All cookies set by websites are automatically saved to `~/.flow-browser/storage/` and restored when you reopen the browser
4. **Manual Storage**: The cookies manager also saves cookies to the `flow-cookies/cookies.json` file for inspection and backup
5. **Synchronization**: When you clear cookies through the Cookies dialog, both the stored file and WebEngine's cookie store are cleared

## Folder Structure

**Project Directory:**
```
flow-web/
├── flow.py
├── flow-bookmarks/
│   ├── bk1.txt
│   └── bk2.txt
└── flow-cookies/
    └── cookies.json
```

**User Home Directory (Persistent WebEngine Storage):**
```
~/.flow-browser/
├── cache/              # Browser cache and temporary files
└── storage/            # Cookies, session storage, and local storage
```

## Notes

- **Persistent Storage**: Cookies are automatically saved to `~/.flow-browser/storage/` and will persist across application restarts
- **Login Sessions**: Once you sign in to a website (e.g., Google), your login session is preserved when you reopen the browser
- **Default Location**: Qt WebEngine automatically manages cookie persistence to `~/.flow-browser/` without requiring manual configuration
- **Manual Inspection**: The `flow-cookies/` folder can be used to export or backup cookies if needed (created automatically on first access)
- **Custom Cookies**: You can manually add or edit cookies by modifying the `cookies.json` file (reload with the Refresh button)
- **Metadata**: Cookie data includes expiration dates, path, domain, and security flags
- **Session Cookies**: Display Session as expiration time instead of a specific date

## Privacy Considerations

- All cookies are stored locally on your machine in `flow-cookies/cookies.json`
- Clearing cookies removes them both from the stored file and from WebEngine's cache
- You can manually delete the `flow-cookies/` folder to completely remove all stored cookie data
