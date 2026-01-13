# Xianyu Login State Extractor Chrome Extension

This Chrome extension helps extract complete login state information from Xianyu (Goofish) for use with the monitoring robot. It also records browser environment hints and request headers to better mimic a real session.

## Installation

1. Open Chrome and navigate to `chrome://extensions`
2. Enable "Developer mode" in the top right corner
3. Click "Load unpacked" and select the `chrome-extension` directory
4. The extension icon should now appear in your toolbar

## Usage

1. Navigate to [https://www.goofish.com](https://www.goofish.com)
2. Log in to your account
3. Click the extension icon in the toolbar
4. Click "Extract Login State" (collects cookies + environment + headers，自动过滤无用/超大字段)
5. The complete JSON will be displayed - click "Copy to Clipboard"
6. Save the JSON文本到 `xianyu_state.json`（或自定义文件名）即可

## Features

- Extracts all cookies including HttpOnly cookies
- Captures browser environment (UA, locale, timezone, screen size, device memory, hardware concurrency)
- Captures observed request headers for the current tab
- Captures localStorage/sessionStorage snapshot for the current domain（会自动丢弃超大或无用字段）
- Outputs a single JSON payload, ready for the monitoring robot
- Copy to clipboard with real-time status feedback

## How It Works

The extension uses the `chrome.cookies` API to access all cookies for the `.goofish.com` domain, including those with the HttpOnly flag set. This bypasses the normal JavaScript security restrictions that prevent access to these cookies.
