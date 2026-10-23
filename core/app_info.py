# =====================================================
# Singleton app_info for everywhere.
# Single Entry -> Modified here
# =====================================================
"""
- Snipaste-like protol: initial version with 1-screen support
- Snipaste-like v0.2: support multiple screen, rename to Snipin Main v0.2
    - reorganaize architecture
- 2026/09/01 Snipaste-like v1.0.0: single overlay, ACC hit test.
    - Remove mutiplescreen session.
    - Remove 2 overlays, keep only 1.
    - ACC hit test, no need transparent nor change system cursor
    - Change hotkey plugins.
    - Fix hotkeys settings dialog.
    - Modified Hotkeys manager, plugins manager, app controller.
    - Add logging

- 2026/09/04 Snipaste-like v1.0.1:
    - Add auto_startup option.
    - Change modules name format: SettingsDialog,KeyMapper,ColorPalette,CompactSlider,DotSizeButton
        EditableArrowItem,EditableTextItem,MosaicPenItem,InvisibleBoxLineItem
    - fix bug pin_viwer show taskbar. set as tool.
- 2026/09/11 Snipaste-like v1.1.0:
    - change config settings GUI: add plugins, add auto startup
    - add win + mouse plugin, extend findit function.
    - change ico
    - add shortcut hint panel.
    - change some structure.
- 2026/09/17 snipin v1.2.0:
    - totally rebuild grabview and pin view by Qgraphicview.
    - add snipin manager control capture and pin.
    - solve performance issue.
-2026/10/1 snipin v1.2.1
    - Optimize compiler.
    - refine toolbar.
-2026/10/2 snipin v1.2.2
    - restruct ui/ structure.
- 2026/10/3 1.2.3
    - fix bug snip.
    - plugin toolbar & plugin
- 2026/10/3 1.2.4
    - New settings dialog with userguide.
    - Fix plugin.
    - Deployed 1.2.4.3
- 2026/10/6 1.3.1
    - Improve performance: implement pin window pool.
    - New plugin UI, combine SAP & findit.
- 2026/10/14 1.3.2
    - Fix 1.3.1 bugs: closed pin & popup ui conflict in grabview.
    - Modified user_guide_tab
- 2026/10/14 1.3.3
    - fix bugs: dxcam _rebuild bugs. modified stagesurf.py in dxcam
    - fix bugs: Qtscreens vs Dxcam screens order mismatch.
    - fix bugs: Window theme effect.
    - fix bugs: Qt event loop not work after compile.
- 2026/10/17 1.3.4
    - Fix tray context menu.
    - Optimize settings UI.
- 2026/10/20 1.3.5
    - Fix auto startup
    - Add debouncing pre-rebuild cameras.

"""


class AppInfo:
    NAME = "SniPin Tool"
    VERSION = "1.3.5"
    PLATFORM = "Windows x64"
    COMPANY = ""
    DESCRIPTION = "A lightweight screen capture and productivity utility designed to simplify daily workflows."
    COPYRIGHT = "AD • AI assisted"
    APPICON = "snipin.png"
    # Proprietary warning text
    DISCLAIMER = (
        "This application is a proprietary internal tool. \n"
        "It is not for public use or distribution."
    )

    # Integrated refined features
    FEATURES = [
        "Flexible area selection",
        "Capture on-the-fly with Win + Mouse",
        "Drawing & annotation tools",
        "Pin snips to the screen",
        "Save snips to clipboard or directory",
        "Recognize text via OCR",
        "Dynamic plugin support",
        "Extract SO, 12NC, procedures, etc... from images",
        "Query SAP directly from images or text",
        "Quick lookup Findit + SAP via popup UI",
    ]

    @classmethod
    def about_text(cls):
        feature_list_html = "".join(f"<li>{feature}</li>" for feature in cls.FEATURES)

        # Replace newlines in warning with HTML line breaks
        warning_html = cls.DISCLAIMER.replace("\n", "<br>")

        return (
            f"<h2>{cls.NAME}</h2>"
            f"version {cls.VERSION} <small>© {cls.COPYRIGHT}</small><br><br>"
            f"{cls.DESCRIPTION}<br><br>"
            f"<b>⚙️ Key Features:</b>"
            f"<ul style='margin-top: 5px; margin-bottom: 5px;'>{feature_list_html}</ul><br>"
            f"<font color='#d32f2f'><b>⚠️ NOTICE:</b><br>"
            f"{warning_html}</font><br><br>"
        )
