from components.anchored_tooltip import AnchoredTooltip
from components.inline_badge import InlineBadgeParagraphWrapper

ICON_ONLINE = "icons/wifi.svg"

def show_esp_wifi_guidance(
    parent,
    widget,
    esp_ssid,
):
    if not hasattr(
        parent,
        "esp_wifi_tooltips",
    ):
        parent.esp_wifi_tooltips = {}

    if widget in parent.esp_wifi_tooltips:
        return

    content = InlineBadgeParagraphWrapper()

    content.insert_text("OSS is connected to ")
    content.insert_badge_with_icon(esp_ssid, ICON_ONLINE)
    # --------------------------------------------------------
    # Tooltip
    # --------------------------------------------------------

    tooltip = AnchoredTooltip(
        content=content,
        target=widget,
        position="down",
    )

    parent.esp_wifi_tooltips[widget] = tooltip

    tooltip.show()