---
name: brand-colors-both-themes
description: Give an app its own brand palette in both light and dark mode with base_sdk AppStyle.injectBrandColors.
version: 1.0.0
---

# Brand colours in both themes (base_sdk)
**When:** an app needs its own palette in light and dark.

1. base_sdk >= 1.93.0. Call `AppStyle.injectBrandColors(primary, dark values..., surfaceLight, cardLight, cardLightAlt, strokeLight, strokeLightSubtle, textLightSecondary, textLightFaint, inkDark, inkLight)`.
2. Wire it from the app's brand hook (`app_type.<app>.brand_hook`), as `applyPolarisBrandColors` does.
3. Render both themes (procedure 1) to check the contrast.
