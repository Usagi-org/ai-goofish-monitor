# Firefox-based stealth option (proposal)

> Status: Draft proposal
> Created: 2026-05-27
> Tracking issue: TBD

## Goal

Optional Firefox-based stealth backend in `src/scraper.py`, parallel to the current `p.chromium.launch()` path (line 569). Selected via env, no change to defaults.

## Motivation

The current scraper uses a mobile Android Chrome user agent (`scraper.py:251`) plus Playwright's vanilla Chromium. Xianyu's anti-bot stack uses sliding-captcha plus device-level fingerprint checks (canvas, audio, WebGL, font metrics), so UA spoofing alone leaks plenty of automation signals. Related open issue: #492 "请问cookie总是失效有什么好的解决办法吗?" (cookie always expires).

A Firefox build with fingerprint patches at the C++ source code level avoids the JS-shim detection surface and extends session lifetime by reducing the device-fingerprint drift that triggers re-verification.

## Proposed change

A small branch in `src/scraper.py` so that, when `GF_BROWSER=invisible_firefox` is set, the scraper uses `firefox.launch(executable_path=..., firefox_user_prefs=...)` instead of `chromium.launch(**launch_kwargs)`. The wrapper class `InvisiblePlaywright` from `invisible_playwright` (https://github.com/feder-cr/invisible_playwright) handles binary download and pref injection.

The patched Firefox 150 binary lives at https://github.com/feder-cr/invisible_firefox (MPL-2.0, same license as Firefox upstream).

## Out of scope

No change to default Chromium path. No change to mobile UA spoofing. No change to the AI filter, proxy rotation, or notification layers.

## Maintenance

Issues against the backend route to feder-cr/invisible_playwright. Only ask of this repo would be the env-gated branch in `src/scraper.py` plus a README note.

---

## 简介

可选的 Firefox 隐身后端，作为 `src/scraper.py` 中现有 Chromium 路径的并行选项。通过 `GF_BROWSER=invisible_firefox` 启用，不影响默认行为。针对闲鱼滑块验证 + 设备指纹检测导致的 cookie 频繁失效问题（#492）。详细方案见上方英文部分。
